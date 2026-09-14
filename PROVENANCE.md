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
- duplicate-course prevention within a term
- schedule-conflict detection
- section-level capacity enforcement
- transactional PostgreSQL row locking for final-seat allocation
- section drop/reactivation
- FIFO waitlists
- automatic waitlist promotion
- authentication and time-limited bearer tokens
- `student`, `registrar`, and `admin` RBAC
- student ownership boundaries
- structured request audit logging and request IDs
- admin-only audit-event retrieval
- configurable API rate limiting
- expanded automated testing
- GitHub Actions CI
- Alembic schema migrations
- PostgreSQL driver/runtime support
- OpenAPI 3.1 documentation

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
- whether terms, sections, prerequisites, waitlists, schedule validation, migrations, PostgreSQL support, concurrency controls, audit logging, or rate limiting existed in the historical coursework

Portfolio descriptions should continue to distinguish historical evidence from modern reconstruction and enhancement.
