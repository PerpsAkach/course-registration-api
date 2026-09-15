from __future__ import annotations

import os

from flask import jsonify

from . import create_app as create_core_app
from . import capacity as _capacity  # noqa: F401 - registers SQLAlchemy capacity guard
from .audit import init_audit
from .auth import init_auth
from .docs import init_docs
from .observability import init_observability
from .rate_limit import init_rate_limiting
from .waitlist import init_waitlist


def _resolve_secret_key() -> str:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    configured = os.getenv("APP_SECRET_KEY")
    if environment == "production":
        if not configured or configured in {
            "development-only-change-me",
            "local-development-secret-change-me",
        }:
            raise RuntimeError("APP_SECRET_KEY must be explicitly configured for production")
        return configured
    return configured or "development-only-change-me"


def create_app(database_url: str | None = None, *, auth_required: bool = True):
    """Create the production-oriented application with security controls enabled."""
    app = create_core_app(database_url)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _resolve_secret_key()
    if "docs" not in app.blueprints:
        init_docs(app)
    if "observability" not in app.blueprints:
        init_observability(app)
    if "waitlist" not in app.blueprints:
        init_waitlist(app)
    if "audit" not in app.blueprints:
        init_audit(app)
    if "auth" not in app.blueprints:
        init_auth(app, required=auth_required)
    init_rate_limiting(app)

    @app.errorhandler(_capacity.SectionCapacityExceeded)
    def _section_capacity_exceeded(exc):
        return jsonify({"error": "section_full", "section_id": exc.section_id}), 409

    return app
