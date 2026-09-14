import pytest

from app.db import Base, get_engine
from app.secure import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:", auth_required=True)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "audit-test-secret"
    Base.metadata.create_all(get_engine())
    return app.test_client()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _bootstrap(client):
    response = client.post("/api/auth/bootstrap", json={
        "username": "admin",
        "email": "admin@example.edu",
        "password": "AdminPassword123!",
    })
    assert response.status_code == 201
    return response.get_json()["token"], response.get_json()["user"]["id"]


def test_mutating_requests_are_audited_and_admin_can_read_log(client):
    admin_token, admin_id = _bootstrap(client)

    created = client.post("/api/courses", headers=_auth(admin_token), json={
        "code": "CS501",
        "title": "Distributed Systems",
        "credits": 3,
        "capacity": 20,
    })
    assert created.status_code == 201
    assert created.headers.get("X-Request-ID")

    events = client.get("/api/audit-events", headers=_auth(admin_token))
    assert events.status_code == 200
    rows = events.get_json()["items"]

    course_events = [row for row in rows if row["path"] == "/api/courses" and row["method"] == "POST"]
    assert course_events
    assert course_events[0]["actor_user_id"] == admin_id
    assert course_events[0]["status_code"] == 201


def test_audit_log_is_admin_only(client):
    admin_token, _ = _bootstrap(client)

    created = client.post("/api/auth/users", headers=_auth(admin_token), json={
        "username": "registrar",
        "email": "registrar@example.edu",
        "password": "RegistrarPassword123!",
        "role": "registrar",
    })
    assert created.status_code == 201

    login = client.post("/api/auth/login", json={
        "username": "registrar",
        "password": "RegistrarPassword123!",
    })
    assert login.status_code == 200
    registrar_token = login.get_json()["token"]

    forbidden = client.get("/api/audit-events", headers=_auth(registrar_token))
    assert forbidden.status_code == 403
