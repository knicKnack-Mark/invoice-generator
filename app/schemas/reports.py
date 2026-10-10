from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class RevenueReportItem(BaseModel):
    client_id: UUID
    client_name: str
    total: Decimal


class RevenueReport(BaseModel):
    items: list[RevenueReportItem]
    total: Decimal


class ExpenseReportItem(BaseModel):
    category_id: UUID | None
    category_name: str
    total: Decimal


class ExpenseReport(BaseModel):
    items: list[ExpenseReportItem]
    total: Decimal


class OutstandingInvoiceItem(BaseModel):
    invoice_id: UUID
    invoice_number: str
    client_name: str
    amount: Decimal
    due_date: date
    days_overdue: int


class OutstandingInvoicesReport(BaseModel):
    items: list[OutstandingInvoiceItem]
    total_outstanding: Decimal


class ClientProfitabilityItem(BaseModel):
    client_id: UUID
    client_name: str
    revenue: Decimal
    expenses: Decimal
    net_revenue: Decimal
    hours_worked: Decimal
    effective_hourly_rate: Decimal | None
    expense_ratio: Decimal | None   # expenses / revenue, None if revenue is 0
    profit_margin: Decimal | None   # net_revenue / revenue, None if revenue is 0


class ProfitabilityReport(BaseModel):
    """Operational reporting only, not accounting or tax advice (spec section 55)."""
    items: list[ClientProfitabilityItem]