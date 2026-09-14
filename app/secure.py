from __future__ import annotations

import os

from . import create_app as create_core_app
from . import capacity as _capacity  # noqa: F401 - registers SQLAlchemy capacity guard
from .auth import init_auth
from .waitlist import init_waitlist


def create_app(database_url: str | None = None, *, auth_required: bool = True):
    """Create the production-oriented application with waitlists and RBAC enabled."""
    app = create_core_app(database_url)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.getenv("APP_SECRET_KEY", "development-only-change-me")
    if "waitlist" not in app.blueprints:
        init_waitlist(app)
    if "auth" not in app.blueprints:
        init_auth(app, required=auth_required)
    return app
