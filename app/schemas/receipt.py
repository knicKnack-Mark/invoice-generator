from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ReceiptMetadataUpdate(BaseModel):
    """Fields the user can correct after upload (manually, or after reviewing
    OCR-extracted values in a future phase)."""
    vendor: str | None = Field(default=None, max_length=255)
    receipt_date: date | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    tax: Decimal | None = Field(default=None, ge=0)
    receipt_number: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ReceiptOut(BaseModel):
    id: UUID
    expense_id: UUID
    file_name: str
    mime_type: str
    size_bytes: int
    vendor: str | None
    receipt_date: date | None
    amount: Decimal | None
    tax: Decimal | None
    receipt_number: str | None
    currency: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}
