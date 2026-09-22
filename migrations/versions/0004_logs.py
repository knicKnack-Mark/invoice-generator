"""activity_logs and audit_logs

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("log_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_activity_logs_org_created", "activity_logs", ["organization_id", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("log_metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["organization_id", "created_at"])
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])

    # Append-only enforcement: the app's runtime DB role should not be able to
    # UPDATE or DELETE audit_logs rows. If you created a dedicated app role
    # (recommended for production), run this with a superuser/owner
    # connection, substituting your actual app role name:
    #
    #   REVOKE UPDATE, DELETE ON audit_logs FROM app_role;
    #
    # This is commented out here because the Supabase default connection
    # uses the postgres superuser, which must retain full access; apply the
    # REVOKE once you provision a least-privilege application role.


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("activity_logs")
