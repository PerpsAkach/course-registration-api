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


def create_term(client, name="Fall", year=2026, opens="2026-08-01", closes="2026-09-15"):
    return client.post("/api/terms", json={
        "name": name,
        "year": year,
        "starts_on": f"{year}-09-01",
        "ends_on": f"{year}-12-20",
        "registration_opens_on": opens,
        "registration_closes_on": closes,
    })


def create_section(client, course_id, term_id, number="001", capacity=2, days="MW", starts="09:00", ends="10:15"):
    return client.post("/api/sections", json={
        "course_id": course_id,
        "term_id": term_id,
        "section_number": number,
        "capacity": capacity,
        "meeting_days": days,
        "starts_at": starts,
        "ends_at": ends,
        "instructor": "Dr. Rivera",
        "location": "TECH-201",
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


def test_terms_sections_and_prerequisites(client):
    intro = create_course(client, "CS101", "Intro")
    advanced = create_course(client, "CS201", "Advanced")
    term = create_term(client)
    intro_id = intro.get_json()["id"]
    advanced_id = advanced.get_json()["id"]
    term_id = term.get_json()["id"]

    section = create_section(client, advanced_id, term_id)
    assert section.status_code == 201
    assert section.get_json()["meeting_days"] == "MW"

    prereq = client.post(f"/api/courses/{advanced_id}/prerequisites", json={"required_course_id": intro_id})
    assert prereq.status_code == 201

    listed = client.get(f"/api/courses/{advanced_id}/prerequisites")
    assert listed.status_code == 200
    assert listed.get_json()["items"][0]["required_course"]["code"] == "CS101"


def test_section_registration_enforces_window_and_prerequisites(client):
    student = create_student(client)
    intro = create_course(client, "CS101", "Intro")
    advanced = create_course(client, "CS201", "Advanced")
    term = create_term(client)

    student_id = student.get_json()["id"]
    intro_id = intro.get_json()["id"]
    advanced_id = advanced.get_json()["id"]
    term_id = term.get_json()["id"]
    section = create_section(client, advanced_id, term_id)
    section_id = section.get_json()["id"]

    client.post(f"/api/courses/{advanced_id}/prerequisites", json={"required_course_id": intro_id})

    before_window = client.post("/api/section-enrollments", json={
        "student_id": student_id,
        "section_id": section_id,
        "as_of": "2026-07-31",
    })
    assert before_window.status_code == 409
    assert before_window.get_json()["error"] == "registration_closed"

    missing = client.post("/api/section-enrollments", json={
        "student_id": student_id,
        "section_id": section_id,
        "as_of": "2026-08-15",
    })
    assert missing.status_code == 409
    assert missing.get_json()["error"] == "prerequisites_not_met"

    completion = client.post("/api/completions", json={
        "student_id": student_id,
        "course_id": intro_id,
        "completed_on": "2026-05-15",
        "grade": "A",
    })
    assert completion.status_code == 201

    enrolled = client.post("/api/section-enrollments", json={
        "student_id": student_id,
        "section_id": section_id,
        "as_of": "2026-08-15",
    })
    assert enrolled.status_code == 201
    assert enrolled.get_json()["status"] == "active"


def test_section_capacity_and_schedule_conflict(client):
    first_student = create_student(client, "S1001", "a@example.edu")
    second_student = create_student(client, "S1002", "b@example.edu")
    course1 = create_course(client, "CS101", "Intro")
    course2 = create_course(client, "MATH101", "Math")
    term = create_term(client)

    first_student_id = first_student.get_json()["id"]
    second_student_id = second_student.get_json()["id"]
    term_id = term.get_json()["id"]
    section1 = create_section(client, course1.get_json()["id"], term_id, "001", capacity=1, days="MW", starts="09:00", ends="10:15")
    section2 = create_section(client, course2.get_json()["id"], term_id, "001", capacity=2, days="MW", starts="10:00", ends="11:15")

    first = client.post("/api/section-enrollments", json={
        "student_id": first_student_id,
        "section_id": section1.get_json()["id"],
        "as_of": "2026-08-15",
    })
    assert first.status_code == 201

    full = client.post("/api/section-enrollments", json={
        "student_id": second_student_id,
        "section_id": section1.get_json()["id"],
        "as_of": "2026-08-15",
    })
    assert full.status_code == 409
    assert full.get_json()["error"] == "section_full"

    conflict = client.post("/api/section-enrollments", json={
        "student_id": first_student_id,
        "section_id": section2.get_json()["id"],
        "as_of": "2026-08-15",
    })
    assert conflict.status_code == 409
    assert conflict.get_json()["error"] == "schedule_conflict"


def test_section_enrollment_drop_and_reactivation(client):
    student = create_student(client)
    course = create_course(client)
    term = create_term(client)
    section = create_section(client, course.get_json()["id"], term.get_json()["id"])

    created = client.post("/api/section-enrollments", json={
        "student_id": student.get_json()["id"],
        "section_id": section.get_json()["id"],
        "as_of": "2026-08-15",
    })
    assert created.status_code == 201
    enrollment_id = created.get_json()["id"]

    dropped = client.delete(f"/api/section-enrollments/{enrollment_id}")
    assert dropped.status_code == 200
    assert dropped.get_json()["status"] == "dropped"

    reactivated = client.post("/api/section-enrollments", json={
        "student_id": student.get_json()["id"],
        "section_id": section.get_json()["id"],
        "as_of": "2026-08-15",
    })
    assert reactivated.status_code == 201
    assert reactivated.get_json()["id"] == enrollment_id
    assert reactivated.get_json()["status"] == "active"
