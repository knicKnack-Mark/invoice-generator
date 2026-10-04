from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class DashboardTotals(BaseModel):
    total_revenue: Decimal          # sum of amount_paid across all invoices (lifetime)
    outstanding_invoices: Decimal   # sum of balance_due on sent/viewed/partially_paid invoices
    overdue_invoices: Decimal       # sum of balance_due on invoices past due_date
    expenses_this_month: Decimal    # sum of (amount+tax) for expenses dated this month
    billable_expenses: Decimal      # sum of (amount+tax) for billable expenses this month
    unbilled_expenses: Decimal      # sum of (amount+tax) for billable expenses not yet invoiced (any date)
    paid_invoices_count: int
    pending_invoices_count: int     # draft/sent/viewed/partially_paid, not overdue


class RevenueByClientItem(BaseModel):
    client_id: UUID
    client_name: str
    total: Decimal


class ExpenseByCategoryItem(BaseModel):
    category_id: UUID | None
    category_name: str
    total: Decimal


class RecentInvoiceItem(BaseModel):
    id: UUID
    invoice_number: str
    client_name: str
    status: str
    total: Decimal
    currency: str
    invoice_date: date


class RecentExpenseItem(BaseModel):
    id: UUID
    vendor: str | None
    amount: Decimal
    currency: str
    expense_date: date
    billable: bool


class RecentPaymentItem(BaseModel):
    id: UUID
    invoice_id: UUID
    invoice_number: str
    amount: Decimal
    currency: str
    payment_date: date


class UpcomingDueItem(BaseModel):
    id: UUID
    invoice_number: str
    client_name: str
    due_date: date
    balance_due: Decimal
    currency: str


class DashboardOut(BaseModel):
    totals: DashboardTotals
    revenue_by_client: list[RevenueByClientItem]
    expense_by_category: list[ExpenseByCategoryItem]
    recent_invoices: list[RecentInvoiceItem]
    recent_expenses: list[RecentExpenseItem]
    recent_payments: list[RecentPaymentItem]
    upcoming_due_dates: list[UpcomingDueItem]
