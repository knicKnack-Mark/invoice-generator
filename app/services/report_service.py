import csv
import io
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.expense_repository import ExpenseRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.reports import (
    ClientProfitabilityItem,
    ExpenseReport,
    ExpenseReportItem,
    OutstandingInvoiceItem,
    OutstandingInvoicesReport,
    ProfitabilityReport,
    RevenueReport,
    RevenueReportItem,
)


def _csv_safe(value) -> str:
    """Guards against CSV/formula injection. Vendor and description are
    user-entered text; if one starts with = + - or @, Excel/Sheets can treat
    it as a formula when the export is opened. A leading apostrophe forces it
    to be read as plain text."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ReportRepository(db)

    async def revenue_report(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> RevenueReport:
        rows = await self.repo.revenue_by_client(
            organization_id=organization_id, date_from=date_from, date_to=date_to
        )
        items = [RevenueReportItem(client_id=cid, client_name=name, total=total) for cid, name, total in rows]
        return RevenueReport(items=items, total=sum((i.total for i in items), Decimal("0")))

    async def expense_report(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> ExpenseReport:
        rows = await self.repo.expenses_by_category(
            organization_id=organization_id, date_from=date_from, date_to=date_to
        )
        items = [ExpenseReportItem(category_id=cid, category_name=name, total=total) for cid, name, total in rows]
        return ExpenseReport(items=items, total=sum((i.total for i in items), Decimal("0")))

    async def outstanding_invoices_report(self, *, organization_id: UUID) -> OutstandingInvoicesReport:
        rows = await self.repo.outstanding_invoices(organization_id=organization_id)
        today = date.today()
        items = [
            OutstandingInvoiceItem(
                invoice_id=inv.id,
                invoice_number=inv.invoice_number,
                client_name=client_name,
                amount=inv.balance_due,
                due_date=inv.due_date,
                days_overdue=max(0, (today - inv.due_date).days),
            )
            for inv, client_name in rows
        ]
        return OutstandingInvoicesReport(
            items=items, total_outstanding=sum((i.amount for i in items), Decimal("0"))
        )

    async def profitability_report(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> ProfitabilityReport:
        rows = await self.repo.client_profitability(
            organization_id=organization_id, date_from=date_from, date_to=date_to
        )
        items = []
        for row in rows:
            revenue, expenses, hours = row["revenue"], row["expenses"], row["hours"]
            net_revenue = revenue - expenses
            items.append(ClientProfitabilityItem(
                client_id=row["client_id"],
                client_name=row["client_name"],
                revenue=revenue,
                expenses=expenses,
                net_revenue=net_revenue,
                hours_worked=hours,
                effective_hourly_rate=(revenue / hours) if hours > 0 else None,
                expense_ratio=(expenses / revenue) if revenue > 0 else None,
                profit_margin=(net_revenue / revenue) if revenue > 0 else None,
            ))
        return ProfitabilityReport(items=items)

    async def export_expenses_csv(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> str:
        expenses, _total = await ExpenseRepository(self.db).list(
            organization_id=organization_id, page=1, page_size=10_000, date_from=date_from, date_to=date_to
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Date", "Vendor", "Description", "Amount", "Tax", "Currency", "Billable", "Status"])
        for e in expenses:
            writer.writerow([
                e.expense_date, _csv_safe(e.vendor), _csv_safe(e.description),
                e.amount, e.tax, e.currency, e.billable, e.status.value,
            ])
        return buffer.getvalue()

    async def export_invoices_csv(
        self, *, organization_id: UUID, date_from: date | None, date_to: date | None
    ) -> str:
        invoices, _total = await InvoiceRepository(self.db).list(
            organization_id=organization_id, page=1, page_size=10_000, date_from=date_from, date_to=date_to
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Invoice Number", "Date", "Due Date", "Status", "Total", "Paid", "Balance", "Currency"])
        for inv in invoices:
            writer.writerow([
                inv.invoice_number, inv.invoice_date, inv.due_date, inv.status.value,
                inv.total, inv.amount_paid, inv.balance_due, inv.currency,
            ])
        return buffer.getvalue()

    async def export_payments_csv(self, *, organization_id: UUID) -> str:
        payments, _total = await PaymentRepository(self.db).list(
            organization_id=organization_id, page=1, page_size=10_000
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Date", "Invoice ID", "Amount", "Currency", "Method", "Reference"])
        for p in payments:
            writer.writerow([
                p.payment_date, p.invoice_id, p.amount, p.currency, p.payment_method, _csv_safe(p.reference_number),
            ])
        return buffer.getvalue()