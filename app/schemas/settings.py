from uuid import UUID

from pydantic import BaseModel, Field


class BankInfo(BaseModel):
    bank_name: str | None = None
    account_name: str | None = None
    account_number: str | None = None
    routing_or_swift: str | None = None


class SettingsUpdate(BaseModel):
    invoice_prefix: str | None = Field(default=None, min_length=1, max_length=20)
    brand_color: str | None = Field(default=None, max_length=20)
    footer_text: str | None = None
    bank_info: BankInfo | None = None


class SettingsOut(BaseModel):
    id: UUID
    organization_id: UUID
    invoice_prefix: str
    logo_key: str | None
    brand_color: str | None
    footer_text: str | None
    bank_info: dict
    reminder_schedule: dict

    model_config = {"from_attributes": True}