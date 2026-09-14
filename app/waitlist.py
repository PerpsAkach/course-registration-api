from __future__ import annotations

from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from .db import new_session
from .models import CourseCompletion, Prerequisite, Section, SectionEnrollment, Student, WaitlistEntry

bp = Blueprint("waitlist", __name__)


def _waitlist_json(entry: WaitlistEntry) -> dict:
    return {
        "id": entry.id,
        "student_id": entry.student_id,
        "section_id": entry.section_id,
        "status": entry.status,
        "joined_at": entry.joined_at.isoformat() if entry.joined_at else None,
        "promoted_at": entry.promoted_at.isoformat() if entry.promoted_at else None,
        "cancelled_at": entry.cancelled_at.isoformat() if entry.cancelled_at else None,
    }


def _meeting_days(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = value.upper().replace(" ", "")
    tokens = []
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


def _sections_conflict(first: Section, second: Section) -> bool:
    if first.term_id != second.term_id:
        return False
    if not first.starts_at or not first.ends_at or not second.starts_at or not second.ends_at:
        return False
    if not (_meeting_days(first.meeting_days) & _meeting_days(second.meeting_days)):
        return False
    return first.starts_at < second.ends_at and second.starts_at < first.ends_at


def _is_eligible(session, student_id: int, section: Section) -> tuple[bool, str | None]:
    required_ids = set(session.scalars(
        select(Prerequisite.required_course_id).where(Prerequisite.course_id == section.course_id)
    ))
    completed_ids = set(session.scalars(
        select(CourseCompletion.course_id).where(CourseCompletion.student_id == student_id)
    ))
    if required_ids - completed_ids:
        return False, "prerequisites_not_met"

    active_for_term = list(session.scalars(
        select(SectionEnrollment)
        .join(Section, Section.id == SectionEnrollment.section_id)
        .where(
            SectionEnrollment.student_id == student_id,
            SectionEnrollment.status == "active",
            Section.term_id == section.term_id,
        )
    ))
    for enrollment in active_for_term:
        current = enrollment.section
        if current.course_id == section.course_id:
            return False, "already_registered_for_course"
        if _sections_conflict(current, section):
            return False, "schedule_conflict"
    return True, None


def promote_next_eligible(session, section_id: int) -> WaitlistEntry | None:
    section = session.get(Section, section_id)
    if section is None:
        return None

    active_count = session.scalar(
        select(func.count()).select_from(SectionEnrollment).where(
            SectionEnrollment.section_id == section_id,
            SectionEnrollment.status == "active",
        )
    ) or 0
    if active_count >= section.capacity:
        return None

    entries = list(session.scalars(
        select(WaitlistEntry)
        .where(WaitlistEntry.section_id == section_id, WaitlistEntry.status == "waiting")
        .order_by(WaitlistEntry.joined_at, WaitlistEntry.id)
    ))
    for entry in entries:
        eligible, _ = _is_eligible(session, entry.student_id, section)
        if not eligible:
            continue
        enrollment = session.scalar(select(SectionEnrollment).where(
            SectionEnrollment.student_id == entry.student_id,
            SectionEnrollment.section_id == section_id,
        ))
        if enrollment:
            enrollment.status = "active"
            enrollment.dropped_at = None
            enrollment.enrolled_at = datetime.now(timezone.utc)
        else:
            session.add(SectionEnrollment(student_id=entry.student_id, section_id=section_id))
        entry.status = "promoted"
        entry.promoted_at = datetime.now(timezone.utc)
        return entry
    return None


def init_waitlist(app) -> None:
    app.register_blueprint(bp)

    @app.after_request
    def _promote_after_section_drop(response):
        if request.method != "DELETE" or not request.path.startswith("/api/section-enrollments/") or response.status_code != 200:
            return response
        payload = response.get_json(silent=True) or {}
        section_id = payload.get("section_id")
        if section_id is None:
            return response
        with new_session() as session:
            promoted = promote_next_eligible(session, int(section_id))
            if promoted is not None:
                session.commit()
        return response


@bp.post("/api/waitlists")
def join_waitlist():
    data = request.get_json(force=True)
    try:
        student_id = int(data["student_id"])
        section_id = int(data["section_id"])
        as_of = date.fromisoformat(str(data.get("as_of", date.today().isoformat())))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "invalid_waitlist_request"}), 400

    with new_session() as session:
        student = session.get(Student, student_id)
        section = session.get(Section, section_id)
        if student is None or section is None:
            return jsonify({"error": "student_or_section_not_found"}), 404
        if as_of < section.term.registration_opens_on or as_of > section.term.registration_closes_on:
            return jsonify({"error": "registration_closed"}), 409

        active = session.scalar(select(SectionEnrollment).where(
            SectionEnrollment.student_id == student_id,
            SectionEnrollment.section_id == section_id,
            SectionEnrollment.status == "active",
        ))
        if active:
            return jsonify({"error": "already_enrolled"}), 409

        eligible, error = _is_eligible(session, student_id, section)
        if not eligible:
            return jsonify({"error": error}), 409

        existing = session.scalar(select(WaitlistEntry).where(
            WaitlistEntry.student_id == student_id,
            WaitlistEntry.section_id == section_id,
        ))
        if existing and existing.status == "waiting":
            return jsonify({"error": "already_waitlisted"}), 409

        active_count = session.scalar(select(func.count()).select_from(SectionEnrollment).where(
            SectionEnrollment.section_id == section_id,
            SectionEnrollment.status == "active",
        )) or 0
        if active_count < section.capacity:
            return jsonify({"error": "section_has_available_seats"}), 409

        if existing:
            existing.status = "waiting"
            existing.joined_at = datetime.now(timezone.utc)
            existing.promoted_at = None
            existing.cancelled_at = None
            entry = existing
        else:
            entry = WaitlistEntry(student_id=student_id, section_id=section_id)
            session.add(entry)
        session.commit()
        return jsonify(_waitlist_json(entry)), 201


@bp.get("/api/waitlists")
def list_waitlist():
    query = select(WaitlistEntry)
    status = request.args.get("status")
    if status:
        if status not in {"waiting", "promoted", "cancelled"}:
            return jsonify({"error": "invalid_status"}), 400
        query = query.where(WaitlistEntry.status == status)
    for arg, column in (("student_id", WaitlistEntry.student_id), ("section_id", WaitlistEntry.section_id)):
        value = request.args.get(arg)
        if value is not None:
            try:
                query = query.where(column == int(value))
            except ValueError:
                return jsonify({"error": f"invalid_{arg}"}), 400

    with new_session() as session:
        rows = list(session.scalars(query.order_by(WaitlistEntry.joined_at, WaitlistEntry.id)))
        return jsonify({"items": [_waitlist_json(row) for row in rows]})


@bp.delete("/api/waitlists/<int:entry_id>")
def cancel_waitlist(entry_id: int):
    with new_session() as session:
        entry = session.get(WaitlistEntry, entry_id)
        if entry is None:
            return jsonify({"error": "waitlist_entry_not_found"}), 404
        if entry.status != "waiting":
            return jsonify({"error": "waitlist_entry_not_waiting"}), 409
        entry.status = "cancelled"
        entry.cancelled_at = datetime.now(timezone.utc)
        session.commit()
        return jsonify(_waitlist_json(entry))
