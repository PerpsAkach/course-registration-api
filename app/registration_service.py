from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import CourseCompletion, Prerequisite, Section, SectionEnrollment, Student


@dataclass(frozen=True)
class RegistrationError(Exception):
    """Domain error returned by the section-registration service."""

    code: str
    status_code: int = 409
    details: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.code}
        if self.details:
            payload.update(self.details)
        return payload


def policy_date() -> date:
    """Return the server-controlled registration policy date.

    Tests may set ``REGISTRATION_POLICY_DATE`` to an ISO date or a callable
    returning ``date``. Production requests never trust a client supplied
    ``as_of`` value for registration-window decisions.
    """
    override = current_app.config.get("REGISTRATION_POLICY_DATE")
    if callable(override):
        value = override()
        if not isinstance(value, date):
            raise RuntimeError("REGISTRATION_POLICY_DATE callable must return date")
        return value
    if isinstance(override, date):
        return override
    if isinstance(override, str) and override:
        return date.fromisoformat(override)
    return date.today()


def meeting_days(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = value.upper().replace(" ", "")
    tokens: list[str] = []
    i = 0
    while i < len(normalized):
        if normalized.startswith("TH", i):
            tokens.append("TH")
            i += 2
        elif normalized.startswith("TU", i):
            tokens.append("TU")
            i += 2
        elif normalized.startswith("SA", i):
            tokens.append("SA")
            i += 2
        elif normalized.startswith("SU", i):
            tokens.append("SU")
            i += 2
        else:
            tokens.append(normalized[i])
            i += 1
    aliases = {"T": "TU", "R": "TH", "M": "M", "W": "W", "F": "F"}
    return {aliases.get(token, token) for token in tokens}


def sections_conflict(first: Section, second: Section) -> bool:
    if first.term_id != second.term_id:
        return False
    if not first.starts_at or not first.ends_at or not second.starts_at or not second.ends_at:
        return False
    if not (meeting_days(first.meeting_days) & meeting_days(second.meeting_days)):
        return False
    return first.starts_at < second.ends_at and second.starts_at < first.ends_at


def active_section_count(session: Session, section_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(SectionEnrollment)
        .where(
            SectionEnrollment.section_id == section_id,
            SectionEnrollment.status == "active",
        )
    ) or 0


def eligibility_error(
    session: Session,
    student_id: int,
    section: Section,
    *,
    as_of: date,
    check_window: bool = True,
    check_capacity: bool = False,
) -> RegistrationError | None:
    """Evaluate shared registration rules without mutating state."""
    if check_window:
        term = section.term
        if as_of < term.registration_opens_on or as_of > term.registration_closes_on:
            return RegistrationError("registration_closed")

    required_ids = set(session.scalars(
        select(Prerequisite.required_course_id).where(Prerequisite.course_id == section.course_id)
    ))
    completed_ids = set(session.scalars(
        select(CourseCompletion.course_id).where(CourseCompletion.student_id == student_id)
    ))
    missing = sorted(required_ids - completed_ids)
    if missing:
        return RegistrationError("prerequisites_not_met", details={"missing_course_ids": missing})

    active_for_term = list(session.scalars(
        select(SectionEnrollment)
        .join(Section, Section.id == SectionEnrollment.section_id)
        .where(
            SectionEnrollment.student_id == student_id,
            SectionEnrollment.status == "active",
            Section.term_id == section.term_id,
        )
    ))
    for current in active_for_term:
        current_section = current.section
        if current_section.course_id == section.course_id:
            return RegistrationError("already_registered_for_course")
        if sections_conflict(current_section, section):
            return RegistrationError(
                "schedule_conflict",
                details={"conflicting_section_id": current_section.id},
            )

    if check_capacity and active_section_count(session, section.id) >= section.capacity:
        return RegistrationError("section_full")

    return None


def register_for_section(
    session: Session,
    *,
    student_id: int,
    section_id: int,
    as_of: date,
) -> SectionEnrollment:
    """Register or reactivate one student in a section.

    The caller owns commit/rollback. The SQLAlchemy capacity guard remains the
    final transactional protection against concurrent over-allocation.
    """
    student = session.get(Student, student_id)
    section = session.get(Section, section_id)
    if student is None or section is None:
        raise RegistrationError("student_or_section_not_found", status_code=404)

    existing = session.scalar(select(SectionEnrollment).where(
        SectionEnrollment.student_id == student_id,
        SectionEnrollment.section_id == section_id,
    ))
    if existing and existing.status == "active":
        raise RegistrationError("already_enrolled")

    error = eligibility_error(
        session,
        student_id,
        section,
        as_of=as_of,
        check_window=True,
        check_capacity=True,
    )
    if error:
        raise error

    now = datetime.now(timezone.utc)
    if existing:
        existing.status = "active"
        existing.dropped_at = None
        existing.enrolled_at = now
        enrollment = existing
    else:
        enrollment = SectionEnrollment(student_id=student_id, section_id=section_id)
        session.add(enrollment)

    # Flush here so transactional capacity protection fails inside the service
    # boundary rather than after the route has built a success response.
    session.flush()
    return enrollment


def drop_section(session: Session, *, enrollment_id: int) -> SectionEnrollment:
    enrollment = session.get(SectionEnrollment, enrollment_id)
    if enrollment is None:
        raise RegistrationError("section_enrollment_not_found", status_code=404)
    if enrollment.status == "dropped":
        raise RegistrationError("already_dropped")

    enrollment.status = "dropped"
    enrollment.dropped_at = datetime.now(timezone.utc)
    session.flush()
    return enrollment
