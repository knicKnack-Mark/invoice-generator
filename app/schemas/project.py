from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    billing_type: str = Field(default="hourly", pattern="^(hourly|fixed|retainer)$")
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    fixed_rate: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def check_dates_and_rates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.billing_type == "hourly" and self.hourly_rate is None:
            raise ValueError("hourly_rate is required when billing_type is 'hourly'")
        if self.billing_type in ("fixed", "retainer") and self.fixed_rate is None:
            raise ValueError("fixed_rate is required when billing_type is 'fixed' or 'retainer'")
        return self


class ProjectCreate(ProjectBase):
    client_id: UUID


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, pattern="^(active|on_hold|completed|cancelled)$")
    billing_type: str | None = Field(default=None, pattern="^(hourly|fixed|retainer)$")
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    fixed_rate: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class ProjectOut(BaseModel):
    id: UUID
    client_id: UUID
    name: str
    description: str | None
    start_date: date | None
    end_date: date | None
    status: str
    billing_type: str
    hourly_rate: Decimal | None
    fixed_rate: Decimal | None
    currency: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
