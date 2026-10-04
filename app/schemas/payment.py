from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Matches spec section 23. "Other" catches anything not listed; a free-text
# payment_method beyond this set is rejected rather than silently accepted,
# to keep reporting consistent.
PAYMENT_METHODS = ("Bank Transfer", "PayPal", "Wise", "Stripe", "Cash", "GCash", "Other")


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_date: date
    payment_method: str
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("payment_method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of {PAYMENT_METHODS}")
        return v


class PaymentOut(BaseModel):
    id: UUID
    invoice_id: UUID
    amount: Decimal
    currency: str
    payment_date: date
    payment_method: str
    reference_number: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
