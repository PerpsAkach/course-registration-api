from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time

import pytest
from sqlalchemy import func, select

from app import capacity as _capacity  # noqa: F401 - registers capacity guard
from app.capacity import SectionCapacityExceeded
from app.db import configure_database, new_session
from app.models import AcademicTerm, Course, Section, SectionEnrollment, Student


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")


pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL concurrency integration tests",
)


def _seed_capacity_one_section() -> tuple[int, int, int]:
    suffix = uuid.uuid4().hex[:10]
    with new_session() as session:
        first = Student(
            student_number=f"PG-{suffix}-1",
            first_name="Concurrent",
            last_name="One",
            email=f"pg-{suffix}-1@example.edu",
        )
        second = Student(
            student_number=f"PG-{suffix}-2",
            first_name="Concurrent",
            last_name="Two",
            email=f"pg-{suffix}-2@example.edu",
        )
        course = Course(
            code=f"PG{suffix[:6].upper()}",
            title="PostgreSQL Concurrency Test",
            credits=3,
            capacity=30,
        )
        term = AcademicTerm(
            name=f"PG-{suffix}",
            year=2026,
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 12, 20),
            registration_opens_on=date(2026, 8, 1),
            registration_closes_on=date(2026, 9, 15),
        )
        session.add_all([first, second, course, term])
        session.flush()
        section = Section(
            course_id=course.id,
            term_id=term.id,
            section_number="001",
            capacity=1,
            meeting_days="MW",
            starts_at=time(9, 0),
            ends_at=time(10, 15),
        )
        session.add(section)
        session.commit()
        return first.id, second.id, section.id


def _attempt_registration(student_id: int, section_id: int, barrier: threading.Barrier) -> str:
    with new_session() as session:
        session.add(SectionEnrollment(student_id=student_id, section_id=section_id))
        barrier.wait(timeout=10)
        try:
            session.commit()
            return "committed"
        except SectionCapacityExceeded:
            session.rollback()
            return "capacity_rejected"


def test_postgresql_serializes_competing_final_seat_commits():
    configure_database(POSTGRES_TEST_URL)
    first_id, second_id, section_id = _seed_capacity_one_section()
    barrier = threading.Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_attempt_registration, first_id, section_id, barrier),
            pool.submit(_attempt_registration, second_id, section_id, barrier),
        ]
        outcomes = sorted(future.result(timeout=20) for future in futures)

    assert outcomes == ["capacity_rejected", "committed"]

    with new_session() as session:
        active_count = session.scalar(
            select(func.count())
            .select_from(SectionEnrollment)
            .where(
                SectionEnrollment.section_id == section_id,
                SectionEnrollment.status == "active",
            )
        ) or 0
        assert active_count == 1
