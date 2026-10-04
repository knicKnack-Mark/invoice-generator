from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class InvoiceItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)


class InvoiceItemOut(BaseModel):
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    sort_order: int

    model_config = {"from_attributes": True}


class InvoiceExpenseOut(BaseModel):
    id: UUID
    expense_id: UUID
    amount: Decimal

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    client_id: UUID
    invoice_date: date
    due_date: date | None = None  # defaults to invoice_date + settings.default_payment_terms_days
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = None
    terms: str | None = None
    items: list[InvoiceItemCreate] = Field(default_factory=list)
    expense_ids: list[UUID] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class InvoiceUpdate(BaseModel):
    """Only permitted while the invoice is still in draft — see
    InvoiceService.update. Line items and totals are not editable here;
    recreate the draft if the items need to change (kept simple deliberately;
    a dedicated item-patch endpoint can be added later if needed)."""
    invoice_date: date | None = None
    due_date: date | None = None
    notes: str | None = None
    terms: str | None = None


class InvoiceStatusUpdate(BaseModel):
    status: str = Field(pattern="^(sent|viewed|partially_paid|paid|cancelled)$")


class InvoiceOut(BaseModel):
    id: UUID
    client_id: UUID
    invoice_number: str
    status: str
    invoice_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    discount_total: Decimal
    total: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    is_overdue: bool
    notes: str | None
    terms: str | None
    public_token: str
    created_at: datetime
    updated_at: datetime
    items: list[InvoiceItemOut] = []
    expenses: list[InvoiceExpenseOut] = []

    model_config = {"from_attributes": True}


class PublicInvoiceOut(BaseModel):
    """Deliberately narrower than InvoiceOut — no internal notes, no
    organization-facing fields, safe to expose on an unauthenticated link."""
    invoice_number: str
    status: str
    invoice_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    discount_total: Decimal
    total: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    is_overdue: bool
    terms: str | None
    items: list[InvoiceItemOut] = []
    client_name: str
    organization_name: str
