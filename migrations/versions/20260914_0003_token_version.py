"""add token revocation version

Revision ID: 20260914_0003
Revises: 20260914_0002
Create Date: 2026-09-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260914_0003"
down_revision = "20260914_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_accounts", "token_version")
