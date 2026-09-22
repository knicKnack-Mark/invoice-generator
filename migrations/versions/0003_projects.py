"""projects

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

project_status_enum = postgresql.ENUM(
    "active", "on_hold", "completed", "cancelled", name="project_status"
)
billing_type_enum = postgresql.ENUM("hourly", "fixed", "retainer", name="project_billing_type")


def upgrade() -> None:
    project_status_enum.create(op.get_bind(), checkfirst=True)
    billing_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "projects",
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
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("status", project_status_enum, nullable=False, server_default="active"),
        sa.Column("billing_type", billing_type_enum, nullable=False, server_default="hourly"),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("fixed_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_client_id", "projects", ["client_id"])
    op.create_index("ix_projects_org_status", "projects", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_table("projects")
    billing_type_enum.drop(op.get_bind(), checkfirst=True)
    project_status_enum.drop(op.get_bind(), checkfirst=True)
