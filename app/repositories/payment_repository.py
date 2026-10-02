from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, organization_id: UUID, invoice_id: UUID, **fields) -> Payment:
        payment = Payment(organization_id=organization_id, invoice_id=invoice_id, **fields)
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def get_by_id(self, *, organization_id: UUID, payment_id: UUID) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def list_for_invoice(self, *, organization_id: UUID, invoice_id: UUID) -> list[Payment]:
        result = await self.db.execute(
            select(Payment)
            .where(Payment.organization_id == organization_id, Payment.invoice_id == invoice_id)
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        )
        return list(result.scalars().all())

    async def list(
        self, *, organization_id: UUID, page: int, page_size: int, invoice_id: UUID | None = None
    ) -> tuple[list[Payment], int]:
        conditions = [Payment.organization_id == organization_id]
        if invoice_id:
            conditions.append(Payment.invoice_id == invoice_id)

        count_result = await self.db.execute(select(func.count()).select_from(Payment).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Payment)
            .where(*conditions)
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def sum_for_invoice(self, *, invoice_id: UUID, exclude_payment_id: UUID | None = None) -> Decimal:
        conditions = [Payment.invoice_id == invoice_id]
        if exclude_payment_id:
            conditions.append(Payment.id != exclude_payment_id)
        result = await self.db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(*conditions))
        return Decimal(result.scalar_one())

    async def delete(self, payment: Payment) -> None:
        await self.db.delete(payment)
        await self.db.flush()