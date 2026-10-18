from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class BankInfo(BaseModel):
    bank_name: str | None = None
    account_name: str | None = None
    account_number: str | None = None
    routing_or_swift: str | None = None


class SettingsUpdate(BaseModel):
    invoice_prefix: str | None = Field(default=None, min_length=1, max_length=20)
    business_name: str | None = Field(default=None, max_length=255)
    business_address: str | None = Field(default=None, max_length=4000)
    business_email: EmailStr | None = None
    business_phone: str | None = Field(default=None, max_length=50)
    tax_id: str | None = Field(default=None, max_length=100)
    invoice_template: Literal["classic", "modern", "minimal"] | None = None
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    footer_text: str | None = None
    bank_info: BankInfo | None = None

    @field_validator("business_email", mode="before")
    @classmethod
    def allow_empty_business_email(cls, value: str | None) -> str | None:
        return None if value == "" else value


class SettingsOut(BaseModel):
    id: UUID
    organization_id: UUID
    invoice_prefix: str
    business_name: str | None
    business_address: str | None
    business_email: str | None
    business_phone: str | None
    tax_id: str | None
    invoice_template: str
    logo_key: str | None
    brand_color: str | None
    footer_text: str | None
    bank_info: dict
    reminder_schedule: dict

    model_config = {"from_attributes": True}