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


def _has_token_version() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        column["name"] == "token_version"
        for column in inspector.get_columns("user_accounts")
    )


def upgrade() -> None:
    # The initial portfolio baseline is metadata-driven. On a brand-new database
    # it may already contain this newly modeled column, while a database that was
    # previously migrated to revision 0002 will not. Support both upgrade paths.
    if not _has_token_version():
        op.add_column(
            "user_accounts",
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if _has_token_version():
        op.drop_column("user_accounts", "token_version")
