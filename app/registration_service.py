from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from flask import current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import new_session
from .models import (
    CourseCompletion,
    Prerequisite,
    Section,
    SectionEnrollment,
    Student,
    WaitlistEntry,
)


@dataclass(frozen=True)
class RegistrationError(Exception):
    """Domain error returned by registration/waitlist services."""

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

    Tests may set ``REGISTRATION_POLICY_DATE`` to an ISO date, a ``date``, or a
    callable returning ``date``. Production policy never trusts a client
    supplied date for registration-window decisions.
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
    """Evaluate shared registration policy without mutating state."""
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

    session.flush()
    return enrollment


def join_waitlist(
    session: Session,
    *,
    student_id: int,
    section_id: int,
    as_of: date,
) -> WaitlistEntry:
    student = session.get(Student, student_id)
    section = session.get(Section, section_id)
    if student is None or section is None:
        raise RegistrationError("student_or_section_not_found", status_code=404)

    active = session.scalar(select(SectionEnrollment).where(
        SectionEnrollment.student_id == student_id,
        SectionEnrollment.section_id == section_id,
        SectionEnrollment.status == "active",
    ))
    if active:
        raise RegistrationError("already_enrolled")

    error = eligibility_error(
        session,
        student_id,
        section,
        as_of=as_of,
        check_window=True,
        check_capacity=False,
    )
    if error:
        raise error

    existing = session.scalar(select(WaitlistEntry).where(
        WaitlistEntry.student_id == student_id,
        WaitlistEntry.section_id == section_id,
    ))
    if existing and existing.status == "waiting":
        raise RegistrationError("already_waitlisted")

    if active_section_count(session, section_id) < section.capacity:
        raise RegistrationError("section_has_available_seats")

    now = datetime.now(timezone.utc)
    if existing:
        existing.status = "waiting"
        existing.joined_at = now
        existing.promoted_at = None
        existing.cancelled_at = None
        entry = existing
    else:
        entry = WaitlistEntry(student_id=student_id, section_id=section_id)
        session.add(entry)

    session.flush()
    return entry


def cancel_waitlist(session: Session, *, entry_id: int) -> WaitlistEntry:
    entry = session.get(WaitlistEntry, entry_id)
    if entry is None:
        raise RegistrationError("waitlist_entry_not_found", status_code=404)
    if entry.status != "waiting":
        raise RegistrationError("waitlist_entry_not_waiting")

    entry.status = "cancelled"
    entry.cancelled_at = datetime.now(timezone.utc)
    session.flush()
    return entry


def promote_next_eligible(
    session: Session,
    *,
    section_id: int,
    as_of: date,
) -> WaitlistEntry | None:
    section = session.get(Section, section_id)
    if section is None or active_section_count(session, section_id) >= section.capacity:
        return None

    entries = list(session.scalars(
        select(WaitlistEntry)
        .where(WaitlistEntry.section_id == section_id, WaitlistEntry.status == "waiting")
        .order_by(WaitlistEntry.joined_at, WaitlistEntry.id)
    ))
    for entry in entries:
        error = eligibility_error(
            session,
            entry.student_id,
            section,
            as_of=as_of,
            check_window=True,
            check_capacity=False,
        )
        if error:
            continue

        enrollment = session.scalar(select(SectionEnrollment).where(
            SectionEnrollment.student_id == entry.student_id,
            SectionEnrollment.section_id == section_id,
        ))
        now = datetime.now(timezone.utc)
        if enrollment:
            enrollment.status = "active"
            enrollment.dropped_at = None
            enrollment.enrolled_at = now
        else:
            session.add(SectionEnrollment(student_id=entry.student_id, section_id=section_id))

        entry.status = "promoted"
        entry.promoted_at = now
        session.flush()
        return entry

    return None


def drop_section_and_promote(
    session: Session,
    *,
    enrollment_id: int,
    as_of: date,
) -> tuple[SectionEnrollment, WaitlistEntry | None]:
    enrollment = session.get(SectionEnrollment, enrollment_id)
    if enrollment is None:
        raise RegistrationError("section_enrollment_not_found", status_code=404)
    if enrollment.status == "dropped":
        raise RegistrationError("already_dropped")

    section_id = enrollment.section_id
    enrollment.status = "dropped"
    enrollment.dropped_at = datetime.now(timezone.utc)

    # Materialize the seat release before evaluating the waitlist, but keep the
    # transaction open. Flush is not a commit, so the drop and any promotion
    # still succeed or roll back as one database transaction.
    session.flush()
    promoted = promote_next_eligible(session, section_id=section_id, as_of=as_of)
    session.flush()
    return enrollment, promoted


def _enrollment_json(enrollment: SectionEnrollment) -> dict[str, Any]:
    return {
        "id": enrollment.id,
        "student_id": enrollment.student_id,
        "section_id": enrollment.section_id,
        "status": enrollment.status,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "dropped_at": enrollment.dropped_at.isoformat() if enrollment.dropped_at else None,
    }


def install_registration_service(app) -> None:
    """Replace legacy section mutation handlers with thin service adapters.

    Existing URL rules and endpoint names are preserved, so this can be
    installed on the reconstructed core app without duplicating routes.
    """
    if app.extensions.get("registration_service_installed"):
        return

    if "create_section_enrollment" not in app.view_functions or "drop_section_enrollment" not in app.view_functions:
        raise RuntimeError("core section-enrollment routes must be registered before service installation")

    def create_section_enrollment_service():
        data = request.get_json(force=True)
        try:
            student_id = int(data["student_id"])
            section_id = int(data["section_id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid_section_enrollment"}), 400

        with new_session() as session:
            try:
                enrollment = register_for_section(
                    session,
                    student_id=student_id,
                    section_id=section_id,
                    as_of=policy_date(),
                )
                session.commit()
            except RegistrationError as exc:
                session.rollback()
                return jsonify(exc.payload()), exc.status_code
            return jsonify(_enrollment_json(enrollment)), 201

    def drop_section_enrollment_service(enrollment_id: int):
        with new_session() as session:
            try:
                enrollment, promoted = drop_section_and_promote(
                    session,
                    enrollment_id=enrollment_id,
                    as_of=policy_date(),
                )
                payload = _enrollment_json(enrollment)
                if promoted is not None:
                    payload["promoted_waitlist_entry_id"] = promoted.id
                    payload["promoted_student_id"] = promoted.student_id
                session.commit()
            except RegistrationError as exc:
                session.rollback()
                return jsonify(exc.payload()), exc.status_code
            return jsonify(payload)

    app.view_functions["create_section_enrollment"] = create_section_enrollment_service
    app.view_functions["drop_section_enrollment"] = drop_section_enrollment_service
    app.extensions["registration_service_installed"] = True
