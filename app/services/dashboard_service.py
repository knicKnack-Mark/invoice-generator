from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    DashboardOut,
    DashboardTotals,
    ExpenseByCategoryItem,
    RecentExpenseItem,
    RecentInvoiceItem,
    RecentPaymentItem,
    RevenueByClientItem,
    UpcomingDueItem,
)


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DashboardRepository(db)

    async def get_overview(self, *, organization_id: UUID) -> DashboardOut:
        today = date.today()
        month_start = today.replace(day=1)

        total_revenue = await self.repo.total_revenue(organization_id=organization_id)
        outstanding, overdue = await self.repo.outstanding_and_overdue(organization_id=organization_id)
        expenses_this_month = await self.repo.expenses_sum(
            organization_id=organization_id, date_from=month_start, date_to=today
        )
        billable_expenses = await self.repo.expenses_sum(
            organization_id=organization_id, date_from=month_start, date_to=today, billable=True
        )
        unbilled_expenses = await self.repo.unbilled_expenses_sum(organization_id=organization_id)
        paid_count, pending_count = await self.repo.invoice_status_counts(organization_id=organization_id)

        totals = DashboardTotals(
            total_revenue=total_revenue,
            outstanding_invoices=outstanding,
            overdue_invoices=overdue,
            expenses_this_month=expenses_this_month,
            billable_expenses=billable_expenses,
            unbilled_expenses=unbilled_expenses,
            paid_invoices_count=paid_count,
            pending_invoices_count=pending_count,
        )

        revenue_rows = await self.repo.revenue_by_client(organization_id=organization_id)
        revenue_by_client = [
            RevenueByClientItem(client_id=cid, client_name=name, total=total) for cid, name, total in revenue_rows
        ]

        expense_rows = await self.repo.expense_by_category(organization_id=organization_id)
        expense_by_category = [
            ExpenseByCategoryItem(category_id=cid, category_name=name, total=total)
            for cid, name, total in expense_rows
        ]

        invoice_rows = await self.repo.recent_invoices(organization_id=organization_id)
        recent_invoices = [
            RecentInvoiceItem(
                id=inv.id, invoice_number=inv.invoice_number, client_name=client_name,
                status=inv.status.value, total=inv.total, currency=inv.currency, invoice_date=inv.invoice_date,
            )
            for inv, client_name in invoice_rows
        ]

        recent_expenses = [
            RecentExpenseItem(
                id=e.id, vendor=e.vendor, amount=e.amount, currency=e.currency,
                expense_date=e.expense_date, billable=e.billable,
            )
            for e in await self.repo.recent_expenses(organization_id=organization_id)
        ]

        payment_rows = await self.repo.recent_payments(organization_id=organization_id)
        recent_payments = [
            RecentPaymentItem(
                id=p.id, invoice_id=p.invoice_id, invoice_number=invoice_number,
                amount=p.amount, currency=p.currency, payment_date=p.payment_date,
            )
            for p, invoice_number in payment_rows
        ]

        due_rows = await self.repo.upcoming_due(organization_id=organization_id)
        upcoming_due_dates = [
            UpcomingDueItem(
                id=inv.id, invoice_number=inv.invoice_number, client_name=client_name,
                due_date=inv.due_date, balance_due=inv.balance_due, currency=inv.currency,
            )
            for inv, client_name in due_rows
        ]

        return DashboardOut(
            totals=totals,
            revenue_by_client=revenue_by_client,
            expense_by_category=expense_by_category,
            recent_invoices=recent_invoices,
            recent_expenses=recent_expenses,
            recent_payments=recent_payments,
            upcoming_due_dates=upcoming_due_dates,
        )
