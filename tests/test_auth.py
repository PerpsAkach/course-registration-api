import pytest

from app import create_app
from app.auth import init_auth
from app.db import Base, get_engine


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:")
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-for-auth-suite"
    init_auth(app, required=True)
    Base.metadata.create_all(get_engine())
    return app.test_client()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def bootstrap(client):
    response = client.post("/api/auth/bootstrap", json={
        "username": "admin",
        "email": "admin@example.edu",
        "password": "AdminPassword123!",
    })
    assert response.status_code == 201
    return response.get_json()["token"]


def create_student_record(client, token, number="S1001", email="student@example.edu"):
    response = client.post("/api/students", headers=auth_header(token), json={
        "student_number": number,
        "first_name": "Amina",
        "last_name": "Otieno",
        "email": email,
    })
    assert response.status_code == 201
    return response.get_json()["id"]


def test_authentication_required_and_bootstrap_is_one_time(client):
    assert client.get("/api/courses").status_code == 401

    token = bootstrap(client)
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.get_json()["role"] == "admin"

    repeated = client.post("/api/auth/bootstrap", json={
        "username": "second-admin",
        "email": "second@example.edu",
        "password": "AnotherPassword123!",
    })
    assert repeated.status_code == 409
    assert repeated.get_json()["error"] == "bootstrap_already_completed"


def test_admin_creates_roles_and_registrar_manages_catalog(client):
    admin_token = bootstrap(client)

    registrar = client.post("/api/auth/users", headers=auth_header(admin_token), json={
        "username": "registrar",
        "email": "registrar@example.edu",
        "password": "RegistrarPassword123!",
        "role": "registrar",
    })
    assert registrar.status_code == 201

    login = client.post("/api/auth/login", json={
        "username": "registrar",
        "password": "RegistrarPassword123!",
    })
    assert login.status_code == 200
    registrar_token = login.get_json()["token"]

    course = client.post("/api/courses", headers=auth_header(registrar_token), json={
        "code": "CS101",
        "title": "Introduction to Programming",
        "credits": 3,
        "capacity": 30,
    })
    assert course.status_code == 201

    forbidden_user_admin = client.post("/api/auth/users", headers=auth_header(registrar_token), json={
        "username": "other",
        "email": "other@example.edu",
        "password": "OtherPassword123!",
        "role": "registrar",
    })
    assert forbidden_user_admin.status_code == 403


def test_student_can_access_only_own_student_resources(client):
    admin_token = bootstrap(client)
    student_id = create_student_record(client, admin_token)
    other_id = create_student_record(client, admin_token, "S1002", "other.student@example.edu")

    account = client.post("/api/auth/users", headers=auth_header(admin_token), json={
        "username": "amina",
        "email": "amina.login@example.edu",
        "password": "StudentPassword123!",
        "role": "student",
        "student_id": student_id,
    })
    assert account.status_code == 201

    login = client.post("/api/auth/login", json={
        "username": "amina",
        "password": "StudentPassword123!",
    })
    assert login.status_code == 200
    student_token = login.get_json()["token"]

    own = client.get(f"/api/students/{student_id}", headers=auth_header(student_token))
    assert own.status_code == 200

    other = client.get(f"/api/students/{other_id}", headers=auth_header(student_token))
    assert other.status_code == 403

    cannot_create_course = client.post("/api/courses", headers=auth_header(student_token), json={
        "code": "CS999",
        "title": "Restricted",
        "credits": 3,
        "capacity": 20,
    })
    assert cannot_create_course.status_code == 403


def test_invalid_login_is_rejected(client):
    bootstrap(client)
    bad = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrong-password",
    })
    assert bad.status_code == 401
    assert bad.get_json()["error"] == "invalid_credentials"
