"""settings, time_entries, invoice_time_entries, recurring_invoices,
recurring_invoice_items, notifications

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-10

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

recurring_frequency_enum = postgresql.ENUM(
    "weekly", "monthly", "quarterly", "yearly", name="recurring_frequency", create_type=False
)


def upgrade() -> None:
    # --- settings ---
    op.create_table(
        "settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True,
        ),
        sa.Column("invoice_prefix", sa.String(20), nullable=False, server_default="INV"),
        sa.Column("logo_key", sa.String(500), nullable=True),
        sa.Column("brand_color", sa.String(20), nullable=True),
        sa.Column("footer_text", sa.Text, nullable=True),
        sa.Column("bank_info", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("reminder_schedule", postgresql.JSONB, nullable=False, server_default="{}"),
    )

    # --- time_entries (must exist before invoice_time_entries references it) ---
    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("start_time", sa.Time, nullable=True),
        sa.Column("end_time", sa.Time, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("billable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_time_entries_org", "time_entries", ["organization_id"])
    op.create_index("ix_time_entries_org_client", "time_entries", ["organization_id", "client_id"])

    # --- invoice_time_entries ---
    op.create_table(
        "invoice_time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "time_entry_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("time_entries.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_invoice_time_entries_invoice_id", "invoice_time_entries", ["invoice_id"])

    # --- recurring_invoices ---
    recurring_frequency_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "recurring_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("frequency", recurring_frequency_enum, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("payment_terms_days", sa.Integer, nullable=False, server_default="15"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("terms", sa.Text, nullable=True),
        sa.Column("next_run_date", sa.Date, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_recurring_invoices_org", "recurring_invoices", ["organization_id"])
    op.create_index(
        "ix_recurring_invoices_next_run", "recurring_invoices", ["organization_id", "is_active", "next_run_date"]
    )

    op.create_table(
        "recurring_invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recurring_invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recurring_invoices.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_recurring_invoice_items_parent", "recurring_invoice_items", ["recurring_invoice_id"])

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user", "notifications", ["organization_id", "user_id", "read_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("recurring_invoice_items")
    op.drop_table("recurring_invoices")
    recurring_frequency_enum.drop(op.get_bind(), checkfirst=True)
    op.drop_table("invoice_time_entries")
    op.drop_table("time_entries")
    op.drop_table("settings")