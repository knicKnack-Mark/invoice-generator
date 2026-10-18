import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class OrganizationSettings(UUIDPKMixin, Base):
    __tablename__ = "settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    invoice_prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="INV")
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_template: Mapped[str] = mapped_column(String(20), nullable=False, default="classic")
    logo_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_info: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reminder_schedule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)