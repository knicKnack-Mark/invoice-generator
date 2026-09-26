"""expense_categories and expenses

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-23

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

expense_status_enum = postgresql.ENUM(
    "draft", "pending", "approved", "rejected", "billed", "paid", name="expense_status", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "expense_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_expense_categories_org", "expense_categories", ["organization_id"])

    expense_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("expense_date", sa.Date, nullable=False),
        sa.Column("billable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("reimbursable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", expense_status_enum, nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_expenses_org", "expenses", ["organization_id"])
    op.create_index("ix_expenses_org_client", "expenses", ["organization_id", "client_id"])
    op.create_index("ix_expenses_org_status", "expenses", ["organization_id", "status"])
    op.create_index("ix_expenses_org_billable_invoiced", "expenses", ["organization_id", "billable", "invoiced_at"])


def downgrade() -> None:
    op.drop_table("expenses")
    expense_status_enum.drop(op.get_bind(), checkfirst=True)
    op.drop_table("expense_categories")