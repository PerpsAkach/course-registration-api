# Provenance

This repository preserves an explicit boundary between recovered historical evidence, reconstructed functionality, and new portfolio engineering.

## RECOVERED

Available historical evidence supports the broad coursework/project context:

- Python
- Flask
- SQL / relational database work
- student, course, and registration concepts
- CRUD / REST-style functionality

The recovered evidence does **not** prove the exact historical source tree, endpoint paths, schema, database engine, authentication design, or the richer registration workflows now present in this repository.

## RECONSTRUCTED

The initial public implementation was reconstructed from that broad historical concept and included:

- Flask application structure
- SQLAlchemy relational student/course/enrollment model
- student and course creation/listing
- course-level enrollment creation/reactivation
- duplicate-enrollment prevention
- basic capacity validation
- database constraints
- pytest API tests

This reconstruction should not be described as byte-for-byte recovered historical source.

## ENHANCED

The following capabilities were subsequently built as new portfolio engineering and are therefore **ENHANCED**, not historical claims:

- full student and course CRUD
- search and pagination
- academic terms and registration windows
- course sections and meeting schedules
- prerequisite relationships
- course-completion tracking
- section-level registration
- shared registration-policy/service layer for the enhanced runtime
- server-controlled registration policy date
- duplicate-course prevention within a term
- schedule-conflict detection
- section-level capacity enforcement
- transactional PostgreSQL row locking for final-seat allocation
- real PostgreSQL concurrency integration testing for final-seat protection
- section drop/reactivation
- FIFO waitlists
- automatic waitlist promotion
- promotion-time revalidation of registration-window, prerequisite, duplicate-course and schedule-conflict rules
- atomic drop + waitlist-promotion transaction coordination
- rollback testing for failed promotion workflows
- waitlist cancellation and policy-controlled rejoin
- authentication and time-limited bearer tokens
- account-wide bearer-token revocation
- password change with prior-token invalidation
- `student`, `registrar`, and `admin` RBAC
- secure-runtime student ownership tests for section registration and waitlists
- structured request audit logging and request IDs
- admin-only audit-event retrieval
- configurable API rate limiting
- Prometheus-compatible request metrics and latency histograms
- expanded automated testing
- GitHub Actions CI
- Alembic schema migrations
- PostgreSQL driver/runtime support
- OpenAPI 3.1 documentation
- interactive Swagger UI
- Docker/Gunicorn production runtime
- local Docker Compose PostgreSQL deployment stack
- architecture and implementation-status documentation

## Compatibility boundary

The reconstructed core application remains in `app/__init__.py`. The canonical enhanced runtime used by `run.py` is composed through `app.secure:create_app`, which installs the enhanced registration service for section-mutation and waitlist policy.

This means modern service-layer behavior—such as server-controlled registration time and atomic drop/promotion—must be described as **enhanced runtime behavior**, not as recovered historical behavior.

## CURRENT IMPLEMENTATION STATUS

For the detailed capability matrix and remaining production gaps, see [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md).

The current public implementation should be presented as a **reconstructed and substantially enhanced portfolio backend**.

## UNVERIFIED

Unless stronger source artifacts are recovered, the following remain unverified historical details:

- exact original source bytes
- exact original endpoint set
- exact original database engine
- exact original schema columns and constraints
- exact original authentication or authorization behavior
- whether terms, sections, prerequisites, waitlists, schedule validation, service-layer registration policy, migrations, PostgreSQL support, concurrency controls, audit logging, rate limiting, observability, or deployment tooling existed in the historical coursework

Portfolio descriptions should continue to distinguish historical evidence from modern reconstruction and enhancement.
