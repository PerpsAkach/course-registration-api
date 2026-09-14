import pytest

from app.db import Base, get_engine
from app.secure import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:", auth_required=False)
    app.config["TESTING"] = True
    Base.metadata.create_all(get_engine())
    return app.test_client()


def test_metrics_endpoint_exposes_http_counters_and_latency(client):
    health = client.get("/api/health")
    assert health.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.get_data(as_text=True)

    assert "course_registration_app_info" in body
    assert "course_registration_http_requests_total" in body
    assert 'route="/api/health"' in body
    assert 'status="200"' in body
    assert "course_registration_http_request_duration_seconds" in body
