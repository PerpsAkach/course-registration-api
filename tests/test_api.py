import pytest

from app import create_app
from app.db import Base, get_engine


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:")
    app.config["TESTING"] = True
    Base.metadata.create_all(get_engine())
    return app.test_client()


def create_student(client, number="S1001", email="amina@example.edu", first="Amina", last="Otieno"):
    return client.post("/api/students", json={
        "student_number": number,
        "first_name": first,
        "last_name": last,
        "email": email,
    })


def create_course(client, code="CS101", title="Introduction to Programming", capacity=2):
    return client.post("/api/courses", json={
        "code": code,
        "title": title,
        "credits": 3,
        "capacity": capacity,
    })


def create_term(client, name="Fall", year=2026):
    return client.post("/api/terms", json={
        "name": name,
        "year": year,
        "starts_on": f"{year}-09-01",
        "ends_on": f"{year}-12-20",
        "registration_opens_on": f"{year}-04-01",
        "registration_closes_on": f"{year}-09-10",
    })


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_student_crud_search_and_pagination(client):
    first = create_student(client)
    second = create_student(client, "S1002", "brian@example.edu", "Brian", "Kamau")
    assert first.status_code == 201
    assert second.status_code == 201

    student_id = first.get_json()["id"]
    fetched = client.get(f"/api/students/{student_id}")
    assert fetched.status_code == 200
    assert fetched.get_json()["student_number"] == "S1001"

    search = client.get("/api/students?q=amina&page=1&per_page=1")
    payload = search.get_json()
    assert search.status_code == 200
    assert payload["total"] == 1
    assert len(payload["items"]) == 1

    updated = client.patch(f"/api/students/{student_id}", json={"first_name": "Amara"})
    assert updated.status_code == 200
    assert updated.get_json()["first_name"] == "Amara"

    deleted = client.delete(f"/api/students/{student_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/students/{student_id}").status_code == 404


def test_course_crud_search_and_capacity_guard(client):
    course = create_course(client, capacity=1)
    assert course.status_code == 201
    course_id = course.get_json()["id"]

    student = create_student(client)
    enrollment = client.post("/api/enrollments", json={
        "student_id": student.get_json()["id"],
        "course_id": course_id,
    })
    assert enrollment.status_code == 201

    too_small = client.patch(f"/api/courses/{course_id}", json={"capacity": 0})
    assert too_small.status_code == 400

    updated = client.patch(f"/api/courses/{course_id}", json={"title": "Programming Fundamentals"})
    assert updated.status_code == 200
    assert updated.get_json()["title"] == "Programming Fundamentals"

    search = client.get("/api/courses?q=programming")
    assert search.status_code == 200
    assert search.get_json()["total"] == 1


def test_enrollment_listing_relationships_drop_and_reactivation(client):
    student = create_student(client)
    course = create_course(client)
    student_id = student.get_json()["id"]
    course_id = course.get_json()["id"]

    enrollment = client.post("/api/enrollments", json={
        "student_id": student_id,
        "course_id": course_id,
    })
    assert enrollment.status_code == 201
    enrollment_id = enrollment.get_json()["id"]

    listed = client.get(f"/api/enrollments?student_id={student_id}&status=active")
    assert listed.status_code == 200
    assert listed.get_json()["total"] == 1

    student_courses = client.get(f"/api/students/{student_id}/courses")
    assert student_courses.status_code == 200
    assert student_courses.get_json()["items"][0]["id"] == course_id

    course_students = client.get(f"/api/courses/{course_id}/students")
    assert course_students.status_code == 200
    assert course_students.get_json()["items"][0]["id"] == student_id

    dropped = client.delete(f"/api/enrollments/{enrollment_id}")
    assert dropped.status_code == 200
    assert dropped.get_json()["status"] == "dropped"

    reactivated = client.post("/api/enrollments", json={
        "student_id": student_id,
        "course_id": course_id,
    })
    assert reactivated.status_code == 201
    assert reactivated.get_json()["status"] == "active"


def test_duplicate_and_capacity_errors(client):
    student1 = create_student(client, "S1001", "a@example.edu")
    student2 = create_student(client, "S1002", "b@example.edu")
    course = create_course(client, capacity=1)
    course_id = course.get_json()["id"]

    first = client.post("/api/enrollments", json={
        "student_id": student1.get_json()["id"],
        "course_id": course_id,
    })
    assert first.status_code == 201

    duplicate = client.post("/api/enrollments", json={
        "student_id": student1.get_json()["id"],
        "course_id": course_id,
    })
    assert duplicate.status_code == 409

    full = client.post("/api/enrollments", json={
        "student_id": student2.get_json()["id"],
        "course_id": course_id,
    })
    assert full.status_code == 409
    assert full.get_json()["error"] == "course_full"


def test_term_creation_and_listing(client):
    term = create_term(client)
    assert term.status_code == 201
    payload = term.get_json()
    assert payload["name"] == "Fall"
    assert payload["year"] == 2026

    listed = client.get("/api/terms")
    assert listed.status_code == 200
    assert listed.get_json()["items"][0]["id"] == payload["id"]

    duplicate = create_term(client)
    assert duplicate.status_code == 409


def test_section_creation_schedule_and_filters(client):
    course = create_course(client)
    term = create_term(client)
    course_id = course.get_json()["id"]
    term_id = term.get_json()["id"]

    section = client.post("/api/sections", json={
        "course_id": course_id,
        "term_id": term_id,
        "section_number": "001",
        "instructor": "Dr. Njoroge",
        "capacity": 25,
        "meeting_days": "MWF",
        "starts_at": "09:00",
        "ends_at": "09:50",
        "location": "SCI-210",
    })
    assert section.status_code == 201
    payload = section.get_json()
    assert payload["meeting_days"] == "MWF"
    assert payload["starts_at"] == "09:00"
    assert payload["ends_at"] == "09:50"

    listed = client.get(f"/api/sections?course_id={course_id}&term_id={term_id}")
    assert listed.status_code == 200
    assert len(listed.get_json()["items"]) == 1

    fetched = client.get(f"/api/sections/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["location"] == "SCI-210"

    duplicate = client.post("/api/sections", json={
        "course_id": course_id,
        "term_id": term_id,
        "section_number": "001",
        "capacity": 25,
    })
    assert duplicate.status_code == 409


def test_prerequisite_relationship(client):
    intro = create_course(client, code="CS101", title="Introduction")
    advanced = create_course(client, code="CS201", title="Data Structures")
    intro_id = intro.get_json()["id"]
    advanced_id = advanced.get_json()["id"]

    added = client.post(f"/api/courses/{advanced_id}/prerequisites", json={
        "required_course_id": intro_id,
    })
    assert added.status_code == 201

    listed = client.get(f"/api/courses/{advanced_id}/prerequisites")
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert len(items) == 1
    assert items[0]["required_course"]["code"] == "CS101"

    duplicate = client.post(f"/api/courses/{advanced_id}/prerequisites", json={
        "required_course_id": intro_id,
    })
    assert duplicate.status_code == 409

    self_prereq = client.post(f"/api/courses/{intro_id}/prerequisites", json={
        "required_course_id": intro_id,
    })
    assert self_prereq.status_code == 400
