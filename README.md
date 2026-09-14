# Course Registration REST API

> Flask + SQLAlchemy registration backend with academic terms, course sections, prerequisites, schedule validation, waitlists, authentication, role-based authorization, migrations, PostgreSQL support, transactional capacity protection, OpenAPI documentation, and automated CI.

[![CI](https://github.com/PerpsAkach/course-registration-api/actions/workflows/ci.yml/badge.svg)](https://github.com/PerpsAkach/course-registration-api/actions/workflows/ci.yml)
[![Portfolio](https://img.shields.io/badge/Portfolio-perpsakach.github.io-d7ff5f?style=flat-square&labelColor=11151a)](https://perpsakach.github.io/)
![Flask](https://img.shields.io/badge/Flask-REST%20API-111827?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-2563eb?style=flat-square)
![Testing](https://img.shields.io/badge/Testing-pytest-0f766e?style=flat-square)
![Status](https://img.shields.io/badge/Status-Reconstructed%20%2B%20Enhanced-6b7280?style=flat-square)

## Overview

This repository started as a portfolio reconstruction of a course-registration/database-systems project and has since been deliberately enhanced into a substantially richer backend system.

The current implementation models the real registration domain rather than only a student-to-course join table. It includes students, courses, academic terms, sections, meeting schedules, prerequisites, course completions, section registrations, waitlists, authentication, role-based access control, schema migrations, PostgreSQL runtime support, and an OpenAPI contract.

The public code is therefore best described as:

**Recovered project concept → reconstructed core → enhanced portfolio backend**

The provenance boundary remains explicit: the richer features documented below are current portfolio enhancements, not claims about the exact historical coursework implementation.

## What is implemented

The current API supports:

- student and course CRUD
- search and pagination
- academic terms and registration windows
- course sections with instructor, location, meeting days, times, and section-level capacity
- prerequisite relationships
- completed-course records used for prerequisite evaluation
- section registration with registration-window enforcement
- duplicate-course prevention within a term
- schedule-conflict detection
- section-level capacity enforcement
- transactional final-seat protection using PostgreSQL row locking
- drop/reactivation behavior
- FIFO waitlists
- automatic promotion of the next eligible waitlisted student when a seat opens
- bearer-token authentication
- `student`, `registrar`, and `admin` roles
- student self-service authorization boundaries
- admin-managed user creation
- Alembic migrations
- PostgreSQL driver/runtime support
- OpenAPI 3.1 documentation in `docs/openapi.yaml`
- pytest coverage and GitHub Actions CI

## Architecture

```mermaid
flowchart LR
    Client[API Client] --> Runtime[Secure Flask Application]
    Runtime --> Auth[Authentication + RBAC]
    Runtime --> Core[Core Registration Routes]
    Runtime --> Wait[Waitlist Workflow]
    Runtime --> Capacity[Transactional Capacity Guard]
    Auth --> DB[(SQLAlchemy / Relational DB)]
    Core --> DB
    Wait --> DB
    Capacity --> DB

    Core --> Rules[Registration Rules]
    Rules --> P[Prerequisites]
    Rules --> W[Registration Windows]
    Rules --> C[Capacity]
    Rules --> S[Schedule Conflicts]
```

Runtime composition is handled by `app/secure.py`. It builds the core Flask application, registers waitlist behavior, enables authentication/authorization, and activates the transactional capacity guard. The executable entry point in `run.py` uses this secure application factory.

### Main code organization

```text
app/
├── __init__.py   # core REST endpoints and registration rules
├── auth.py       # authentication, user accounts, RBAC
├── capacity.py   # transactional section-capacity guard
├── db.py         # SQLAlchemy engine/session configuration
├── models.py     # academic/registration relational model
├── secure.py     # production-oriented application composition
└── waitlist.py   # waitlist lifecycle and automatic promotion

migrations/       # Alembic migration environment and versions
docs/openapi.yaml # OpenAPI 3.1 API contract
```

The project is not yet split into a full route/service/repository package hierarchy. That remains a possible architectural refinement, but the current separation already isolates database configuration, authentication, waitlisting, transactional capacity enforcement, application composition, migrations, and the central domain model.

## Domain model

```mermaid
erDiagram
    STUDENT ||--o{ SECTION_ENROLLMENT : registers
    SECTION ||--o{ SECTION_ENROLLMENT : receives
    STUDENT ||--o{ COURSE_COMPLETION : completes
    COURSE ||--o{ COURSE_COMPLETION : records
    COURSE ||--o{ SECTION : offered_as
    ACADEMIC_TERM ||--o{ SECTION : contains
    COURSE ||--o{ PREREQUISITE : requires
    COURSE ||--o{ PREREQUISITE : prerequisite_course
    STUDENT ||--o{ WAITLIST_ENTRY : joins
    SECTION ||--o{ WAITLIST_ENTRY : queues
    STUDENT ||--o| USER_ACCOUNT : authenticates_as

    STUDENT {
        int id PK
        string student_number UK
        string first_name
        string last_name
        string email UK
    }

    COURSE {
        int id PK
        string code UK
        string title
        int credits
        int capacity
    }

    ACADEMIC_TERM {
        int id PK
        string name
        int year
        date starts_on
        date ends_on
        date registration_opens_on
        date registration_closes_on
    }

    SECTION {
        int id PK
        int course_id FK
        int term_id FK
        string section_number
        int capacity
        string instructor
        string meeting_days
        time starts_at
        time ends_at
        string location
    }

    SECTION_ENROLLMENT {
        int id PK
        int student_id FK
        int section_id FK
        string status
        datetime enrolled_at
        datetime dropped_at
    }

    WAITLIST_ENTRY {
        int id PK
        int student_id FK
        int section_id FK
        string status
        datetime joined_at
        datetime promoted_at
        datetime cancelled_at
    }
```

The original course-level `Enrollment` model remains available as part of the reconstruction. The enhanced registration workflow uses `SectionEnrollment`, which is the more realistic unit for term-based registration.

## Registration decision flow

```mermaid
flowchart TD
    A[Registration request] --> B{Registration window open?}
    B -- No --> X1[409 registration_closed]
    B -- Yes --> C{Already active in this section?}
    C -- Yes --> X2[409 already_enrolled]
    C -- No --> D{Prerequisites complete?}
    D -- No --> X3[409 prerequisites_not_met]
    D -- Yes --> E{Same course already registered this term?}
    E -- Yes --> X4[409 already_registered_for_course]
    E -- No --> F{Schedule conflict?}
    F -- Yes --> X5[409 schedule_conflict]
    F -- No --> G{Seat available?}
    G -- Yes --> H[Create or reactivate section enrollment]
    G -- No --> X6[409 section_full]
    H --> I[Transactional capacity guard]
    I --> J[201 Created]
```

When a section is full, an eligible student may join its waitlist. Dropping an active section enrollment triggers FIFO evaluation of waiting students; the first student who still satisfies the registration rules is automatically promoted.

### Final-seat concurrency protection

The route-level capacity check provides a fast domain response, but production PostgreSQL deployments also activate `app/capacity.py`. Before an active section seat is committed, the guard locks the target `sections` row with `SELECT ... FOR UPDATE`, recounts active section enrollments inside the transaction, and rejects an over-capacity transaction with `409 section_full`.

That row lock serializes competing registrations for the same section on PostgreSQL. SQLite remains useful for development and tests, but it does not provide PostgreSQL-equivalent row-level `FOR UPDATE` semantics, so production concurrency claims are scoped to databases that support the locking strategy.

## Authentication and authorization

The secure runtime protects API routes by default.

Roles:

| Role | Intended access |
|---|---|
| `student` | Read catalog data and operate on the student's own registration/waitlist resources |
| `registrar` | Manage operational registration and catalog resources |
| `admin` | Registrar capabilities plus user/account administration |

Authentication uses password hashing plus time-limited signed bearer tokens. The current token lifetime is eight hours.

### First-time bootstrap

Create the first administrator once:

```bash
curl -X POST http://127.0.0.1:5000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.edu",
    "password": "ChangeThisStrongPassword"
  }'
```

The bootstrap endpoint refuses subsequent bootstrap attempts once an account exists.

### Login

```bash
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "ChangeThisStrongPassword"
  }'
```

Use the returned token as:

```bash
-H "Authorization: Bearer <token>"
```

For deployment, set a strong application secret instead of relying on the development fallback:

```bash
export APP_SECRET_KEY="replace-with-a-long-random-secret"
```

## Endpoint matrix

### Public / authentication

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/bootstrap` | One-time first-admin creation |
| POST | `/api/auth/login` | Authenticate and receive bearer token |
| GET | `/api/auth/me` | Current authenticated account |
| POST | `/api/auth/users` | Create account; admin only |
| GET | `/api/auth/users` | List accounts; admin only |

### Students and courses

| Method | Endpoint |
|---|---|
| POST / GET | `/api/students` |
| GET / PATCH / DELETE | `/api/students/<student_id>` |
| GET | `/api/students/<student_id>/courses` |
| GET | `/api/students/<student_id>/completions` |
| POST / GET | `/api/courses` |
| GET / PATCH / DELETE | `/api/courses/<course_id>` |
| GET | `/api/courses/<course_id>/students` |
| POST / GET | `/api/courses/<course_id>/prerequisites` |

### Terms, sections, completions, and registration

| Method | Endpoint |
|---|---|
| POST / GET | `/api/terms` |
| POST / GET | `/api/sections` |
| GET | `/api/sections/<section_id>` |
| POST | `/api/completions` |
| POST / GET | `/api/section-enrollments` |
| DELETE | `/api/section-enrollments/<enrollment_id>` |
| POST / GET | `/api/waitlists` |
| DELETE | `/api/waitlists/<entry_id>` |

The reconstruction's course-level enrollment endpoints also remain available under `/api/enrollments`.

The machine-readable API contract is maintained at [`docs/openapi.yaml`](docs/openapi.yaml).

## Search and pagination

Student and course collection endpoints support `q` search. Student/course/enrollment collection APIs also implement pagination where provided by the core routes, using `page` and `per_page` with defensive bounds.

Example:

```text
GET /api/students?q=amina&page=1&per_page=25
GET /api/courses?q=programming&page=1&per_page=25
```

## Database integrity and migrations

The relational model uses application validation plus SQL-level constraints including:

- unique student number and email
- unique course code
- positive credits and capacity
- unique course/term/section-number combinations
- unique student/section enrollment relationships
- unique student/section waitlist relationships
- prerequisite self-reference prevention
- controlled lifecycle states for enrollments and waitlist entries
- foreign-key relationships across the registration domain

Alembic manages schema evolution. The repository includes a baseline migration for the current schema, and CI verifies `upgrade head → downgrade base → upgrade head` before running tests.

The application defaults to SQLite for local use and supports PostgreSQL through `psycopg`. Common hosted `postgres://` URLs are normalized for SQLAlchemy/psycopg compatibility.

## Tests and CI

The test suite now covers considerably more than the original reconstruction, including:

- health checks
- student/course CRUD
- search and pagination
- enrollment creation, drop, and reactivation
- duplicate and capacity errors
- academic terms and sections
- prerequisites and completion records
- registration windows
- schedule conflicts
- section capacity
- transactional capacity guard behavior
- PostgreSQL `FOR UPDATE` lock generation
- waitlist lifecycle
- automatic waitlist promotion
- authentication requirements
- one-time admin bootstrap
- login failures
- admin/registrar/student role boundaries
- student ownership restrictions
- OpenAPI specification structure
- Alembic migration upgrade/downgrade cycles in CI

GitHub Actions runs migration verification and the pytest suite on pushes and pull requests to `main`. The current capacity/migration test run is passing.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
flask --app run.py run --debug
```

`flask --app run.py init-db` remains available for simple local reconstruction workflows, but Alembic is the preferred schema-management path for the enhanced backend.

Run tests:

```bash
python -m pytest -q
```

SQLite is the default development database. For PostgreSQL, provide a SQLAlchemy-compatible connection string through `DATABASE_URL`, for example:

```bash
export DATABASE_URL="postgresql+psycopg://user:password@host:5432/course_registration"
alembic upgrade head
```

## Current production gaps

This is now a strong portfolio backend, but it is not presented as a finished university production registration platform. Important remaining engineering work includes:

- a real PostgreSQL integration environment/load test with simultaneous registration workers
- account password reset/recovery and explicit token revocation
- rate limiting / abuse controls
- structured audit logging
- interactive Swagger UI or equivalent generated documentation surface
- deeper service-layer extraction from `app/__init__.py`
- production observability / metrics
- deployment infrastructure and secret-management integration

These are intentionally listed as gaps rather than implied capabilities.

## Provenance

Historical evidence supports the broad existence of a Python/Flask/SQL course-registration/database-systems project, but the exact historical endpoint set, source bytes, database engine, and richer domain behavior have not been recovered.

Accordingly:

- **RECOVERED:** broad project concept and academic context
- **RECONSTRUCTED:** initial student/course/enrollment Flask API
- **ENHANCED:** CRUD expansion, terms, sections, prerequisites, registration rules, completions, waitlists, automatic promotion, authentication, RBAC, migrations, PostgreSQL support, transactional capacity protection, OpenAPI documentation, expanded tests, and CI

See [`PROVENANCE.md`](PROVENANCE.md) and [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for the explicit boundary.

## Portfolio

Explore the complete technical portfolio at **[perpsakach.github.io](https://perpsakach.github.io/)**.
