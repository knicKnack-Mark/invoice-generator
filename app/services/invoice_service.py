from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.integrations.email import email_backend
from app.integrations.pdf import render_invoice_pdf
from app.models.expense import Expense, ExpenseStatus
from app.models.invoice import Invoice, InvoiceStatus, VALID_INVOICE_TRANSITIONS
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.log_repository import LogRepository
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, PublicInvoiceOut


class InvoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InvoiceRepository(db)
        self.expenses = ExpenseRepository(db)
        self.logs = LogRepository(db)

    async def _load_and_validate_expenses(
        self, *, organization_id: UUID, client_id: UUID, expense_ids: list[UUID]
    ) -> list[Expense]:
        if not expense_ids:
            return []
        result = await self.db.execute(
            select(Expense).where(
                Expense.id.in_(expense_ids),
                Expense.organization_id == organization_id,
                Expense.deleted_at.is_(None),
            )
        )
        expenses = list(result.scalars().all())

        found_ids = {e.id for e in expenses}
        missing = set(expense_ids) - found_ids
        if missing:
            raise ValidationAppError(
                f"Expense(s) not found in this organization: {', '.join(str(i) for i in missing)}",
                error_code="INVALID_EXPENSE",
            )
        for e in expenses:
            if e.client_id != client_id:
                raise ValidationAppError(
                    f"Expense {e.id} does not belong to the invoice's client.", error_code="EXPENSE_CLIENT_MISMATCH"
                )
            if not e.billable:
                raise ValidationAppError(f"Expense {e.id} is not marked billable.", error_code="EXPENSE_NOT_BILLABLE")
            if e.invoiced_at is not None:
                raise ValidationAppError(
                    f"Expense {e.id} is already attached to another invoice.", error_code="EXPENSE_ALREADY_INVOICED"
                )
        return expenses

    @staticmethod
    def calculate_totals(items: list[dict], expenses: list[Expense]) -> dict:
        """The single source of truth for invoice money math. Never trusts
        client-submitted totals — everything here is derived from item/expense
        inputs using Decimal arithmetic."""
        subtotal = Decimal("0")
        tax_total = Decimal("0")
        discount_total = Decimal("0")

        for item in items:
            qty = item["quantity"]
            line_subtotal = qty * item["unit_price"]
            subtotal += line_subtotal
            discount_total += item["discount"]
            tax_total += item["tax"]
            item["total"] = line_subtotal - item["discount"] + item["tax"]

        expense_links = []
        for e in expenses:
            amount = e.amount + e.tax
            subtotal += amount
            tax_total += e.tax
            expense_links.append({"expense_id": e.id, "amount": amount})

        # total is the sum of each item's already-net total (qty*price - discount + tax)
        # plus each attached expense's amount+tax — never subtotal-discount+tax
        # computed separately, which would double-count tax already folded into
        # the per-item totals above.
        total = sum((item["total"] for item in items), Decimal("0")) + sum(
            (link["amount"] for link in expense_links), Decimal("0")
        )

        return {
            "subtotal": subtotal,
            "tax_total": tax_total,
            "discount_total": discount_total,
            "total": total,
            "expense_links": expense_links,
        }

    async def create(self, *, organization_id: UUID, payload: InvoiceCreate, actor_user_id: UUID) -> Invoice:
        if not await self.repo.client_exists(organization_id=organization_id, client_id=payload.client_id):
            raise ValidationAppError("client_id does not refer to a client in this organization.", error_code="INVALID_CLIENT")
        if not payload.items and not payload.expense_ids:
            raise ValidationAppError("Invoice must have at least one line item or one attached expense.", error_code="EMPTY_INVOICE")

        expenses = await self._load_and_validate_expenses(
            organization_id=organization_id, client_id=payload.client_id, expense_ids=payload.expense_ids
        )

        item_dicts = [i.model_dump() for i in payload.items]
        totals = self.calculate_totals(item_dicts, expenses)

        due_date = payload.due_date or (payload.invoice_date + timedelta(days=settings.default_payment_terms_days))
        invoice_number = await self.repo.next_invoice_number(organization_id=organization_id, year=payload.invoice_date.year)

        invoice = await self.repo.create(
            organization_id=organization_id,
            client_id=payload.client_id,
            invoice_number=invoice_number,
            invoice_date=payload.invoice_date,
            due_date=due_date,
            currency=payload.currency,
            notes=payload.notes,
            terms=payload.terms,
            subtotal=totals["subtotal"],
            tax_total=totals["tax_total"],
            discount_total=totals["discount_total"],
            total=totals["total"],
            items=[{k: v for k, v in item.items()} for item in item_dicts],
            expense_links=totals["expense_links"],
        )

        # Mark attached expenses as billed and no longer eligible for another invoice.
        for e in expenses:
            e.invoiced_at = invoice.created_at
            e.status = ExpenseStatus.billed
        await self.db.flush()

        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="invoice.created",
            entity_type="invoice", entity_id=invoice.id, metadata={"invoice_number": invoice.invoice_number},
        )
        await self.db.commit()
        return await self.get(organization_id=organization_id, invoice_id=invoice.id)

    async def get(self, *, organization_id: UUID, invoice_id: UUID) -> Invoice:
        invoice = await self.repo.get_by_id(organization_id=organization_id, invoice_id=invoice_id)
        if not invoice:
            raise NotFoundError("Invoice not found.", error_code="INVOICE_NOT_FOUND")
        return invoice

    async def get_by_public_token(self, *, public_token: str) -> tuple[Invoice, PublicInvoiceOut]:
        invoice = await self.repo.get_by_public_token(public_token=public_token)
        if not invoice:
            raise NotFoundError("Invoice not found.", error_code="INVOICE_NOT_FOUND")

        # First public view of a sent invoice transitions it to 'viewed'.
        if invoice.status == InvoiceStatus.sent:
            invoice = await self.repo.set_status(invoice, InvoiceStatus.viewed)
            await self.logs.record_activity(
                organization_id=invoice.organization_id, user_id=None, action="invoice.viewed",
                entity_type="invoice", entity_id=invoice.id,
            )
            await self.db.commit()

        client_name = await self.repo.get_client_name(client_id=invoice.client_id) or ""
        org_name = await self.repo.get_organization_name(organization_id=invoice.organization_id) or ""

        public_out = PublicInvoiceOut(
            invoice_number=invoice.invoice_number, status=invoice.status.value,
            invoice_date=invoice.invoice_date, due_date=invoice.due_date, currency=invoice.currency,
            subtotal=invoice.subtotal, tax_total=invoice.tax_total, discount_total=invoice.discount_total,
            total=invoice.total, amount_paid=invoice.amount_paid, balance_due=invoice.balance_due,
            is_overdue=invoice.is_overdue, terms=invoice.terms, items=invoice.items,
            client_name=client_name, organization_name=org_name,
        )
        return invoice, public_out

    async def list(self, *, organization_id: UUID, page: int, page_size: int, **filters) -> tuple[list[Invoice], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), settings.max_page_size)
        return await self.repo.list(organization_id=organization_id, page=page, page_size=page_size, **filters)

    async def update(
        self, *, organization_id: UUID, invoice_id: UUID, payload: InvoiceUpdate, actor_user_id: UUID
    ) -> Invoice:
        invoice = await self.get(organization_id=organization_id, invoice_id=invoice_id)
        if invoice.status != InvoiceStatus.draft:
            raise ValidationAppError("Only draft invoices can be edited.", error_code="INVOICE_NOT_EDITABLE")

        update_data = payload.model_dump(exclude_unset=True)
        invoice = await self.repo.update(invoice, **update_data)
        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="invoice.updated",
            entity_type="invoice", entity_id=invoice.id, metadata={"fields": list(update_data.keys())},
        )
        await self.db.commit()
        return await self.get(organization_id=organization_id, invoice_id=invoice_id)

    async def _release_expenses(self, *, invoice_id: UUID) -> None:
        expense_ids = await self.repo.remove_expense_links(invoice_id=invoice_id)
        if not expense_ids:
            return
        result = await self.db.execute(select(Expense).where(Expense.id.in_(expense_ids)))
        for e in result.scalars().all():
            e.invoiced_at = None
            if e.status == ExpenseStatus.billed:
                e.status = ExpenseStatus.approved
        await self.db.flush()

    async def change_status(
        self, *, organization_id: UUID, invoice_id: UUID, new_status: str, actor_user_id: UUID
    ) -> Invoice:
        invoice = await self.get(organization_id=organization_id, invoice_id=invoice_id)
        target = InvoiceStatus(new_status)
        allowed = VALID_INVOICE_TRANSITIONS.get(invoice.status, set())
        if target not in allowed:
            raise ValidationAppError(
                f"Cannot move invoice from '{invoice.status.value}' to '{target.value}'.",
                error_code="INVALID_STATUS_TRANSITION",
            )

        if target == InvoiceStatus.cancelled:
            await self._release_expenses(invoice_id=invoice.id)

        invoice = await self.repo.set_status(invoice, target)

        if target == InvoiceStatus.paid:
            invoice = await self.repo.update(invoice, amount_paid=invoice.total)

        await self.logs.record_activity(
            organization_id=organization_id, user_id=actor_user_id, action="invoice.status_changed",
            entity_type="invoice", entity_id=invoice.id,
            metadata={"from": invoice.status.value, "to": target.value},
        )
        await self.db.commit()
        return await self.get(organization_id=organization_id, invoice_id=invoice_id)

    async def send(self, *, organization_id: UUID, invoice_id: UUID, actor_user_id: UUID) -> Invoice:
        invoice = await self.change_status(
            organization_id=organization_id, invoice_id=invoice_id, new_status="sent", actor_user_id=actor_user_id
        )
        client_name = await self.repo.get_client_name(client_id=invoice.client_id) or "Client"
        pdf_bytes = render_invoice_pdf(invoice=invoice, client_name=client_name)
        # In dev this just logs; swap EMAIL_BACKEND for a real provider to
        # actually deliver it — no code here changes when that happens.
        await email_backend.send(
            to="client@example.com",  # replace with the client's actual email once Client.email is loaded here
            subject=f"Invoice {invoice.invoice_number}",
            html_body=f"<p>Please find attached invoice {invoice.invoice_number}, total {invoice.currency} {invoice.total}.</p>",
            attachments=[(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")],
        )
        return invoice

    async def delete(self, *, organization_id: UUID, invoice_id: UUID, actor_user_id: UUID) -> None:
        invoice = await self.get(organization_id=organization_id, invoice_id=invoice_id)
        if invoice.status != InvoiceStatus.draft:
            raise ValidationAppError("Only draft invoices can be deleted.", error_code="INVOICE_NOT_DELETABLE")
        await self._release_expenses(invoice_id=invoice.id)
        await self.repo.soft_delete(invoice)
        await self.logs.record_audit(
            organization_id=organization_id, user_id=actor_user_id, action="invoice.deleted",
            entity_type="invoice", entity_id=invoice_id,
        )
        await self.db.commit()

    async def get_pdf_bytes(self, *, organization_id: UUID, invoice_id: UUID) -> bytes:
        invoice = await self.get(organization_id=organization_id, invoice_id=invoice_id)
        client_name = await self.repo.get_client_name(client_id=invoice.client_id) or ""
        return render_invoice_pdf(invoice=invoice, client_name=client_name)
