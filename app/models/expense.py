import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class ExpenseStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    billed = "billed"
    paid = "paid"


# Status transitions considered valid by ExpenseService.update_status.
# Anything not listed here (e.g. billed -> draft) is rejected.
VALID_STATUS_TRANSITIONS: dict[ExpenseStatus, set[ExpenseStatus]] = {
    ExpenseStatus.draft: {ExpenseStatus.pending, ExpenseStatus.approved},
    ExpenseStatus.pending: {ExpenseStatus.approved, ExpenseStatus.rejected},
    ExpenseStatus.approved: {ExpenseStatus.billed, ExpenseStatus.rejected},
    ExpenseStatus.rejected: {ExpenseStatus.pending},
    ExpenseStatus.billed: {ExpenseStatus.paid},
    ExpenseStatus.paid: set(),
}


class ExpenseCategory(UUIDPKMixin, Base):
    __tablename__ = "expense_categories"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Expense(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True
    )

    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    tax: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)

    billable: Mapped[bool] = mapped_column(Boolean, default=False)
    reimbursable: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, name="expense_status"), nullable=False, default=ExpenseStatus.draft
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set once a billable expense is attached to an invoice (invoice_expenses,
    # added in the Invoices module). Kept here too as a fast "is this already
    # on an invoice" check without a join, since it's checked on every list.
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
