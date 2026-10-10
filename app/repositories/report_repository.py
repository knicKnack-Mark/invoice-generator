from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.models.expense import Expense, ExpenseCategory
from app.models.invoice import Invoice, InvoiceStatus
from app.models.time_entry import TimeEntry

OUTSTANDING_STATUSES = (InvoiceStatus.sent, InvoiceStatus.viewed, InvoiceStatus.partially_paid)


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def revenue_by_client(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> list[tuple]:
        conditions = [Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None)]
        if date_from:
            conditions.append(Invoice.invoice_date >= date_from)
        if date_to:
            conditions.append(Invoice.invoice_date <= date_to)
        result = await self.db.execute(
            select(Client.id, Client.name, func.coalesce(func.sum(Invoice.amount_paid), 0))
            .join(Invoice, Invoice.client_id == Client.id)
            .where(*conditions)
            .group_by(Client.id, Client.name)
            .order_by(func.sum(Invoice.amount_paid).desc())
        )
        return result.all()

    async def expenses_by_category(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> list[tuple]:
        conditions = [Expense.organization_id == organization_id, Expense.deleted_at.is_(None)]
        if date_from:
            conditions.append(Expense.expense_date >= date_from)
        if date_to:
            conditions.append(Expense.expense_date <= date_to)
        result = await self.db.execute(
            select(
                ExpenseCategory.id,
                func.coalesce(ExpenseCategory.name, "Uncategorized"),
                func.coalesce(func.sum(Expense.amount + Expense.tax), 0),
            )
            .select_from(Expense)
            .outerjoin(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(*conditions)
            .group_by(ExpenseCategory.id, ExpenseCategory.name)
            .order_by(func.sum(Expense.amount + Expense.tax).desc())
        )
        return result.all()

    async def outstanding_invoices(self, *, organization_id: UUID) -> list[tuple]:
        result = await self.db.execute(
            select(Invoice, Client.name)
            .join(Client, Client.id == Invoice.client_id)
            .where(
                Invoice.organization_id == organization_id,
                Invoice.deleted_at.is_(None),
                Invoice.status.in_(OUTSTANDING_STATUSES),
            )
            .order_by(Invoice.due_date.asc())
        )
        return result.all()

    async def client_profitability(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> list[dict]:
        """Per-client revenue, expenses and hours, built from three separate
        aggregate queries instead of one big join, so a client with many
        invoices AND many expenses doesn't get its rows multiplied."""
        client_result = await self.db.execute(
            select(Client.id, Client.name).where(
                Client.organization_id == organization_id, Client.deleted_at.is_(None)
            )
        )
        clients = {cid: name for cid, name in client_result.all()}

        rev_conditions = [Invoice.organization_id == organization_id, Invoice.deleted_at.is_(None)]
        exp_conditions = [Expense.organization_id == organization_id, Expense.deleted_at.is_(None)]
        time_conditions = [TimeEntry.organization_id == organization_id, TimeEntry.deleted_at.is_(None)]
        if date_from:
            rev_conditions.append(Invoice.invoice_date >= date_from)
            exp_conditions.append(Expense.expense_date >= date_from)
            time_conditions.append(TimeEntry.entry_date >= date_from)
        if date_to:
            rev_conditions.append(Invoice.invoice_date <= date_to)
            exp_conditions.append(Expense.expense_date <= date_to)
            time_conditions.append(TimeEntry.entry_date <= date_to)

        revenue_rows = await self.db.execute(
            select(Invoice.client_id, func.coalesce(func.sum(Invoice.amount_paid), 0))
            .where(*rev_conditions)
            .group_by(Invoice.client_id)
        )
        revenue_by_client = {cid: total for cid, total in revenue_rows.all()}

        expense_rows = await self.db.execute(
            select(Expense.client_id, func.coalesce(func.sum(Expense.amount + Expense.tax), 0))
            .where(*exp_conditions)
            .group_by(Expense.client_id)
        )
        expenses_by_client = {cid: total for cid, total in expense_rows.all()}

        time_rows = await self.db.execute(
            select(TimeEntry.client_id, func.coalesce(func.sum(TimeEntry.duration_minutes), 0))
            .where(*time_conditions)
            .group_by(TimeEntry.client_id)
        )
        minutes_by_client = {cid: total for cid, total in time_rows.all()}

        results = []
        for client_id, name in clients.items():
            revenue = Decimal(revenue_by_client.get(client_id, 0))
            expenses = Decimal(expenses_by_client.get(client_id, 0))
            minutes = minutes_by_client.get(client_id, 0)
            if revenue == 0 and expenses == 0 and minutes == 0:
                continue  # skip clients with no activity in the period
            results.append({
                "client_id": client_id,
                "client_name": name,
                "revenue": revenue,
                "expenses": expenses,
                "hours": Decimal(minutes) / Decimal(60),
            })
        return results