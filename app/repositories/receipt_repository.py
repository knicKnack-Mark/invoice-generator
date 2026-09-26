from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.receipt import ExpenseReceipt


class ReceiptRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def expense_belongs_to_org(self, *, organization_id: UUID, expense_id: UUID) -> bool:
        result = await self.db.execute(
            select(Expense.id).where(
                Expense.id == expense_id,
                Expense.organization_id == organization_id,
                Expense.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(self, *, expense_id: UUID, **fields) -> ExpenseReceipt:
        receipt = ExpenseReceipt(expense_id=expense_id, **fields)
        self.db.add(receipt)
        await self.db.flush()
        return receipt

    async def list_for_expense(self, *, organization_id: UUID, expense_id: UUID) -> list[ExpenseReceipt]:
        result = await self.db.execute(
            select(ExpenseReceipt)
            .join(Expense, Expense.id == ExpenseReceipt.expense_id)
            .where(
                ExpenseReceipt.expense_id == expense_id,
                Expense.organization_id == organization_id,
            )
            .order_by(ExpenseReceipt.uploaded_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, *, organization_id: UUID, receipt_id: UUID) -> ExpenseReceipt | None:
        result = await self.db.execute(
            select(ExpenseReceipt)
            .join(Expense, Expense.id == ExpenseReceipt.expense_id)
            .where(
                ExpenseReceipt.id == receipt_id,
                Expense.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, receipt: ExpenseReceipt, **fields) -> ExpenseReceipt:
        for key, value in fields.items():
            if value is not None:
                setattr(receipt, key, value)
        await self.db.flush()
        return receipt

    async def delete(self, receipt: ExpenseReceipt) -> None:
        await self.db.delete(receipt)
        await self.db.flush()
