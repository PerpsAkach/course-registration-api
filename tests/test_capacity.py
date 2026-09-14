import pytest
from sqlalchemy.dialects import postgresql

from app.capacity import SectionCapacityExceeded, section_lock_statement
from app.db import Base, get_engine, new_session
from app.models import SectionEnrollment
from app.secure import create_app


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:", auth_required=False)
    app.config["TESTING"] = True
    Base.metadata.create_all(get_engine())
    return app.test_client()


def _student(client, number, email):
    response = client.post("/api/students", json={
        "student_number": number,
        "first_name": "Test",
        "last_name": number,
        "email": email,
    })
    assert response.status_code == 201
    return response.get_json()["id"]


def _section(client, capacity=1):
    course = client.post("/api/courses", json={
        "code": "CS401",
        "title": "Concurrent Systems",
        "credits": 3,
        "capacity": 30,
    })
    assert course.status_code == 201
    term = client.post("/api/terms", json={
        "name": "Fall",
        "year": 2026,
        "starts_on": "2026-09-01",
        "ends_on": "2026-12-20",
        "registration_opens_on": "2026-08-01",
        "registration_closes_on": "2026-09-15",
    })
    assert term.status_code == 201
    section = client.post("/api/sections", json={
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


def test_postgresql_capacity_guard_uses_row_lock():
    sql = str(section_lock_statement(42).compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql.upper()


def test_capacity_guard_blocks_direct_overfill(client):
    first_student = _student(client, "S1", "s1@example.edu")
    second_student = _student(client, "S2", "s2@example.edu")
    section_id = _section(client, capacity=1)

    first = client.post("/api/section-enrollments", json={
        "student_id": first_student,
        "section_id": section_id,
        "as_of": "2026-08-15",
    })
    assert first.status_code == 201

    with new_session() as session:
        session.add(SectionEnrollment(student_id=second_student, section_id=section_id))
        with pytest.raises(SectionCapacityExceeded) as exc_info:
            session.commit()
        session.rollback()
        assert exc_info.value.section_id == section_id
