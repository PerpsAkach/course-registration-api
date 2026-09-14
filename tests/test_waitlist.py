import pytest

from app import create_app
from app.db import Base, get_engine
from app.waitlist import init_waitlist


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:")
    app.config["TESTING"] = True
    init_waitlist(app)
    Base.metadata.create_all(get_engine())
    return app.test_client()


def create_student(client, number, email):
    return client.post("/api/students", json={
        "student_number": number,
        "first_name": "Test",
        "last_name": number,
        "email": email,
    }).get_json()["id"]


def create_course(client, code):
    return client.post("/api/courses", json={
        "code": code,
        "title": code,
        "credits": 3,
        "capacity": 10,
    }).get_json()["id"]


def create_term(client):
    return client.post("/api/terms", json={
        "name": "Fall",
        "year": 2026,
        "starts_on": "2026-09-01",
        "ends_on": "2026-12-20",
        "registration_opens_on": "2026-08-01",
        "registration_closes_on": "2026-09-15",
    }).get_json()["id"]


def create_section(client, course_id, term_id, capacity=1):
    return client.post("/api/sections", json={
        "course_id": course_id,
        "term_id": term_id,
        "section_number": "001",
        "capacity": capacity,
        "meeting_days": "MW",
        "starts_at": "09:00",
        "ends_at": "10:15",
    }).get_json()["id"]


def test_waitlist_join_cancel_and_validation(client):
    student1 = create_student(client, "S1", "s1@example.edu")
    student2 = create_student(client, "S2", "s2@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    first = client.post("/api/section-enrollments", json={
        "student_id": student1,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    assert first.status_code == 201

    waiting = client.post("/api/waitlists", json={
        "student_id": student2,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    assert waiting.status_code == 201
    assert waiting.get_json()["status"] == "waiting"

    duplicate = client.post("/api/waitlists", json={
        "student_id": student2,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "already_waitlisted"

    entry_id = waiting.get_json()["id"]
    cancelled = client.delete(f"/api/waitlists/{entry_id}")
    assert cancelled.status_code == 200
    assert cancelled.get_json()["status"] == "cancelled"


def test_waitlist_automatically_promotes_next_student(client):
    student1 = create_student(client, "S1", "s1@example.edu")
    student2 = create_student(client, "S2", "s2@example.edu")
    student3 = create_student(client, "S3", "s3@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    enrolled = client.post("/api/section-enrollments", json={
        "student_id": student1,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    enrollment_id = enrolled.get_json()["id"]

    first_waiting = client.post("/api/waitlists", json={
        "student_id": student2,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    second_waiting = client.post("/api/waitlists", json={
        "student_id": student3,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    assert first_waiting.status_code == 201
    assert second_waiting.status_code == 201

    dropped = client.delete(f"/api/section-enrollments/{enrollment_id}")
    assert dropped.status_code == 200

    promoted = client.get(f"/api/section-enrollments?section_id={section}&status=active").get_json()["items"]
    assert len(promoted) == 1
    assert promoted[0]["student_id"] == student2

    waitlist = client.get(f"/api/waitlists?section_id={section}").get_json()["items"]
    by_student = {entry["student_id"]: entry["status"] for entry in waitlist}
    assert by_student[student2] == "promoted"
    assert by_student[student3] == "waiting"
