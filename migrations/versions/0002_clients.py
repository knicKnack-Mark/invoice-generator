"""clients

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

client_status_enum = postgresql.ENUM("active", "inactive", "archived", name="client_status", create_type=False)


def upgrade() -> None:
    client_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("tax_info", sa.String(255), nullable=True),
        sa.Column("payment_terms", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", client_status_enum, nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_clients_organization_id", "clients", ["organization_id"])
    op.create_index("ix_clients_org_status", "clients", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_table("clients")
    client_status_enum.drop(op.get_bind(), checkfirst=True)
