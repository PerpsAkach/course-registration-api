from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from .db import Base, new_session

TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60
bp = Blueprint("auth", __name__)


class UserAccount(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'registrar', 'admin')", name="ck_user_role"),
        UniqueConstraint("student_id", name="uq_user_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


def user_json(user: UserAccount) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "student_id": user.student_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _secret_key() -> str:
    return current_app.config["SECRET_KEY"]


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt="course-registration-api-auth")


def issue_token(user: UserAccount) -> str:
    return _serializer().dumps({"user_id": user.id, "role": user.role})


def authenticate_request() -> UserAccount | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        user_id = int(payload["user_id"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None

    with new_session() as session:
        user = session.get(UserAccount, user_id)
        if user is None or not user.is_active:
            return None
        session.expunge(user)
        return user


def _student_owns_target(user: UserAccount) -> bool:
    if user.student_id is None:
        return False

    path = request.path
    method = request.method

    if method == "GET" and (
        path == "/api/courses"
        or path.startswith("/api/courses/")
        or path == "/api/terms"
        or path.startswith("/api/terms/")
        or path == "/api/sections"
        or path.startswith("/api/sections/")
    ):
        return True

    student_match = re.fullmatch(r"/api/students/(\d+)(?:/(?:courses|completions))?", path)
    if method == "GET" and student_match:
        return int(student_match.group(1)) == user.student_id

    if method == "GET" and path in {"/api/section-enrollments", "/api/waitlists"}:
        try:
            return int(request.args.get("student_id", "")) == user.student_id
        except ValueError:
            return False

    if method == "POST" and path in {"/api/section-enrollments", "/api/waitlists"}:
        data = request.get_json(silent=True) or {}
        try:
            return int(data.get("student_id")) == user.student_id
        except (TypeError, ValueError):
            return False

    if method == "DELETE" and path.startswith("/api/section-enrollments/"):
        from .models import SectionEnrollment

        try:
            enrollment_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            return False
        with new_session() as session:
            enrollment = session.get(SectionEnrollment, enrollment_id)
            return enrollment is not None and enrollment.student_id == user.student_id

    if method == "DELETE" and path.startswith("/api/waitlists/"):
        from .models import WaitlistEntry

        try:
            entry_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            return False
        with new_session() as session:
            entry = session.get(WaitlistEntry, entry_id)
            return entry is not None and entry.student_id == user.student_id

    return False


def init_auth(app, *, required: bool | None = None) -> None:
    if required is None:
        required = os.getenv("AUTH_REQUIRED", "1").lower() not in {"0", "false", "no"}
    app.config["AUTH_REQUIRED"] = required
    app.config.setdefault("SECRET_KEY", os.getenv("APP_SECRET_KEY", "development-only-change-me"))
    app.register_blueprint(bp)

    @app.before_request
    def _authorize_request():
        if not app.config["AUTH_REQUIRED"]:
            return None
        if not request.path.startswith("/api/"):
            return None
        if request.path in {"/api/health", "/api/auth/bootstrap", "/api/auth/login"}:
            return None

        user = authenticate_request()
        if user is None:
            return jsonify({"error": "authentication_required"}), 401
        g.current_user = user

        if request.path.startswith("/api/auth/"):
            return None
        if user.role in {"admin", "registrar"}:
            return None
        if user.role == "student" and _student_owns_target(user):
            return None
        return jsonify({"error": "forbidden"}), 403


@bp.post("/api/auth/bootstrap")
def bootstrap_admin():
    data = request.get_json(force=True)
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not username or not email or len(password) < 10:
        return jsonify({"error": "invalid_bootstrap_request"}), 400

    with new_session() as session:
        existing_count = session.scalar(select(func.count()).select_from(UserAccount)) or 0
        if existing_count:
            return jsonify({"error": "bootstrap_already_completed"}), 409
        user = UserAccount(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="admin",
        )
        session.add(user)
        session.commit()
        return jsonify({"user": user_json(user), "token": issue_token(user)}), 201


@bp.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    identifier = str(data.get("username", data.get("email", ""))).strip().lower()
    password = str(data.get("password", ""))
    if not identifier or not password:
        return jsonify({"error": "invalid_credentials"}), 401

    with new_session() as session:
        user = session.scalar(select(UserAccount).where(
            (UserAccount.username == identifier) | (UserAccount.email == identifier)
        ))
        if user is None or not user.is_active or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "invalid_credentials"}), 401
        return jsonify({
            "token": issue_token(user),
            "token_type": "Bearer",
            "expires_in": TOKEN_MAX_AGE_SECONDS,
            "user": user_json(user),
        })


@bp.get("/api/auth/me")
def me():
    user = getattr(g, "current_user", None)
    if user is None:
        return jsonify({"error": "authentication_required"}), 401
    return jsonify(user_json(user))


@bp.post("/api/auth/users")
def create_user():
    actor = getattr(g, "current_user", None)
    if actor is None:
        return jsonify({"error": "authentication_required"}), 401
    if actor.role != "admin":
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True)
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "")).strip().lower()
    student_id = data.get("student_id")
    if not username or not email or len(password) < 10 or role not in {"student", "registrar", "admin"}:
        return jsonify({"error": "invalid_user"}), 400
    if role == "student":
        try:
            student_id = int(student_id)
        except (TypeError, ValueError):
            return jsonify({"error": "student_id_required"}), 400
    else:
        student_id = None

    from .models import Student

    with new_session() as session:
        if session.scalar(select(UserAccount).where(UserAccount.username == username)):
            return jsonify({"error": "username_exists"}), 409
        if session.scalar(select(UserAccount).where(UserAccount.email == email)):
            return jsonify({"error": "email_exists"}), 409
        if role == "student":
            if session.get(Student, student_id) is None:
                return jsonify({"error": "student_not_found"}), 404
            if session.scalar(select(UserAccount).where(UserAccount.student_id == student_id)):
                return jsonify({"error": "student_account_exists"}), 409

        user = UserAccount(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            student_id=student_id,
        )
        session.add(user)
        session.commit()
        return jsonify(user_json(user)), 201


@bp.get("/api/auth/users")
def list_users():
    actor = getattr(g, "current_user", None)
    if actor is None:
        return jsonify({"error": "authentication_required"}), 401
    if actor.role != "admin":
        return jsonify({"error": "forbidden"}), 403
    with new_session() as session:
        rows = list(session.scalars(select(UserAccount).order_by(UserAccount.username)))
        return jsonify({"items": [user_json(row) for row in rows]})
