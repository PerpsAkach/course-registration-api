from datetime import date

import pytest

from app import create_app
from app.db import Base, get_engine, new_session
from app.models import AcademicTerm, Course, Section, SectionEnrollment, Student, WaitlistEntry
from app import registration_service


@pytest.fixture()
def app():
    app = create_app("sqlite+pysqlite:///:memory:")
    app.config["TESTING"] = True
    app.config["REGISTRATION_POLICY_DATE"] = "2026-08-15"
    Base.metadata.create_all(get_engine())
    return app


def seed_drop_scenario():
    with new_session() as session:
        holder = Student(
            student_number="S-ATOMIC-1",
            first_name="Seat",
            last_name="Holder",
            email="atomic-holder@example.edu",
        )
        waiter = Student(
            student_number="S-ATOMIC-2",
            first_name="Wait",
            last_name="Candidate",
            email="atomic-waiter@example.edu",
        )
        course = Course(code="ATOMIC401", title="Atomic Registration", credits=3, capacity=10)
        term = AcademicTerm(
            name="Atomic Fall",
            year=2026,
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 12, 20),
            registration_opens_on=date(2026, 8, 1),
            registration_closes_on=date(2026, 9, 15),
        )
        session.add_all([holder, waiter, course, term])
        session.flush()
        section = Section(
            course_id=course.id,
            term_id=term.id,
            section_number="001",
            capacity=1,
            meeting_days="MW",
        )
        session.add(section)
        session.flush()
        enrollment = SectionEnrollment(student_id=holder.id, section_id=section.id)
        waiting = WaitlistEntry(student_id=waiter.id, section_id=section.id)
        session.add_all([enrollment, waiting])
        session.commit()
        return enrollment.id, section.id, waiter.id


def test_drop_rolls_back_if_promotion_workflow_fails(app, monkeypatch):
    enrollment_id, section_id, waiter_id = seed_drop_scenario()

    def fail_promotion(*_args, **_kwargs):
        raise RuntimeError("simulated promotion failure")

    monkeypatch.setattr(registration_service, "promote_next_eligible", fail_promotion)

    with new_session() as session:
        with pytest.raises(RuntimeError, match="simulated promotion failure"):
            registration_service.drop_section_and_promote(
                session,
                enrollment_id=enrollment_id,
                as_of=date(2026, 8, 15),
            )
        session.rollback()

    with new_session() as session:
        enrollment = session.get(SectionEnrollment, enrollment_id)
        assert enrollment.status == "active"
        assert enrollment.dropped_at is None

        waiting = session.scalar(
            registration_service.select(WaitlistEntry).where(
                WaitlistEntry.section_id == section_id,
                WaitlistEntry.student_id == waiter_id,
            )
        )
        assert waiting.status == "waiting"
        assert waiting.promoted_at is None


def test_policy_date_is_server_controlled(app):
    with app.app_context():
        assert registration_service.policy_date() == date(2026, 8, 15)
        app.config["REGISTRATION_POLICY_DATE"] = date(2026, 9, 1)
        assert registration_service.policy_date() == date(2026, 9, 1)
