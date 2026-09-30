"""invoices, invoice_items, invoice_expenses

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

invoice_status_enum = postgresql.ENUM(
    "draft", "sent", "viewed", "partially_paid", "paid", "cancelled", name="invoice_status", create_type=False
)


def upgrade() -> None:
    invoice_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("status", invoice_status_enum, nullable=False, server_default="draft"),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("terms", sa.Text, nullable=True),
        sa.Column("public_token", sa.String(64), nullable=False, unique=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_number_per_org"),
    )
    op.create_index("ix_invoices_org", "invoices", ["organization_id"])
    op.create_index("ix_invoices_org_client", "invoices", ["organization_id", "client_id"])
    op.create_index("ix_invoices_org_status", "invoices", ["organization_id", "status"])
    op.create_index("ix_invoices_public_token", "invoices", ["public_token"])

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    op.create_table(
        "invoice_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "expense_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_invoice_expenses_invoice_id", "invoice_expenses", ["invoice_id"])
    op.create_index("ix_invoice_expenses_expense_id", "invoice_expenses", ["expense_id"])


def downgrade() -> None:
    op.drop_table("invoice_expenses")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    invoice_status_enum.drop(op.get_bind(), checkfirst=True)