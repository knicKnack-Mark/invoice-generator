from datetime import date, timedelta
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.recurring_invoice import RecurringFrequency, RecurringInvoice
from app.repositories.client_repository import ClientRepository
from app.repositories.log_repository import LogRepository
from app.repositories.recurring_invoice_repository import RecurringInvoiceRepository
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.schemas.recurring_invoice import RecurringInvoiceCreate, RecurringInvoiceUpdate
from app.services.invoice_service import InvoiceService


def advance_date(current: date, frequency: RecurringFrequency) -> date:
    """Scheduling logic for the four frequencies in spec section 22."""
    if frequency == RecurringFrequency.weekly:
        return current + timedelta(weeks=1)
    if frequency == RecurringFrequency.monthly:
        return current + relativedelta(months=1)
    if frequency == RecurringFrequency.quarterly:
        return current + relativedelta(months=3)
    if frequency == RecurringFrequency.yearly:
        return current + relativedelta(years=1)
    raise ValueError(f"Unknown frequency: {frequency}")


class RecurringInvoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RecurringInvoiceRepository(db)
        self.clients = ClientRepository(db)
        self.logs = LogRepository(db)

    async def create(
        self, *, organization_id: UUID, payload: RecurringInvoiceCreate, actor_user_id: UUID
    ) -> RecurringInvoice:
        client = await self.clients.get_by_id(organization_id=organization_id, client_id=payload.client_id)
        if not client:
            raise ValidationAppError(
                "client_id does not refer to a client in this organization.", error_code="INVALID_CLIENT"
            )

        recurring = await self.repo.create(
            organization_id=organization_id,
            client_id=payload.client_id,
            frequency=RecurringFrequency(payload.frequency),
            currency=payload.currency,
            payment_terms_days=payload.payment_terms_days,
            notes=payload.notes,
            terms=payload.terms,
            next_run_date=payload.start_date,
            items=[i.model_dump() for i in payload.items],
        )
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="recurring_invoice.created",
            entity_type="recurring_invoice", entity_id=recurring.id,
        )
        await self.db.commit()
        return await self.get(organization_id=organization_id, recurring_id=recurring.id)

    async def get(self, *, organization_id: UUID, recurring_id: UUID) -> RecurringInvoice:
        recurring = await self.repo.get_by_id(organization_id=organization_id, recurring_id=recurring_id)
        if not recurring:
            raise NotFoundError("Recurring invoice not found.", error_code="RECURRING_INVOICE_NOT_FOUND")
        return recurring

    async def list(self, *, organization_id: UUID, is_active: bool | None = None) -> list[RecurringInvoice]:
        return await self.repo.list(organization_id=organization_id, is_active=is_active)

    async def update(
        self, *, organization_id: UUID, recurring_id: UUID, payload: RecurringInvoiceUpdate, actor_user_id: UUID
    ) -> RecurringInvoice:
        recurring = await self.get(organization_id=organization_id, recurring_id=recurring_id)
        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("frequency"):
            update_data["frequency"] = RecurringFrequency(update_data["frequency"])
        recurring = await self.repo.update(recurring, **update_data)
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="recurring_invoice.updated",
            entity_type="recurring_invoice", entity_id=recurring.id,
        )
        await self.db.commit()
        return recurring

    async def _generate_one(self, *, organization_id: UUID, recurring: RecurringInvoice, actor_user_id: UUID):
        invoice_payload = InvoiceCreate(
            client_id=recurring.client_id,
            invoice_date=recurring.next_run_date,
            due_date=recurring.next_run_date + timedelta(days=recurring.payment_terms_days),
            currency=recurring.currency,
            notes=recurring.notes,
            terms=recurring.terms,
            items=[
                InvoiceItemCreate(description=i.description, quantity=i.quantity, unit_price=i.unit_price)
                for i in recurring.items
            ],
        )
        invoice = await InvoiceService(self.db).create(
            organization_id=organization_id, payload=invoice_payload, actor_user_id=actor_user_id
        )

        await self.repo.update(recurring, next_run_date=advance_date(recurring.next_run_date, recurring.frequency))
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="recurring_invoice.generated",
            entity_type="recurring_invoice", entity_id=recurring.id,
            metadata={"invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number},
        )
        await self.db.commit()
        return invoice

    async def generate_now(self, *, organization_id: UUID, recurring_id: UUID, actor_user_id: UUID):
        """Manual 'generate this now' action, regardless of next_run_date."""
        recurring = await self.get(organization_id=organization_id, recurring_id=recurring_id)
        if not recurring.is_active:
            raise ValidationAppError("This recurring invoice is not active.", error_code="RECURRING_INVOICE_INACTIVE")
        return await self._generate_one(organization_id=organization_id, recurring=recurring, actor_user_id=actor_user_id)

    async def generate_due(self, *, organization_id: UUID, actor_user_id: UUID) -> list:
        """Generates an invoice for every active recurring invoice whose
        next_run_date has arrived. Meant to be hit once a day by an external
        scheduler (cron, a scheduled GitHub Action, etc.); there is no
        in-process scheduler yet."""
        due = await self.repo.list_due(organization_id=organization_id, as_of=date.today())
        generated = []
        for recurring in due:
            generated.append(
                await self._generate_one(organization_id=organization_id, recurring=recurring, actor_user_id=actor_user_id)
            )
        return generated