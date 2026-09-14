# Implementation Status

This document separates the current public implementation from historical evidence and remaining future work.

## Current public implementation

| Capability | Status | Evidence / behavior |
|---|---|---|
| Health endpoint | Implemented | `GET /api/health` |
| Student CRUD | Implemented | create, list, fetch, patch, delete |
| Course CRUD | Implemented | create, list, fetch, patch, delete |
| Search | Implemented | `q` search on student/course collections |
| Pagination | Implemented | `page` / `per_page` where supported by core collection routes |
| Course-level enrollment | Implemented | create/list/fetch/drop/reactivate |
| Student-to-course lookup | Implemented | `GET /api/students/<id>/courses` |
| Course-to-student lookup | Implemented | `GET /api/courses/<id>/students` |
| Academic terms | Implemented | term dates + registration-window dates |
| Course sections | Implemented | term/course linkage, instructor, capacity, meeting schedule, location |
| Section-level capacity | Implemented | active section enrollments checked against section capacity |
| Transactional final-seat guard | Implemented | PostgreSQL row lock + transactional recount before active seat commit |
| Prerequisites | Implemented | course-to-required-course relationships |
| Course completion records | Implemented | used for prerequisite evaluation |
| Registration-window enforcement | Implemented | rejects section registration outside configured window |
| Same-course duplicate prevention in term | Implemented | prevents active registration in another section of the same course/term |
| Schedule-conflict detection | Implemented | meeting-day and overlapping-time checks |
| Section drop/reactivation | Implemented | lifecycle handled through section enrollments |
| Waitlists | Implemented | waiting/promoted/cancelled lifecycle |
| FIFO waitlist ordering | Implemented | ordered by join time/id |
| Automatic waitlist promotion | Implemented | next eligible student promoted after a seat opens |
| Authentication | Implemented | password hashing + time-limited signed bearer token |
| One-time admin bootstrap | Implemented | first account only |
| Role-based authorization | Implemented | `student`, `registrar`, `admin` |
| Student ownership boundary | Implemented | student accounts restricted to own registration/waitlist resources plus catalog reads |
| Admin account management | Implemented | create/list user accounts |
| Alembic migrations | Implemented | baseline migration + migration environment |
| Migration CI verification | Implemented and passing | upgrade → downgrade → upgrade cycle before tests |
| PostgreSQL runtime support | Implemented | `psycopg` + URL normalization + connection pre-ping |
| OpenAPI 3.1 contract | Implemented | `docs/openapi.yaml` |
| OpenAPI structure test | Implemented | YAML parse + core path/security assertions |
| Database initialization CLI | Implemented | `flask --app run.py init-db` |
| Automated tests | Implemented | CRUD, registration rules, waitlists, auth/RBAC, capacity guard, OpenAPI, and regression behavior |
| GitHub Actions CI | Implemented and passing | `.github/workflows/ci.yml` |

## Relational integrity currently represented

The current model includes application and/or SQL-level controls for:

- unique student numbers and student emails
- unique course codes
- positive course credits and capacities
- unique course/term/section-number combinations
- unique student/course relationships in the reconstructed course-level enrollment model
- unique student/section enrollment relationships
- unique student/section waitlist relationships
- prerequisite self-reference prevention
- controlled enrollment and waitlist status values
- foreign-key relationships across students, courses, terms, sections, completions, enrollments, and waitlists

## Current architecture status

| Area | Status |
|---|---|
| Core Flask routes | Implemented in `app/__init__.py` |
| SQLAlchemy database/session configuration | Separated in `app/db.py` |
| Domain models | Separated in `app/models.py` |
| Waitlist workflow | Separated in `app/waitlist.py` |
| Transactional capacity guard | Separated in `app/capacity.py` |
| Authentication/RBAC | Separated in `app/auth.py` |
| Secure application composition | Separated in `app/secure.py` |
| Schema migrations | Separated under `migrations/` |
| Machine-readable API contract | `docs/openapi.yaml` |
| Full service layer | Not yet implemented |
| Full repository/data-access layer | Not yet implemented |

## Concurrency scope

The enhanced secure runtime registers a SQLAlchemy transaction guard for active section-seat changes. On PostgreSQL, the guard locks the target section row with `SELECT ... FOR UPDATE`, recounts active section enrollments inside the transaction, and rejects an over-capacity transaction.

This is the production concurrency strategy for final-seat allocation. SQLite is still the default development/test database and does not provide PostgreSQL-equivalent row-level `FOR UPDATE` behavior. A real multi-worker PostgreSQL load/integration test remains future work.

## Not currently implemented / production gaps

| Capability | Status |
|---|---|
| Real PostgreSQL multi-worker concurrency integration/load test | Not implemented |
| Password reset / recovery | Not implemented |
| Explicit bearer-token revocation | Not implemented |
| Rate limiting | Not implemented |
| Structured audit log | Not implemented |
| Interactive Swagger UI / generated docs site | Not implemented |
| Production observability / metrics | Not implemented |
| Deployment infrastructure | Not implemented |
| Secret-management integration | Not implemented |
| Full service/repository architecture | Not implemented |
| `seed-db` CLI command | Not implemented |

## Provenance classification

The current repository intentionally mixes reconstruction and new portfolio engineering, but does not blur the distinction.

| Classification | Scope |
|---|---|
| **RECOVERED** | Broad historical concept: Python + Flask + SQL + student/course/registration + database/REST coursework |
| **RECONSTRUCTED** | Initial student/course/enrollment Flask API built faithfully from the recovered high-level project concept |
| **ENHANCED** | CRUD expansion, search, pagination, terms, sections, prerequisites, completion tracking, registration rules, schedule conflicts, waitlists, automatic promotion, authentication, RBAC, migrations, PostgreSQL support, transactional capacity protection, OpenAPI documentation, expanded tests, and CI |
| **UNVERIFIED** | Any exact historical source implementation, exact historical endpoint set, exact historical database engine, or exact richer behavior not supported by recovered artifacts |

The public README should describe enhanced features as current portfolio functionality, not as recovered historical coursework.
