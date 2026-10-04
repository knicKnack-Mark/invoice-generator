from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceExpense, InvoiceItem, InvoiceStatus
from app.models.organization import Organization


class InvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def client_exists(self, *, organization_id: UUID, client_id: UUID) -> bool:
        result = await self.db.execute(
            select(Client.id).where(
                Client.id == client_id, Client.organization_id == organization_id, Client.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_client_name(self, *, client_id: UUID) -> str | None:
        result = await self.db.execute(select(Client.name).where(Client.id == client_id))
        return result.scalar_one_or_none()

    async def get_organization_name(self, *, organization_id: UUID) -> str | None:
        result = await self.db.execute(select(Organization.name).where(Organization.id == organization_id))
        return result.scalar_one_or_none()

    async def next_invoice_number(self, *, organization_id: UUID, year: int) -> str:
        """Per-organization, per-year sequence: INV-2026-0001, INV-2026-0002, ...
        Counts existing invoices for this org+year rather than a separate
        counter table — simple and correct as long as invoices are only
        ever created through this method (never bulk-inserted directly)."""
        prefix = f"{settings.invoice_number_prefix}-{year}-"
        result = await self.db.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.organization_id == organization_id, Invoice.invoice_number.like(f"{prefix}%"))
        )
        count = result.scalar_one()
        return f"{prefix}{count + 1:04d}"

    async def create(
        self, *, organization_id: UUID, items: list[dict], expense_links: list[dict], **fields
    ) -> Invoice:
        invoice = Invoice(organization_id=organization_id, **fields)
        self.db.add(invoice)
        await self.db.flush()  # need invoice.id for children

        for idx, item_fields in enumerate(items):
            self.db.add(InvoiceItem(invoice_id=invoice.id, sort_order=idx, **item_fields))
        for link_fields in expense_links:
            self.db.add(InvoiceExpense(invoice_id=invoice.id, **link_fields))

        await self.db.flush()
        return invoice

    def _base_query(self):
        return select(Invoice).options(selectinload(Invoice.items), selectinload(Invoice.expenses))

    async def get_by_id(self, *, organization_id: UUID, invoice_id: UUID) -> Invoice | None:
        result = await self.db.execute(
            self._base_query().where(
                Invoice.id == invoice_id, Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None)
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_by_public_token(self, *, public_token: str) -> Invoice | None:
        result = await self.db.execute(
            self._base_query().where(Invoice.public_token == public_token, Invoice.deleted_at.is_(None))
        )
        return result.unique().scalar_one_or_none()

    async def list(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        client_id: UUID | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[Invoice], int]:
        conditions = [Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None)]
        if client_id:
            conditions.append(Invoice.client_id == client_id)
        if status:
            conditions.append(Invoice.status == InvoiceStatus(status))
        if date_from:
            conditions.append(Invoice.invoice_date >= date_from)
        if date_to:
            conditions.append(Invoice.invoice_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(Invoice).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            self._base_query()
            .where(*conditions)
            .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().scalars().all()), total

    async def update(self, invoice: Invoice, **fields) -> Invoice:
        for key, value in fields.items():
            if value is not None:
                setattr(invoice, key, value)
        await self.db.flush()
        return invoice

    async def set_status(self, invoice: Invoice, status: InvoiceStatus) -> Invoice:
        invoice.status = status
        await self.db.flush()
        return invoice

    async def soft_delete(self, invoice: Invoice) -> None:
        from datetime import datetime, timezone

        invoice.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def remove_expense_links(self, *, invoice_id: UUID) -> list[UUID]:
        """Returns the expense_ids that were linked, so the caller (service)
        can release them back to 'approved' status."""
        result = await self.db.execute(select(InvoiceExpense).where(InvoiceExpense.invoice_id == invoice_id))
        links = list(result.scalars().all())
        expense_ids = [link.expense_id for link in links]
        for link in links:
            await self.db.delete(link)
        await self.db.flush()
        return expense_ids
