from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.invoice import InvoiceStatus
from app.models.payment import Payment
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.log_repository import LogRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import PaymentCreate

# Invoice statuses a payment can legally be recorded against. A draft
# invoice hasn't been sent yet, and a cancelled one is dead — recording
# money against either would be nonsensical bookkeeping.
PAYABLE_STATUSES = (InvoiceStatus.sent, InvoiceStatus.viewed, InvoiceStatus.partially_paid)


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PaymentRepository(db)
        self.invoices = InvoiceRepository(db)
        self.logs = LogRepository(db)

    async def _recompute_invoice_status(self, *, invoice_id: UUID, organization_id: UUID) -> None:
        """Single source of truth for an invoice's amount_paid/status after
        any payment is created or deleted. Recomputed as a full sum of
        remaining payments each time, rather than incrementally adjusted, so
        it can never drift out of sync with the actual payment rows."""
        invoice = await self.invoices.get_by_id(organization_id=organization_id, invoice_id=invoice_id)
        total_paid = await self.repo.sum_for_invoice(invoice_id=invoice_id)

        if total_paid <= 0:
            new_status = InvoiceStatus.sent if invoice.status != InvoiceStatus.cancelled else invoice.status
        elif total_paid < invoice.total:
            new_status = InvoiceStatus.partially_paid
        else:
            new_status = InvoiceStatus.paid

        # This bypasses VALID_INVOICE_TRANSITIONS deliberately: that table
        # governs user-driven status changes via the /status endpoint, not
        # this derived recalculation triggered by the payment ledger.
        await self.invoices.update(invoice, amount_paid=total_paid)
        await self.invoices.set_status(invoice, new_status)

    async def create(
        self, *, organization_id: UUID, invoice_id: UUID, payload: PaymentCreate, actor_user_id: UUID
    ) -> Payment:
        invoice = await self.invoices.get_by_id(organization_id=organization_id, invoice_id=invoice_id)
        if not invoice:
            raise NotFoundError("Invoice not found.", error_code="INVOICE_NOT_FOUND")
        if invoice.status not in PAYABLE_STATUSES:
            raise ValidationAppError(
                f"Cannot record a payment against an invoice with status '{invoice.status.value}'.",
                error_code="INVOICE_NOT_PAYABLE",
            )
        if payload.currency != invoice.currency:
            raise ValidationAppError(
                f"Payment currency ({payload.currency}) must match the invoice's currency ({invoice.currency}). "
                "Currency conversion is not performed automatically.",
                error_code="CURRENCY_MISMATCH",
            )

        balance_due = invoice.balance_due
        if payload.amount > balance_due:
            raise ValidationAppError(
                f"Payment amount ({payload.amount}) exceeds the remaining balance ({balance_due}).",
                error_code="AMOUNT_EXCEEDS_BALANCE",
            )

        payment = await self.repo.create(organization_id=organization_id, invoice_id=invoice_id, **payload.model_dump())
        await self._recompute_invoice_status(invoice_id=invoice_id, organization_id=organization_id)

        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="payment.recorded",
            entity_type="payment", entity_id=payment.id,
            metadata={"invoice_id": str(invoice_id), "amount": str(payload.amount)},
        )
        await self.db.commit()
        return payment

    async def get(self, *, organization_id: UUID, payment_id: UUID) -> Payment:
        payment = await self.repo.get_by_id(organization_id=organization_id, payment_id=payment_id)
        if not payment:
            raise NotFoundError("Payment not found.", error_code="PAYMENT_NOT_FOUND")
        return payment

    async def list_for_invoice(self, *, organization_id: UUID, invoice_id: UUID) -> list[Payment]:
        return await self.repo.list_for_invoice(organization_id=organization_id, invoice_id=invoice_id)

    async def list(self, *, organization_id: UUID, page: int, page_size: int, invoice_id: UUID | None = None):
        page = max(page, 1)
        page_size = min(max(page_size, 1), settings.max_page_size)
        return await self.repo.list(organization_id=organization_id, page=page, page_size=page_size, invoice_id=invoice_id)

    async def delete(self, *, organization_id: UUID, payment_id: UUID, actor_user_id: UUID) -> None:
        payment = await self.get(organization_id=organization_id, payment_id=payment_id)
        invoice_id = payment.invoice_id
        await self.repo.delete(payment)
        await self._recompute_invoice_status(invoice_id=invoice_id, organization_id=organization_id)

        # Reversing a recorded payment is a financial correction — audit-worthy,
        # not just an activity-log entry.
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="payment.deleted",
            entity_type="payment", entity_id=payment_id, metadata={"invoice_id": str(invoice_id)},
        )
        await self.db.commit()
