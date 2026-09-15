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
| Course-level enrollment | Implemented | create/list/fetch/drop/reactivate compatibility workflow |
| Student-to-course lookup | Implemented | `GET /api/students/<id>/courses` |
| Course-to-student lookup | Implemented | `GET /api/courses/<id>/students` |
| Academic terms | Implemented | term dates + registration-window dates |
| Course sections | Implemented | term/course linkage, instructor, capacity, meeting schedule, location |
| Shared registration service | Implemented | `app/registration_service.py` centralizes enhanced section-registration/waitlist policy |
| Server-controlled registration policy date | Implemented | client-supplied dates cannot bypass registration-window policy in enhanced runtime |
| Section-level capacity | Implemented | active section enrollments checked against section capacity |
| Transactional final-seat guard | Implemented | PostgreSQL row lock + transactional recount before active seat commit |
| PostgreSQL concurrency integration test | Implemented and passing | two concurrent transactions compete for one seat; exactly one commits |
| Prerequisites | Implemented | course-to-required-course relationships |
| Course completion records | Implemented | used for prerequisite evaluation |
| Registration-window enforcement | Implemented | secure runtime evaluates server policy date against configured term window |
| Same-course duplicate prevention in term | Implemented | prevents active registration in another section of the same course/term |
| Schedule-conflict detection | Implemented | meeting-day and overlapping-time checks |
| Section drop/reactivation | Implemented | lifecycle handled through shared registration service |
| Waitlists | Implemented | waiting/promoted/cancelled lifecycle |
| FIFO waitlist ordering | Implemented | ordered by join time/id |
| Promotion-time policy revalidation | Implemented | window, prerequisites, course duplication and schedule conflicts are rechecked |
| Automatic waitlist promotion | Implemented | first currently eligible student promoted after a seat opens |
| Atomic drop + promotion | Implemented | one SQLAlchemy session/commit boundary; rollback test covers failure semantics |
| Waitlist cancellation/rejoin | Implemented | cancelled entry can rejoin when current policy permits |
| Authentication | Implemented | password hashing + time-limited signed bearer tokens |
| Account-wide bearer-token revocation | Implemented | token-version invalidation through `/api/auth/logout-all` |
| Password change with token invalidation | Implemented | successful password change revokes previously issued tokens |
| One-time admin bootstrap | Implemented | first account only |
| Role-based authorization | Implemented | `student`, `registrar`, `admin` |
| Student ownership boundary | Implemented and tested | secure runtime restricts registration/waitlist create/list operations to linked student |
| Admin account management | Implemented | create/list user accounts |
| Structured audit logging | Implemented | mutating HTTP requests persisted without request-body capture |
| Audit request IDs | Implemented | `X-Request-ID` response header + persisted request ID |
| Audit log retrieval | Implemented | `GET /api/audit-events`; admin only |
| Rate limiting | Implemented | Flask-Limiter global default + stricter login/bootstrap limits |
| Shared rate-limit backend configuration | Supported | configurable through `RATELIMIT_STORAGE_URI`; memory backend is default for dev/tests |
| Alembic migrations | Implemented | baseline plus incremental audit/token-revocation revisions |
| Migration CI verification | Implemented and passing | upgrade → downgrade → upgrade cycle before tests |
| PostgreSQL runtime support | Implemented | `psycopg` + URL normalization + connection pre-ping |
| OpenAPI 3.1 contract | Implemented | `docs/openapi.yaml` |
| Interactive API documentation | Implemented | Swagger UI at `/docs`, spec at `/openapi.yaml` |
| Prometheus observability endpoint | Implemented and passing | `/metrics` exports low-cardinality request counters and latency histograms |
| Containerized production runtime | Implemented | Dockerfile + Gunicorn |
| Local PostgreSQL deployment stack | Implemented | `compose.yaml` with PostgreSQL service and health checks |
| Production container CI build | Implemented and passing | image is built after migrations/tests |
| Database initialization CLI | Implemented | `flask --app run.py init-db` |
| Automated tests | Implemented | CRUD, policy rules, waitlists, atomic rollback, auth/RBAC, ownership, revocation, capacity guard, audit, rate limiting, OpenAPI, metrics, PostgreSQL concurrency, and regression behavior |
| GitHub Actions CI | Implemented | migrations, unit/API tests, real PostgreSQL concurrency integration, and production image build |

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
- foreign-key relationships across students, courses, terms, sections, completions, enrollments, waitlists, users, and audit events

## Current architecture status

| Area | Status |
|---|---|
| Reconstructed core Flask routes | Implemented in `app/__init__.py` |
| Shared enhanced registration policy/service | Implemented in `app/registration_service.py` |
| SQLAlchemy database/session configuration | Separated in `app/db.py` |
| Domain models | Separated in `app/models.py` |
| Waitlist HTTP workflow | Separated in `app/waitlist.py` and backed by shared service |
| Transactional capacity guard | Separated in `app/capacity.py` |
| Authentication/RBAC and token revocation | Separated in `app/auth.py` |
| Structured audit logging | Separated in `app/audit.py` |
| Rate limiting | Separated in `app/rate_limit.py` |
| Prometheus observability | Separated in `app/observability.py` |
| Interactive API docs | Separated in `app/docs.py` |
| Secure application composition | Separated in `app/secure.py` |
| Schema migrations | Separated under `migrations/` |
| Machine-readable API contract | `docs/openapi.yaml` |
| Container/deployment configuration | `Dockerfile`, `.dockerignore`, `compose.yaml` |
| General repository/data-access layer | Not implemented; intentionally lower priority at current scale |

## Registration transaction scope

The enhanced secure runtime uses the shared registration service for section mutation and waitlist policy. The service receives a caller-owned SQLAlchemy session and leaves commit/rollback to the HTTP adapter.

For a drop that may free a waitlist seat, the sequence is:

```text
BEGIN
mark current enrollment dropped
flush seat release
re-evaluate waitlist candidates under current server policy date
create/reactivate eligible promoted enrollment if one exists
mark waitlist row promoted
COMMIT
```

The intermediate flush is not a commit. An automated rollback test injects a promotion failure after the drop is flushed and verifies that rollback restores the original active enrollment and leaves the waitlist unchanged.

Promotion re-checks the registration window, prerequisites, same-course rule, and schedule conflicts. If the window has closed, no promotion occurs.

## Concurrency scope

The enhanced runtime registers a SQLAlchemy transaction guard for active section-seat changes. On PostgreSQL, the guard locks the target section row with `SELECT ... FOR UPDATE`, recounts active section enrollments inside the transaction, and rejects an over-capacity transaction.

The strategy is exercised in CI against a real PostgreSQL 17 service: two independent concurrent transactions compete for a capacity-one section, one commit succeeds, the other is rejected, and the final active-enrollment count remains exactly one.

This is legitimate integration-level validation of the final-seat locking strategy. It should not be described as a high-volume production load benchmark.

## Compatibility boundary

The reconstructed core factory in `app/__init__.py` retains its original inline section-enrollment handlers for historical/reconstruction compatibility. The canonical enhanced runtime (`app.secure:create_app`, used by `run.py`) installs the shared service-backed mutation handlers while preserving the same URL rules.

Therefore, claims about server-controlled policy time, atomic drop/promotion, and centralized registration rules apply to the **enhanced secure runtime**, not to an isolated direct call to the reconstruction-only core factory without enhanced composition.

## Remaining production / architecture gaps

| Capability | Status |
|---|---|
| High-volume PostgreSQL load/stress benchmark | Not implemented |
| Password reset / recovery workflow | Not implemented |
| Per-token selective revocation / refresh-token architecture | Not implemented |
| Shared production rate-limit backend deployment | Not configured in repository |
| External Prometheus/Grafana deployment | Not configured in repository |
| Centralized log aggregation | Not configured in repository |
| Managed deployment target / infrastructure-as-code | Not implemented |
| External secret-management integration | Not implemented |
| General repository/data-access layer | Not implemented; not currently required for domain correctness |
| `seed-db` CLI command | Not implemented |
| Prerequisite-cycle detection | Not implemented |
| Canonical normalized meeting-day persistence | Not implemented |

## Provenance classification

The current repository intentionally mixes reconstruction and new portfolio engineering, but does not blur the distinction.

| Classification | Scope |
|---|---|
| **RECOVERED** | Broad historical concept: Python + Flask + SQL + student/course/registration + database/REST coursework |
| **RECONSTRUCTED** | Initial student/course/enrollment Flask API built faithfully from the recovered high-level project concept |
| **ENHANCED** | CRUD expansion, terms/sections/prerequisites/completions, shared registration service, server policy clock, schedule/window rules, waitlists, atomic drop/promotion, authentication/RBAC, ownership enforcement, token revocation, migrations, PostgreSQL support, transactional capacity protection, PostgreSQL concurrency testing, audit logging, rate limiting, OpenAPI/Swagger documentation, Prometheus metrics, containerization, expanded tests, and CI |
| **UNVERIFIED** | Any exact historical source implementation, exact historical endpoint set, exact historical database engine, or exact richer behavior not supported by recovered artifacts |

The public README should describe enhanced features as current portfolio functionality, not as recovered historical coursework.
