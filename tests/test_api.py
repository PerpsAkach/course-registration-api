import pytest

from app import create_app
from app.db import Base, get_engine


@pytest.fixture()
def client():
    app = create_app("sqlite+pysqlite:///:memory:")
    app.config["TESTING"] = True
    Base.metadata.create_all(get_engine())
    return app.test_client()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_student_course_enrollment_flow(client):
    student = client.post("/api/students", json={
        "student_number": "S1001",
        "first_name": "Amina",
        "last_name": "Otieno",
        "email": "amina@example.edu",
    })
    assert student.status_code == 201

    course = client.post("/api/courses", json={
        "code": "CS101",
        "title": "Introduction to Programming",
        "credits": 3,
        "capacity": 1,
    })
    assert course.status_code == 201

    enrollment = client.post("/api/enrollments", json={
        "student_id": student.get_json()["id"],
        "course_id": course.get_json()["id"],
    })
    assert enrollment.status_code == 201
    assert enrollment.get_json()["status"] == "active"
