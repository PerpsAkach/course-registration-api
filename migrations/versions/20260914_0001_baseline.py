"""baseline current registration schema

Revision ID: 20260914_0001
Revises: None
Create Date: 2026-09-14
"""
from __future__ import annotations

from alembic import op

from app.db import Base
import app.models  # noqa: F401
import app.auth  # noqa: F401

revision = "20260914_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
