"""baseline current registration schema

Revision ID: 20260914_0001
Revises: None
Create Date: 2026-09-14
"""
from __future__ import annotations

from alembic import op

from app.db import Base
import app.models  # noqa: F401 - registers baseline domain tables
import app.auth  # noqa: F401 - registers baseline user_accounts table

revision = "20260914_0001"
down_revision = None
branch_labels = None
depends_on = None

BASELINE_TABLE_NAMES = (
    "students",
    "courses",
    "academic_terms",
    "sections",
    "prerequisites",
    "course_completions",
    "section_enrollments",
    "waitlist_entries",
    "enrollments",
    "user_accounts",
)


def _baseline_tables():
    return [Base.metadata.tables[name] for name in BASELINE_TABLE_NAMES]


def upgrade() -> None:
    # Keep the baseline revision stable as new models are added later. New
    # tables belong in later revisions rather than being pulled implicitly from
    # the current global metadata.
    Base.metadata.create_all(bind=op.get_bind(), tables=_baseline_tables())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), tables=_baseline_tables())
