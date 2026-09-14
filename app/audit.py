from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, g, jsonify, request
from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, new_session


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


bp = Blueprint("audit", __name__)


def _audit_json(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "request_id": event.request_id,
        "actor_user_id": event.actor_user_id,
        "method": event.method,
        "path": event.path,
        "status_code": event.status_code,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def init_audit(app) -> None:
    app.register_blueprint(bp)

    @app.before_request
    def _assign_request_id():
        supplied = request.headers.get("X-Request-ID", "").strip()
        g.request_id = supplied[:36] if supplied else str(uuid4())

    @app.after_request
    def _record_audit_event(response):
        request_id = getattr(g, "request_id", None) or str(uuid4())
        response.headers["X-Request-ID"] = request_id

        if request.method not in {"POST", "PATCH", "PUT", "DELETE"}:
            return response

        actor = getattr(g, "current_user", None)
        actor_user_id = getattr(actor, "id", None)

        try:
            with new_session() as session:
                session.add(
                    AuditEvent(
                        request_id=request_id,
                        actor_user_id=actor_user_id,
                        method=request.method,
                        path=request.path,
                        status_code=response.status_code,
                    )
                )
                session.commit()
        except Exception:
            # Auditing should not convert an already-computed API response into
            # an application failure. Operational monitoring should surface any
            # audit persistence failure in a production deployment.
            pass

        return response


@bp.get("/api/audit-events")
def list_audit_events():
    actor = getattr(g, "current_user", None)
    if actor is None:
        return jsonify({"error": "authentication_required"}), 401
    if actor.role != "admin":
        return jsonify({"error": "forbidden"}), 403

    try:
        limit = min(200, max(1, int(request.args.get("limit", 100))))
    except ValueError:
        return jsonify({"error": "invalid_limit"}), 400

    with new_session() as session:
        rows = list(
            session.scalars(
                select(AuditEvent)
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                .limit(limit)
            )
        )
        return jsonify({"items": [_audit_json(row) for row in rows]})
