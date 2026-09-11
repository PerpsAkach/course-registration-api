# Provenance

- **RECOVERED:** broad historical coursework domain only — Python, Flask, SQL, relational student/course/registration concepts, CRUD/REST-style functionality.
- **RECONSTRUCTED:** the current Flask + SQLAlchemy API implementation in this repository.
- **ENHANCED:** explicit relational constraints, active/dropped enrollment state, capacity validation, duplicate-enrollment prevention, structured HTTP errors, and pytest-based API tests.
- **CURRENTLY IMPLEMENTED:** health; create/list students; create/list courses; create/reactivate enrollments; duplicate checks; capacity checks; `init-db`; relational constraints.
- **NOT CURRENTLY IMPLEMENTED:** full PATCH/DELETE CRUD, search, pagination, service/repository layering, `seed-db`, authentication/authorization, sections/semesters, prerequisites, waitlists, registration windows, or concurrency-safe seat allocation.
- **UNVERIFIED:** exact historical source bytes, endpoint paths, database engine, schema columns, authentication model, and whether the broader planned features existed in the original coursework implementation.

The portfolio documentation should not present reconstructed or planned functionality as historical fact unless a supporting artifact is recovered.