# Course Registration REST API

Flask REST API for managing students, courses, and enrollments using a normalized relational data model.

## What it demonstrates

- Flask backend development
- REST API design
- SQL / relational modeling
- Many-to-many relationships
- CRUD operations
- Database constraints and transactions
- Duplicate-registration prevention
- Course-capacity validation
- Search, pagination, and automated tests

## Domain model

```text
Student 1 ---- * Enrollment * ---- 1 Course
```

## Core endpoints

```text
GET/POST   /api/students
GET/PATCH/DELETE /api/students/<id>
GET/POST   /api/courses
GET/PATCH/DELETE /api/courses/<id>
GET/POST   /api/enrollments
GET/DELETE /api/enrollments/<id>
```

## Run

```bash
pip install -r requirements.txt
flask --app run.py init-db
flask --app run.py seed-db
flask --app run.py run --debug
```

The historical project is recovered at the Flask/SQL/course-registration architecture level; the current repository is a hardened reconstruction. See `PROVENANCE.md`.
