import pytest

from app.db import Base, get_engine
from app.secure import create_app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATELIMIT_LOGIN", "2 per minute")
    app = create_app("sqlite+pysqlite:///:memory:", auth_required=True)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "rate-limit-test-secret"
    Base.metadata.create_all(get_engine())
    return app.test_client()


def test_login_rate_limit_returns_json_429(client):
    payload = {"username": "missing", "password": "invalid-password"}

    first = client.post("/api/auth/login", json=payload)
    second = client.post("/api/auth/login", json=payload)
    limited = client.post("/api/auth/login", json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert limited.status_code == 429
    assert limited.get_json() == {"error": "rate_limit_exceeded"}
