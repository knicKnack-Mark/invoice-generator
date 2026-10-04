from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.expense import Expense, ExpenseCategory
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment

OUTSTANDING_STATUSES = (InvoiceStatus.sent, InvoiceStatus.viewed, InvoiceStatus.partially_paid)


class DashboardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def total_revenue(self, *, organization_id: UUID) -> Decimal:
        result = await self.db.execute(
            select(func.coalesce(func.sum(Invoice.amount_paid), 0)).where(
                Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None)
            )
        )
        return Decimal(result.scalar_one())

    async def outstanding_and_overdue(self, *, organization_id: UUID) -> tuple[Decimal, Decimal]:
        result = await self.db.execute(
            select(Invoice.total, Invoice.amount_paid, Invoice.due_date, Invoice.status).where(
                Invoice.organization_id == organization_id,
                Invoice.deleted_at.is_(None),
                Invoice.status.in_(OUTSTANDING_STATUSES),
            )
        )
        rows = result.all()
        outstanding = Decimal("0")
        overdue = Decimal("0")
        today = date.today()
        for total, amount_paid, due_date, _status in rows:
            balance = Decimal(total) - Decimal(amount_paid)
            outstanding += balance
            if due_date < today:
                overdue += balance
        return outstanding, overdue

    async def expenses_sum(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None, billable: bool | None = None
    ) -> Decimal:
        conditions = [Expense.organization_id == organization_id, Expense.deleted_at.is_(None)]
        if date_from:
            conditions.append(Expense.expense_date >= date_from)
        if date_to:
            conditions.append(Expense.expense_date <= date_to)
        if billable is not None:
            conditions.append(Expense.billable == billable)
        result = await self.db.execute(
            select(func.coalesce(func.sum(Expense.amount + Expense.tax), 0)).where(*conditions)
        )
        return Decimal(result.scalar_one())

    async def unbilled_expenses_sum(self, *, organization_id: UUID) -> Decimal:
        result = await self.db.execute(
            select(func.coalesce(func.sum(Expense.amount + Expense.tax), 0)).where(
                Expense.organization_id == organization_id,
                Expense.deleted_at.is_(None),
                Expense.billable.is_(True),
                Expense.invoiced_at.is_(None),
            )
        )
        return Decimal(result.scalar_one())

    async def invoice_status_counts(self, *, organization_id: UUID) -> tuple[int, int]:
        result = await self.db.execute(
            select(Invoice.status, Invoice.due_date).where(
                Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None)
            )
        )
        rows = result.all()
        today = date.today()
        paid = sum(1 for status, _ in rows if status == InvoiceStatus.paid)
        pending = sum(
            1 for status, due_date in rows
            if status in (InvoiceStatus.draft, *OUTSTANDING_STATUSES) and due_date >= today
        )
        return paid, pending

    async def revenue_by_client(self, *, organization_id: UUID, limit: int = 10) -> list[tuple]:
        result = await self.db.execute(
            select(Client.id, Client.name, func.coalesce(func.sum(Invoice.amount_paid), 0))
            .join(Invoice, Invoice.client_id == Client.id)
            .where(Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None))
            .group_by(Client.id, Client.name)
            .order_by(func.sum(Invoice.amount_paid).desc())
            .limit(limit)
        )
        return result.all()

    async def expense_by_category(self, *, organization_id: UUID, limit: int = 10) -> list[tuple]:
        result = await self.db.execute(
            select(
                ExpenseCategory.id, func.coalesce(ExpenseCategory.name, "Uncategorized"),
                func.coalesce(func.sum(Expense.amount + Expense.tax), 0),
            )
            .select_from(Expense)
            .outerjoin(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(Expense.organization_id == organization_id, Expense.deleted_at.is_(None))
            .group_by(ExpenseCategory.id, ExpenseCategory.name)
            .order_by(func.sum(Expense.amount + Expense.tax).desc())
            .limit(limit)
        )
        return result.all()

    async def recent_invoices(self, *, organization_id: UUID, limit: int = 5) -> list[tuple]:
        result = await self.db.execute(
            select(Invoice, Client.name)
            .join(Client, Client.id == Invoice.client_id)
            .where(Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None))
            .order_by(Invoice.created_at.desc())
            .limit(limit)
        )
        return result.all()

    async def recent_expenses(self, *, organization_id: UUID, limit: int = 5) -> list[Expense]:
        result = await self.db.execute(
            select(Expense)
            .where(Expense.organization_id == organization_id, Expense.deleted_at.is_(None))
            .order_by(Expense.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def recent_payments(self, *, organization_id: UUID, limit: int = 5) -> list[tuple]:
        result = await self.db.execute(
            select(Payment, Invoice.invoice_number)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .where(Payment.organization_id == organization_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return result.all()

    async def upcoming_due(self, *, organization_id: UUID, limit: int = 5) -> list[tuple]:
        result = await self.db.execute(
            select(Invoice, Client.name)
            .join(Client, Client.id == Invoice.client_id)
            .where(
                Invoice.organization_id == organization_id,
                Invoice.deleted_at.is_(None),
                Invoice.status.in_(OUTSTANDING_STATUSES),
                Invoice.due_date >= date.today(),
            )
            .order_by(Invoice.due_date.asc())
            .limit(limit)
        )
        return result.all()
