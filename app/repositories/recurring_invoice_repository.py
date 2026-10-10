from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.recurring_invoice import RecurringInvoice, RecurringInvoiceItem


class RecurringInvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        return select(RecurringInvoice).options(selectinload(RecurringInvoice.items))

    async def create(self, *, organization_id: UUID, items: list[dict], **fields) -> RecurringInvoice:
        recurring = RecurringInvoice(organization_id=organization_id, **fields)
        self.db.add(recurring)
        await self.db.flush()
        for item_fields in items:
            self.db.add(RecurringInvoiceItem(recurring_invoice_id=recurring.id, **item_fields))
        await self.db.flush()
        return recurring

    async def get_by_id(self, *, organization_id: UUID, recurring_id: UUID) -> RecurringInvoice | None:
        result = await self.db.execute(
            self._base_query().where(
                RecurringInvoice.id == recurring_id, RecurringInvoice.organization_id == organization_id
            )
        )
        return result.unique().scalar_one_or_none()

    async def list(self, *, organization_id: UUID, is_active: bool | None = None) -> list[RecurringInvoice]:
        conditions = [RecurringInvoice.organization_id == organization_id]
        if is_active is not None:
            conditions.append(RecurringInvoice.is_active == is_active)
        result = await self.db.execute(
            self._base_query().where(*conditions).order_by(RecurringInvoice.next_run_date.asc())
        )
        return list(result.unique().scalars().all())

    async def list_due(self, *, organization_id: UUID, as_of: date) -> list[RecurringInvoice]:
        result = await self.db.execute(
            self._base_query().where(
                RecurringInvoice.organization_id == organization_id,
                RecurringInvoice.is_active.is_(True),
                RecurringInvoice.next_run_date <= as_of,
            )
        )
        return list(result.unique().scalars().all())

    async def update(self, recurring: RecurringInvoice, **fields) -> RecurringInvoice:
        for key, value in fields.items():
            if value is not None:
                setattr(recurring, key, value)
        await self.db.flush()
        return recurring