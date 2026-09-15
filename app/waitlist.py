from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from .db import new_session
from .models import WaitlistEntry
from .registration_service import (
    RegistrationError,
    cancel_waitlist as cancel_waitlist_entry,
    join_waitlist as join_waitlist_entry,
    policy_date,
)

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


def init_waitlist(app) -> None:
    app.register_blueprint(bp)


@bp.post("/api/waitlists")
def join_waitlist():
    data = request.get_json(force=True)
    try:
        student_id = int(data["student_id"])
        section_id = int(data["section_id"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "invalid_waitlist_request"}), 400

    with new_session() as session:
        try:
            entry = join_waitlist_entry(
                session,
                student_id=student_id,
                section_id=section_id,
                as_of=policy_date(),
            )
            session.commit()
        except RegistrationError as exc:
            session.rollback()
            return jsonify(exc.payload()), exc.status_code
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
        try:
            entry = cancel_waitlist_entry(session, entry_id=entry_id)
            session.commit()
        except RegistrationError as exc:
            session.rollback()
            return jsonify(exc.payload()), exc.status_code
        return jsonify(_waitlist_json(entry))
