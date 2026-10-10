from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RecurringInvoiceItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0)


class RecurringInvoiceItemOut(BaseModel):
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal

    model_config = {"from_attributes": True}


class RecurringInvoiceCreate(BaseModel):
    client_id: UUID
    frequency: str = Field(pattern="^(weekly|monthly|quarterly|yearly)$")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_terms_days: int = Field(default=15, ge=0)
    notes: str | None = None
    terms: str | None = None
    start_date: date
    items: list[RecurringInvoiceItemCreate] = Field(min_length=1)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class RecurringInvoiceUpdate(BaseModel):
    frequency: str | None = Field(default=None, pattern="^(weekly|monthly|quarterly|yearly)$")
    notes: str | None = None
    terms: str | None = None
    is_active: bool | None = None


class RecurringInvoiceOut(BaseModel):
    id: UUID
    client_id: UUID
    frequency: str
    currency: str
    payment_terms_days: int
    notes: str | None
    terms: str | None
    next_run_date: date
    is_active: bool
    created_at: datetime
    items: list[RecurringInvoiceItemOut] = []

    model_config = {"from_attributes": True}