from __future__ import annotations

import time

from flask import Blueprint, Response, current_app, g, request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

bp = Blueprint("observability", __name__)


def init_observability(app) -> None:
    """Register low-cardinality HTTP metrics and a Prometheus scrape endpoint."""
    registry = CollectorRegistry()
    requests_total = Counter(
        "course_registration_http_requests_total",
        "HTTP requests handled by the course-registration API.",
        ("method", "route", "status"),
        registry=registry,
    )
    request_duration = Histogram(
        "course_registration_http_request_duration_seconds",
        "HTTP request latency in seconds.",
        ("method", "route"),
        registry=registry,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )
    app_info = Gauge(
        "course_registration_app_info",
        "Static application information.",
        ("component",),
        registry=registry,
    )
    app_info.labels(component="api").set(1)

    app.extensions["prometheus_registry"] = registry
    app.extensions["prometheus_requests_total"] = requests_total
    app.extensions["prometheus_request_duration"] = request_duration

    if "observability" not in app.blueprints:
        app.register_blueprint(bp)

    @app.before_request
    def _metrics_start_timer():
        g.metrics_started_at = time.perf_counter()

    @app.after_request
    def _metrics_record(response):
        started_at = getattr(g, "metrics_started_at", None)
        if started_at is None:
            return response

        rule = request.url_rule.rule if request.url_rule is not None else "unmatched"
        method = request.method
        elapsed = max(0.0, time.perf_counter() - started_at)

        requests_total.labels(
            method=method,
            route=rule,
            status=str(response.status_code),
        ).inc()
        request_duration.labels(method=method, route=rule).observe(elapsed)
        return response


@bp.get("/metrics")
def metrics():
    registry = current_app.extensions["prometheus_registry"]
    return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)
