from __future__ import annotations

import os

from flask import jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def init_rate_limiting(app) -> Limiter:
    """Enable defensive request throttling for the secure API runtime.

    The default in-memory storage is appropriate for local development and the
    test suite. Production deployments can provide a shared backend through
    ``RATELIMIT_STORAGE_URI`` so limits are coordinated across workers.
    """
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[os.getenv("RATELIMIT_DEFAULT", "300 per minute")],
        storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    )
    limiter.init_app(app)

    endpoint_limits = {
        "auth.login": os.getenv("RATELIMIT_LOGIN", "10 per minute"),
        "auth.bootstrap_admin": os.getenv("RATELIMIT_BOOTSTRAP", "5 per hour"),
    }
    for endpoint, limit in endpoint_limits.items():
        view = app.view_functions.get(endpoint)
        if view is not None:
            app.view_functions[endpoint] = limiter.limit(limit)(view)

    @app.errorhandler(429)
    def _rate_limit_exceeded(_exc):
        return jsonify({"error": "rate_limit_exceeded"}), 429

    return limiter
