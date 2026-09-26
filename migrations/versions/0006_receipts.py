"""expense_receipts

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-24

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "expense_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("receipt_date", sa.Date, nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("receipt_number", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_expense_receipts_expense_id", "expense_receipts", ["expense_id"])


def downgrade() -> None:
    op.drop_table("expense_receipts")
