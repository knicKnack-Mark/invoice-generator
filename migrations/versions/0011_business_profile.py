"""add organization business profile fields

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("business_name", sa.String(length=255), nullable=True))
    op.add_column("settings", sa.Column("business_address", sa.Text(), nullable=True))
    op.add_column("settings", sa.Column("business_email", sa.String(length=255), nullable=True))
    op.add_column("settings", sa.Column("business_phone", sa.String(length=50), nullable=True))
    op.add_column("settings", sa.Column("tax_id", sa.String(length=100), nullable=True))
    op.add_column(
        "settings",
        sa.Column("invoice_template", sa.String(length=20), server_default="classic", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("settings", "invoice_template")
    op.drop_column("settings", "tax_id")
    op.drop_column("settings", "business_phone")
    op.drop_column("settings", "business_email")
    op.drop_column("settings", "business_address")
    op.drop_column("settings", "business_name")
