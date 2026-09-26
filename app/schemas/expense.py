from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ExpenseCategoryOut(BaseModel):
    id: UUID
    name: str
    is_default: bool

    model_config = {"from_attributes": True}


class ExpenseBase(BaseModel):
    client_id: UUID
    project_id: UUID | None = None
    category_id: UUID | None = None
    vendor: str | None = Field(default=None, max_length=255)
    description: str | None = None
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: str | None = Field(default=None, max_length=50)
    expense_date: date
    billable: bool = False
    reimbursable: bool = False
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    project_id: UUID | None = None
    category_id: UUID | None = None
    vendor: str | None = Field(default=None, max_length=255)
    description: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    tax: Decimal | None = Field(default=None, ge=0)
    payment_method: str | None = Field(default=None, max_length=50)
    expense_date: date | None = None
    billable: bool | None = None
    reimbursable: bool | None = None
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ExpenseStatusUpdate(BaseModel):
    status: str = Field(pattern="^(draft|pending|approved|rejected|billed|paid)$")


class ExpenseOut(BaseModel):
    id: UUID
    client_id: UUID
    project_id: UUID | None
    category_id: UUID | None
    vendor: str | None
    description: str | None
    amount: Decimal
    currency: str
    tax: Decimal
    payment_method: str | None
    expense_date: date
    billable: bool
    reimbursable: bool
    status: str
    notes: str | None
    invoiced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UnbilledExpenseItem(BaseModel):
    id: UUID
    vendor: str | None
    description: str | None
    amount: Decimal
    currency: str
    expense_date: date


class UnbilledExpensesSummary(BaseModel):
    total: Decimal
    currency: str
    count: int
    items: list[UnbilledExpenseItem]
