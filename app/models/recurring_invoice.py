import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class RecurringFrequency(str, enum.Enum):
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class RecurringInvoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "recurring_invoices"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    frequency: Mapped[RecurringFrequency] = mapped_column(
        Enum(RecurringFrequency, name="recurring_frequency"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_run_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    items: Mapped[list["RecurringInvoiceItem"]] = relationship(
        back_populates="recurring_invoice", cascade="all, delete-orphan"
    )


class RecurringInvoiceItem(UUIDPKMixin, Base):
    __tablename__ = "recurring_invoice_items"

    recurring_invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("recurring_invoices.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    recurring_invoice: Mapped["RecurringInvoice"] = relationship(back_populates="items")