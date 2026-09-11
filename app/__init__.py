from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from sqlalchemy import func, or_, select

from .db import Base, configure_database, get_engine, new_session
from .models import Course, Enrollment, Student


def _student_json(student: Student) -> dict:
    return {
        "id": student.id,
        "student_number": student.student_number,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
    }


def _course_json(course: Course) -> dict:
    return {
        "id": course.id,
        "code": course.code,
        "title": course.title,
        "description": course.description,
        "credits": course.credits,
        "capacity": course.capacity,
    }


def _enrollment_json(enrollment: Enrollment) -> dict:
    return {
        "id": enrollment.id,
        "student_id": enrollment.student_id,
        "course_id": enrollment.course_id,
        "status": enrollment.status,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "dropped_at": enrollment.dropped_at.isoformat() if enrollment.dropped_at else None,
    }


def _pagination() -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    except ValueError:
        page, per_page = 1, 25
    return page, per_page


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

        student_number = str(data["student_number"]).strip()
        email = str(data["email"]).strip().lower()
        with new_session() as session:
            if session.scalar(select(Student).where(Student.student_number == student_number)):
                return jsonify({"error": "student_number_exists"}), 409
            if session.scalar(select(Student).where(Student.email == email)):
                return jsonify({"error": "email_exists"}), 409

            student = Student(
                student_number=student_number,
                first_name=str(data["first_name"]).strip(),
                last_name=str(data["last_name"]).strip(),
                email=email,
            )
            session.add(student)
            session.commit()
            return jsonify(_student_json(student)), 201

    @app.get("/api/students")
    def list_students():
        page, per_page = _pagination()
        query = select(Student)
        q = request.args.get("q", "").strip()
        if q:
            pattern = f"%{q}%"
            query = query.where(or_(
                Student.student_number.ilike(pattern),
                Student.first_name.ilike(pattern),
                Student.last_name.ilike(pattern),
                Student.email.ilike(pattern),
            ))
        query = query.order_by(Student.last_name, Student.first_name)

        with new_session() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = list(session.scalars(query.offset((page - 1) * per_page).limit(per_page)))
            return jsonify({
                "items": [_student_json(s) for s in rows],
                "page": page,
                "per_page": per_page,
                "total": total,
            })

    @app.get("/api/students/<int:student_id>")
    def get_student(student_id: int):
        with new_session() as session:
            student = session.get(Student, student_id)
            if student is None:
                return jsonify({"error": "student_not_found"}), 404
            return jsonify(_student_json(student))

    @app.patch("/api/students/<int:student_id>")
    def update_student(student_id: int):
        data = request.get_json(force=True)
        allowed = {"student_number", "first_name", "last_name", "email"}
        if not any(k in data for k in allowed):
            return jsonify({"error": "no_updatable_fields"}), 400

        with new_session() as session:
            student = session.get(Student, student_id)
            if student is None:
                return jsonify({"error": "student_not_found"}), 404

            if "student_number" in data:
                value = str(data["student_number"]).strip()
                if not value:
                    return jsonify({"error": "validation_error"}), 400
                duplicate = session.scalar(select(Student).where(
                    Student.student_number == value,
                    Student.id != student_id,
                ))
                if duplicate:
                    return jsonify({"error": "student_number_exists"}), 409
                student.student_number = value

            if "email" in data:
                value = str(data["email"]).strip().lower()
                if not value:
                    return jsonify({"error": "validation_error"}), 400
                duplicate = session.scalar(select(Student).where(
                    Student.email == value,
                    Student.id != student_id,
                ))
                if duplicate:
                    return jsonify({"error": "email_exists"}), 409
                student.email = value

            for field in ("first_name", "last_name"):
                if field in data:
                    value = str(data[field]).strip()
                    if not value:
                        return jsonify({"error": "validation_error"}), 400
                    setattr(student, field, value)

            session.commit()
            return jsonify(_student_json(student))

    @app.delete("/api/students/<int:student_id>")
    def delete_student(student_id: int):
        with new_session() as session:
            student = session.get(Student, student_id)
            if student is None:
                return jsonify({"error": "student_not_found"}), 404
            session.delete(student)
            session.commit()
            return "", 204

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
            code = str(data["code"]).strip().upper()
            if session.scalar(select(Course).where(Course.code == code)):
                return jsonify({"error": "course_code_exists"}), 409

            course = Course(
                code=code,
                title=str(data["title"]).strip(),
                description=data.get("description"),
                credits=credits,
                capacity=capacity,
            )
            session.add(course)
            session.commit()
            return jsonify(_course_json(course)), 201

    @app.get("/api/courses")
    def list_courses():
        page, per_page = _pagination()
        query = select(Course)
        q = request.args.get("q", "").strip()
        if q:
            pattern = f"%{q}%"
            query = query.where(or_(Course.code.ilike(pattern), Course.title.ilike(pattern)))
        query = query.order_by(Course.code)

        with new_session() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = list(session.scalars(query.offset((page - 1) * per_page).limit(per_page)))
            return jsonify({
                "items": [_course_json(c) for c in rows],
                "page": page,
                "per_page": per_page,
                "total": total,
            })

    @app.get("/api/courses/<int:course_id>")
    def get_course(course_id: int):
        with new_session() as session:
            course = session.get(Course, course_id)
            if course is None:
                return jsonify({"error": "course_not_found"}), 404
            return jsonify(_course_json(course))

    @app.patch("/api/courses/<int:course_id>")
    def update_course(course_id: int):
        data = request.get_json(force=True)
        allowed = {"code", "title", "description", "credits", "capacity"}
        if not any(k in data for k in allowed):
            return jsonify({"error": "no_updatable_fields"}), 400

        with new_session() as session:
            course = session.get(Course, course_id)
            if course is None:
                return jsonify({"error": "course_not_found"}), 404

            if "code" in data:
                code = str(data["code"]).strip().upper()
                if not code:
                    return jsonify({"error": "validation_error"}), 400
                duplicate = session.scalar(select(Course).where(Course.code == code, Course.id != course_id))
                if duplicate:
                    return jsonify({"error": "course_code_exists"}), 409
                course.code = code

            if "title" in data:
                title = str(data["title"]).strip()
                if not title:
                    return jsonify({"error": "validation_error"}), 400
                course.title = title

            if "description" in data:
                course.description = data["description"]

            for field in ("credits", "capacity"):
                if field in data:
                    try:
                        value = int(data[field])
                    except (TypeError, ValueError):
                        return jsonify({"error": "invalid_numeric_field"}), 400
                    if value <= 0:
                        return jsonify({"error": "invalid_course_configuration"}), 400
                    if field == "capacity":
                        active_count = session.scalar(select(func.count()).select_from(Enrollment).where(
                            Enrollment.course_id == course_id,
                            Enrollment.status == "active",
                        )) or 0
                        if value < active_count:
                            return jsonify({"error": "capacity_below_active_enrollment"}), 409
                    setattr(course, field, value)

            session.commit()
            return jsonify(_course_json(course))

    @app.delete("/api/courses/<int:course_id>")
    def delete_course(course_id: int):
        with new_session() as session:
            course = session.get(Course, course_id)
            if course is None:
                return jsonify({"error": "course_not_found"}), 404
            session.delete(course)
            session.commit()
            return "", 204

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

            existing = session.scalar(select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            ))
            if existing and existing.status == "active":
                return jsonify({"error": "already_enrolled"}), 409

            active_count = session.scalar(select(func.count()).select_from(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.status == "active",
            )) or 0
            if active_count >= course.capacity:
                return jsonify({"error": "course_full"}), 409

            if existing:
                existing.status = "active"
                existing.dropped_at = None
                existing.enrolled_at = datetime.now(timezone.utc)
                enrollment = existing
            else:
                enrollment = Enrollment(student_id=student_id, course_id=course_id)
                session.add(enrollment)

            session.commit()
            return jsonify(_enrollment_json(enrollment)), 201

    @app.get("/api/enrollments")
    def list_enrollments():
        page, per_page = _pagination()
        query = select(Enrollment)

        status = request.args.get("status")
        if status:
            if status not in {"active", "dropped"}:
                return jsonify({"error": "invalid_status"}), 400
            query = query.where(Enrollment.status == status)

        for arg, column in (("student_id", Enrollment.student_id), ("course_id", Enrollment.course_id)):
            value = request.args.get(arg)
            if value is not None:
                try:
                    query = query.where(column == int(value))
                except ValueError:
                    return jsonify({"error": f"invalid_{arg}"}), 400

        query = query.order_by(Enrollment.id)
        with new_session() as session:
            total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = list(session.scalars(query.offset((page - 1) * per_page).limit(per_page)))
            return jsonify({
                "items": [_enrollment_json(e) for e in rows],
                "page": page,
                "per_page": per_page,
                "total": total,
            })

    @app.get("/api/enrollments/<int:enrollment_id>")
    def get_enrollment(enrollment_id: int):
        with new_session() as session:
            enrollment = session.get(Enrollment, enrollment_id)
            if enrollment is None:
                return jsonify({"error": "enrollment_not_found"}), 404
            return jsonify(_enrollment_json(enrollment))

    @app.delete("/api/enrollments/<int:enrollment_id>")
    def drop_enrollment(enrollment_id: int):
        with new_session() as session:
            enrollment = session.get(Enrollment, enrollment_id)
            if enrollment is None:
                return jsonify({"error": "enrollment_not_found"}), 404
            if enrollment.status == "dropped":
                return jsonify({"error": "already_dropped"}), 409
            enrollment.status = "dropped"
            enrollment.dropped_at = datetime.now(timezone.utc)
            session.commit()
            return jsonify(_enrollment_json(enrollment))

    @app.get("/api/students/<int:student_id>/courses")
    def student_courses(student_id: int):
        with new_session() as session:
            if session.get(Student, student_id) is None:
                return jsonify({"error": "student_not_found"}), 404
            rows = list(session.scalars(
                select(Course)
                .join(Enrollment, Enrollment.course_id == Course.id)
                .where(Enrollment.student_id == student_id, Enrollment.status == "active")
                .order_by(Course.code)
            ))
            return jsonify({"items": [_course_json(c) for c in rows]})

    @app.get("/api/courses/<int:course_id>/students")
    def course_students(course_id: int):
        with new_session() as session:
            if session.get(Course, course_id) is None:
                return jsonify({"error": "course_not_found"}), 404
            rows = list(session.scalars(
                select(Student)
                .join(Enrollment, Enrollment.student_id == Student.id)
                .where(Enrollment.course_id == course_id, Enrollment.status == "active")
                .order_by(Student.last_name, Student.first_name)
            ))
            return jsonify({"items": [_student_json(s) for s in rows]})

    @app.cli.command("init-db")
    def init_db():
        Base.metadata.create_all(get_engine())
        print("Database initialized.")

    return app
