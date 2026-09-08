from __future__ import annotations

import os

from flask import Flask, jsonify, request
from sqlalchemy import func, select

from .db import Base, configure_database, get_engine, new_session
from .models import Course, Enrollment, Student


def create_app(database_url: str | None = None) -> Flask:
    app = Flask(__name__)
    configure_database(database_url or os.getenv("DATABASE_URL", "sqlite:///course_registration.db"))

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/students")
    def create_student():
        data = request.get_json(force=True)
        required = ["student_number", "first_name", "last_name", "email"]
        if any(not str(data.get(k, "")).strip() for k in required):
            return jsonify({"error": "validation_error"}), 400

        with new_session() as session:
            if session.scalar(select(Student).where(Student.student_number == data["student_number"])):
                return jsonify({"error": "student_number_exists"}), 409
            if session.scalar(select(Student).where(Student.email == data["email"].lower())):
                return jsonify({"error": "email_exists"}), 409

            student = Student(
                student_number=data["student_number"].strip(),
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                email=data["email"].strip().lower(),
            )
            session.add(student)
            session.commit()
            return jsonify({
                "id": student.id,
                "student_number": student.student_number,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
            }), 201

    @app.get("/api/students")
    def list_students():
        with new_session() as session:
            rows = list(session.scalars(select(Student).order_by(Student.last_name, Student.first_name)))
            return jsonify({"items": [
                {
                    "id": s.id,
                    "student_number": s.student_number,
                    "first_name": s.first_name,
                    "last_name": s.last_name,
                    "email": s.email,
                }
                for s in rows
            ]})

    @app.post("/api/courses")
    def create_course():
        data = request.get_json(force=True)
        try:
            credits = int(data.get("credits", 3))
            capacity = int(data.get("capacity", 30))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_numeric_field"}), 400

        if not str(data.get("code", "")).strip() or not str(data.get("title", "")).strip():
            return jsonify({"error": "validation_error"}), 400
        if credits <= 0 or capacity <= 0:
            return jsonify({"error": "invalid_course_configuration"}), 400

        with new_session() as session:
            code = data["code"].strip().upper()
            if session.scalar(select(Course).where(Course.code == code)):
                return jsonify({"error": "course_code_exists"}), 409

            course = Course(
                code=code,
                title=data["title"].strip(),
                description=data.get("description"),
                credits=credits,
                capacity=capacity,
            )
            session.add(course)
            session.commit()
            return jsonify({
                "id": course.id,
                "code": course.code,
                "title": course.title,
                "credits": course.credits,
                "capacity": course.capacity,
            }), 201

    @app.get("/api/courses")
    def list_courses():
        with new_session() as session:
            rows = list(session.scalars(select(Course).order_by(Course.code)))
            return jsonify({"items": [
                {
                    "id": c.id,
                    "code": c.code,
                    "title": c.title,
                    "credits": c.credits,
                    "capacity": c.capacity,
                }
                for c in rows
            ]})

    @app.post("/api/enrollments")
    def create_enrollment():
        data = request.get_json(force=True)
        try:
            student_id = int(data["student_id"])
            course_id = int(data["course_id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid_enrollment_request"}), 400

        with new_session() as session:
            student = session.get(Student, student_id)
            course = session.get(Course, course_id)
            if student is None or course is None:
                return jsonify({"error": "student_or_course_not_found"}), 404

            existing = session.scalar(
                select(Enrollment).where(
                    Enrollment.student_id == student_id,
                    Enrollment.course_id == course_id,
                )
            )
            if existing and existing.status == "active":
                return jsonify({"error": "already_enrolled"}), 409

            active_count = session.scalar(
                select(func.count()).select_from(Enrollment).where(
                    Enrollment.course_id == course_id,
                    Enrollment.status == "active",
                )
            ) or 0
            if active_count >= course.capacity:
                return jsonify({"error": "course_full"}), 409

            if existing:
                existing.status = "active"
                enrollment = existing
            else:
                enrollment = Enrollment(student_id=student_id, course_id=course_id)
                session.add(enrollment)

            session.commit()
            return jsonify({
                "id": enrollment.id,
                "student_id": enrollment.student_id,
                "course_id": enrollment.course_id,
                "status": enrollment.status,
            }), 201

    @app.cli.command("init-db")
    def init_db():
        Base.metadata.create_all(get_engine())
        print("Database initialized.")

    return app
