import pytest

from app import create_app
from app.db import Base, get_engine
from app.waitlist import init_waitlist


@pytest.fixture()
def app():
    app = create_app("sqlite+pysqlite:///:memory:")
    app.config["TESTING"] = True
    app.config["REGISTRATION_POLICY_DATE"] = "2026-08-15"
    init_waitlist(app)
    Base.metadata.create_all(get_engine())
    return app


@pytest.fixture()
def client(app):
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


def create_section(client, course_id, term_id, capacity=1, number="001", days="MW", starts="09:00", ends="10:15"):
    return client.post("/api/sections", json={
        "course_id": course_id,
        "term_id": term_id,
        "section_number": number,
        "capacity": capacity,
        "meeting_days": days,
        "starts_at": starts,
        "ends_at": ends,
    }).get_json()["id"]


def enroll(client, student_id, section_id):
    return client.post("/api/section-enrollments", json={
        "student_id": student_id,
        "section_id": section_id,
    })


def waitlist(client, student_id, section_id):
    return client.post("/api/waitlists", json={
        "student_id": student_id,
        "section_id": section_id,
    })


def test_waitlist_join_cancel_rejoin_and_duplicate_validation(client):
    student1 = create_student(client, "S1", "s1@example.edu")
    student2 = create_student(client, "S2", "s2@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    first = enroll(client, student1, section)
    assert first.status_code == 201

    waiting = waitlist(client, student2, section)
    assert waiting.status_code == 201
    assert waiting.get_json()["status"] == "waiting"

    duplicate = waitlist(client, student2, section)
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "already_waitlisted"

    entry_id = waiting.get_json()["id"]
    cancelled = client.delete(f"/api/waitlists/{entry_id}")
    assert cancelled.status_code == 200
    assert cancelled.get_json()["status"] == "cancelled"

    rejoined = waitlist(client, student2, section)
    assert rejoined.status_code == 201
    assert rejoined.get_json()["id"] == entry_id
    assert rejoined.get_json()["status"] == "waiting"


def test_waitlist_requires_full_section(client):
    student = create_student(client, "S1", "s1@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    response = waitlist(client, student, section)
    assert response.status_code == 409
    assert response.get_json()["error"] == "section_has_available_seats"


def test_drop_and_waitlist_promotion_are_one_workflow(client):
    student1 = create_student(client, "S1", "s1@example.edu")
    student2 = create_student(client, "S2", "s2@example.edu")
    student3 = create_student(client, "S3", "s3@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    enrolled = enroll(client, student1, section)
    enrollment_id = enrolled.get_json()["id"]

    first_waiting = waitlist(client, student2, section)
    second_waiting = waitlist(client, student3, section)
    assert first_waiting.status_code == 201
    assert second_waiting.status_code == 201

    dropped = client.delete(f"/api/section-enrollments/{enrollment_id}")
    assert dropped.status_code == 200
    assert dropped.get_json()["status"] == "dropped"
    assert dropped.get_json()["promoted_student_id"] == student2

    promoted = client.get(f"/api/section-enrollments?section_id={section}&status=active").get_json()["items"]
    assert len(promoted) == 1
    assert promoted[0]["student_id"] == student2

    entries = client.get(f"/api/waitlists?section_id={section}").get_json()["items"]
    by_student = {entry["student_id"]: entry["status"] for entry in entries}
    assert by_student[student2] == "promoted"
    assert by_student[student3] == "waiting"


def test_promotion_skips_currently_ineligible_first_candidate(client):
    seat_holder = create_student(client, "S1", "s1@example.edu")
    first_waiter = create_student(client, "S2", "s2@example.edu")
    second_waiter = create_student(client, "S3", "s3@example.edu")
    course = create_course(client, "CS101")
    blocker_course = create_course(client, "MATH101")
    term = create_term(client)
    target = create_section(client, course, term, capacity=1, days="MW", starts="09:00", ends="10:15")
    blocker = create_section(client, blocker_course, term, capacity=5, days="MW", starts="11:00", ends="12:15")

    enrolled = enroll(client, seat_holder, target)
    assert waitlist(client, first_waiter, target).status_code == 201
    assert waitlist(client, second_waiter, target).status_code == 201

    # Make the first waiter ineligible after joining by registering them for the
    # same course in another section of the same term.
    alternate = create_section(client, course, term, capacity=5, number="002", days="TR", starts="13:00", ends="14:15")
    assert enroll(client, first_waiter, alternate).status_code == 201
    # A non-conflicting unrelated registration remains allowed for waiter two.
    assert enroll(client, second_waiter, blocker).status_code == 201

    dropped = client.delete(f"/api/section-enrollments/{enrolled.get_json()['id']}")
    assert dropped.status_code == 200
    assert dropped.get_json()["promoted_student_id"] == second_waiter

    entries = client.get(f"/api/waitlists?section_id={target}").get_json()["items"]
    by_student = {entry["student_id"]: entry["status"] for entry in entries}
    assert by_student[first_waiter] == "waiting"
    assert by_student[second_waiter] == "promoted"


def test_no_promotion_after_registration_window_closes(app, client):
    student1 = create_student(client, "S1", "s1@example.edu")
    student2 = create_student(client, "S2", "s2@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    enrolled = enroll(client, student1, section)
    assert waitlist(client, student2, section).status_code == 201

    app.config["REGISTRATION_POLICY_DATE"] = "2026-09-16"
    dropped = client.delete(f"/api/section-enrollments/{enrolled.get_json()['id']}")
    assert dropped.status_code == 200
    assert "promoted_student_id" not in dropped.get_json()

    active = client.get(f"/api/section-enrollments?section_id={section}&status=active").get_json()["items"]
    assert active == []
    entry = client.get(f"/api/waitlists?section_id={section}").get_json()["items"][0]
    assert entry["status"] == "waiting"


def test_client_supplied_as_of_cannot_bypass_server_policy(app, client):
    app.config["REGISTRATION_POLICY_DATE"] = "2026-09-16"
    student = create_student(client, "S1", "s1@example.edu")
    course = create_course(client, "CS101")
    term = create_term(client)
    section = create_section(client, course, term, capacity=1)

    response = client.post("/api/section-enrollments", json={
        "student_id": student,
        "section_id": section,
        "as_of": "2026-08-15",
    })
    assert response.status_code == 409
    assert response.get_json()["error"] == "registration_closed"
