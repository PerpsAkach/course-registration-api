import pytest

from app.db import Base, get_engine
from app.secure import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:", auth_required=True)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "secure-registration-test-secret"
    app.config["REGISTRATION_POLICY_DATE"] = "2026-08-15"
    Base.metadata.create_all(get_engine())
    return app.test_client()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def bootstrap(client):
    response = client.post("/api/auth/bootstrap", json={
        "username": "admin",
        "email": "admin@example.edu",
        "password": "AdminPassword123!",
    })
    assert response.status_code == 201
    return response.get_json()["token"]


def create_student(client, admin_token, number, email):
    response = client.post("/api/students", headers=auth(admin_token), json={
        "student_number": number,
        "first_name": "Student",
        "last_name": number,
        "email": email,
    })
    assert response.status_code == 201
    return response.get_json()["id"]


def create_student_account(client, admin_token, student_id, username, email):
    response = client.post("/api/auth/users", headers=auth(admin_token), json={
        "username": username,
        "email": email,
        "password": "StudentPassword123!",
        "role": "student",
        "student_id": student_id,
    })
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={
        "username": username,
        "password": "StudentPassword123!",
    })
    assert login.status_code == 200
    return login.get_json()["token"]


def create_catalog(client, admin_token, *, capacity=2):
    course = client.post("/api/courses", headers=auth(admin_token), json={
        "code": "CS401",
        "title": "Secure Registration",
        "credits": 3,
        "capacity": 30,
    })
    assert course.status_code == 201
    term = client.post("/api/terms", headers=auth(admin_token), json={
        "name": "Fall",
        "year": 2026,
        "starts_on": "2026-09-01",
        "ends_on": "2026-12-20",
        "registration_opens_on": "2026-08-01",
        "registration_closes_on": "2026-09-15",
    })
    assert term.status_code == 201
    section = client.post("/api/sections", headers=auth(admin_token), json={
        "course_id": course.get_json()["id"],
        "term_id": term.get_json()["id"],
        "section_number": "001",
        "capacity": capacity,
        "meeting_days": "MW",
        "starts_at": "09:00",
        "ends_at": "10:15",
    })
    assert section.status_code == 201
    return section.get_json()["id"]


def test_student_can_register_and_query_only_own_section_enrollment(client):
    admin_token = bootstrap(client)
    own_id = create_student(client, admin_token, "S1001", "record1@example.edu")
    other_id = create_student(client, admin_token, "S1002", "record2@example.edu")
    student_token = create_student_account(
        client,
        admin_token,
        own_id,
        "student1",
        "student1.login@example.edu",
    )
    section_id = create_catalog(client, admin_token, capacity=2)

    own = client.post("/api/section-enrollments", headers=auth(student_token), json={
        "student_id": own_id,
        "section_id": section_id,
    })
    assert own.status_code == 201
    assert own.get_json()["student_id"] == own_id

    own_list = client.get(
        f"/api/section-enrollments?student_id={own_id}",
        headers=auth(student_token),
    )
    assert own_list.status_code == 200
    assert [item["student_id"] for item in own_list.get_json()["items"]] == [own_id]

    cross_student = client.post("/api/section-enrollments", headers=auth(student_token), json={
        "student_id": other_id,
        "section_id": section_id,
    })
    assert cross_student.status_code == 403

    cross_list = client.get(
        f"/api/section-enrollments?student_id={other_id}",
        headers=auth(student_token),
    )
    assert cross_list.status_code == 403


def test_student_waitlist_ownership_is_enforced(client):
    admin_token = bootstrap(client)
    holder_id = create_student(client, admin_token, "S2000", "holder@example.edu")
    own_id = create_student(client, admin_token, "S2001", "waiter@example.edu")
    other_id = create_student(client, admin_token, "S2002", "other@example.edu")
    student_token = create_student_account(
        client,
        admin_token,
        own_id,
        "waiter",
        "waiter.login@example.edu",
    )
    section_id = create_catalog(client, admin_token, capacity=1)

    holder = client.post("/api/section-enrollments", headers=auth(admin_token), json={
        "student_id": holder_id,
        "section_id": section_id,
    })
    assert holder.status_code == 201

    own_waitlist = client.post("/api/waitlists", headers=auth(student_token), json={
        "student_id": own_id,
        "section_id": section_id,
    })
    assert own_waitlist.status_code == 201
    assert own_waitlist.get_json()["student_id"] == own_id

    own_list = client.get(
        f"/api/waitlists?student_id={own_id}",
        headers=auth(student_token),
    )
    assert own_list.status_code == 200

    cross_waitlist = client.post("/api/waitlists", headers=auth(student_token), json={
        "student_id": other_id,
        "section_id": section_id,
    })
    assert cross_waitlist.status_code == 403

    cross_list = client.get(
        f"/api/waitlists?student_id={other_id}",
        headers=auth(student_token),
    )
    assert cross_list.status_code == 403
