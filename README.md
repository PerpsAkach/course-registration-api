# Course Registration REST API

> Flask + SQLAlchemy registration backend with academic terms, course sections, prerequisites, schedule validation, waitlists, authentication, RBAC, migrations, PostgreSQL support, transactional seat protection, audit logging, rate limiting, OpenAPI documentation, and automated CI.

[![CI](https://github.com/PerpsAkach/course-registration-api/actions/workflows/ci.yml/badge.svg)](https://github.com/PerpsAkach/course-registration-api/actions/workflows/ci.yml)
[![Portfolio](https://img.shields.io/badge/Portfolio-perpsakach.github.io-d7ff5f?style=flat-square&labelColor=11151a)](https://perpsakach.github.io/)
![Flask](https://img.shields.io/badge/Flask-REST%20API-111827?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-2563eb?style=flat-square)
![Testing](https://img.shields.io/badge/Testing-pytest-0f766e?style=flat-square)
![Status](https://img.shields.io/badge/Status-Reconstructed%20%2B%20Enhanced-6b7280?style=flat-square)

## Overview

This repository began as a portfolio reconstruction of a course-registration/database-systems project and has since been deliberately enhanced into a substantially richer backend system.

The current implementation models students, courses, academic terms, sections, meeting schedules, prerequisites, course completions, section registrations, waitlists, authentication, role-based access control, schema migrations, PostgreSQL runtime support, structured audit events, defensive request throttling, and an OpenAPI contract.

The public code is best described as:

**Recovered project concept → reconstructed core → enhanced portfolio backend**

The provenance boundary remains explicit: the richer features documented below are modern portfolio enhancements, not claims about the exact historical coursework implementation.

## Current capabilities

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
- PostgreSQL `SELECT ... FOR UPDATE` protection for final-seat allocation
- drop/reactivation behavior
- FIFO waitlists and automatic promotion
- bearer-token authentication
- `student`, `registrar`, and `admin` RBAC
- student self-service authorization boundaries
- admin-managed user creation
- structured audit logging for mutating API requests
- admin-only audit-event retrieval
- request IDs returned through `X-Request-ID`
- configurable API rate limiting with stricter login/bootstrap limits
- Alembic migrations
- PostgreSQL driver/runtime support
- OpenAPI 3.1 documentation in `docs/openapi.yaml`
- pytest coverage and GitHub Actions CI

## Architecture

```mermaid
flowchart LR
    Client[API Client] --> Runtime[Secure Flask Application]
    Runtime --> Auth[Authentication + RBAC]
    Runtime --> Limits[Rate Limiting]
    Runtime --> Audit[Audit Logging]
    Runtime --> Core[Core Registration Routes]
    Runtime --> Wait[Waitlist Workflow]
    Runtime --> Capacity[Transactional Capacity Guard]

    Auth --> DB[(SQLAlchemy / Relational DB)]
    Audit --> DB
    Core --> DB
    Wait --> DB
    Capacity --> DB

    Core --> Rules[Registration Rules]
    Rules --> P[Prerequisites]
    Rules --> W[Registration Windows]
    Rules --> C[Capacity]
    Rules --> S[Schedule Conflicts]
```

Runtime composition is handled by `app/secure.py`. The executable entry point in `run.py` uses this secure application factory.

### Main code organization

```text
app/
├── __init__.py    # core REST endpoints and registration rules
├── audit.py       # structured request audit events
├── auth.py        # authentication, user accounts, RBAC
├── capacity.py    # transactional section-capacity guard
├── db.py          # SQLAlchemy engine/session configuration
├── models.py      # academic/registration relational model
├── rate_limit.py  # request throttling
├── secure.py      # production-oriented application composition
└── waitlist.py    # waitlist lifecycle and automatic promotion

migrations/        # Alembic migration environment and versions
docs/openapi.yaml  # OpenAPI 3.1 API contract
```

## Registration decision flow

```mermaid
flowchart TD
    A[Registration request] --> B{Registration window open?}
    B -- No --> X1[409 registration_closed]
    B -- Yes --> C{Already active in section?}
    C -- Yes --> X2[409 already_enrolled]
    C -- No --> D{Prerequisites complete?}
    D -- No --> X3[409 prerequisites_not_met]
    D -- Yes --> E{Same course already active this term?}
    E -- Yes --> X4[409 already_registered_for_course]
    E -- No --> F{Schedule conflict?}
    F -- Yes --> X5[409 schedule_conflict]
    F -- No --> G{Seat available?}
    G -- No --> X6[409 section_full]
    G -- Yes --> H[Create or reactivate enrollment]
    H --> I[Transactional capacity guard]
    I --> J[201 Created]
```

When a section is full, an eligible student may join its waitlist. Dropping an active section enrollment triggers FIFO evaluation of waiting students; the first student who still satisfies the registration rules is automatically promoted.

### Final-seat concurrency protection

The route-level capacity check provides a fast domain response. The enhanced secure runtime also activates `app/capacity.py`.

On PostgreSQL, active seat changes lock the target `sections` row with `SELECT ... FOR UPDATE`, recount active section enrollments inside the transaction, and reject an over-capacity transaction. This serializes competing registrations for the same section before the final seat is committed.

SQLite remains useful for local development and tests, but it does not provide PostgreSQL-equivalent row-level `FOR UPDATE` behavior. Production concurrency claims are therefore scoped to databases that support the locking strategy.

## Authentication and authorization

The secure runtime protects API routes by default.

| Role | Intended access |
|---|---|
| `student` | Read catalog data and operate on the student's own registration/waitlist resources |
| `registrar` | Manage operational registration and catalog resources |
| `admin` | Registrar capabilities plus user/account administration and audit-log access |

Authentication uses password hashing plus time-limited signed bearer tokens. The current token lifetime is eight hours.

### First-time bootstrap

```bash
curl -X POST http://127.0.0.1:5000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.edu",
    "password": "ChangeThisStrongPassword"
  }'
```

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

Set a strong deployment secret:

```bash
export APP_SECRET_KEY="replace-with-a-long-random-secret"
```

## Audit logging

Mutating HTTP requests (`POST`, `PATCH`, `PUT`, `DELETE`) are recorded in `audit_events` with:

- request ID
- authenticated actor ID when available
- HTTP method
- request path
- response status
- timestamp

The middleware intentionally does **not** persist request bodies or credentials.

Admins can inspect recent events using:

```text
GET /api/audit-events?limit=100
```

Responses also include an `X-Request-ID` header for request tracing.

## Rate limiting

The secure runtime uses Flask-Limiter.

Defaults:

```text
Global default: 300 requests/minute per remote address
Login:          10 requests/minute
Bootstrap:       5 requests/hour
```

These can be changed with:

```text
RATELIMIT_DEFAULT
RATELIMIT_LOGIN
RATELIMIT_BOOTSTRAP
RATELIMIT_STORAGE_URI
```

The default `memory://` limiter backend is appropriate for development and tests. A multi-worker production deployment should configure a shared rate-limit storage backend.

Rate-limit violations return:

```json
{"error": "rate_limit_exceeded"}
```

with HTTP `429`.

## Endpoint groups

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

### Registration domain

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
| GET | `/api/audit-events` |

The reconstruction's course-level enrollment endpoints also remain available under `/api/enrollments`.

The machine-readable API contract is maintained at [`docs/openapi.yaml`](docs/openapi.yaml).

## Database integrity and migrations

The relational model uses application validation plus SQL-level constraints including unique identifiers, positive credits/capacities, unique course/term/section combinations, unique enrollment/waitlist relationships, controlled lifecycle states, prerequisite self-reference prevention, and foreign keys across the registration domain.

Alembic manages schema evolution. The repository contains a frozen baseline migration and a subsequent audit-events migration. CI verifies:

```text
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

before running the test suite.

The application defaults to SQLite for local use and supports PostgreSQL through `psycopg`. Common hosted `postgres://` URLs are normalized for SQLAlchemy/psycopg compatibility.

## Tests and CI

Coverage includes:

- student/course CRUD
- search and pagination
- enroll/drop/reactivate behavior
- academic terms and sections
- prerequisites and completions
- registration windows
- schedule conflicts
- capacity errors
- transactional capacity guard behavior
- PostgreSQL `FOR UPDATE` lock generation
- waitlist lifecycle and automatic promotion
- authentication and RBAC
- student ownership restrictions
- structured audit logging and admin-only audit access
- authentication rate limiting and JSON `429` responses
- OpenAPI structure
- Alembic migration upgrade/downgrade cycles

GitHub Actions runs migration verification and pytest on pushes and pull requests to `main`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
flask --app run.py run --debug
```

Run tests:

```bash
python -m pytest -q
```

SQLite is the default development database. For PostgreSQL:

```bash
export DATABASE_URL="postgresql+psycopg://user:password@host:5432/course_registration"
alembic upgrade head
```

`flask --app run.py init-db` remains available for simple local reconstruction workflows, but Alembic is the preferred schema-management path for the enhanced backend.

## Remaining production gaps

This is a strong portfolio backend, but it is not presented as a finished university production registration platform. Remaining engineering work includes:

- a real PostgreSQL multi-worker concurrency/load test
- password reset/recovery and explicit token revocation
- shared production rate-limit storage configuration
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
- **ENHANCED:** CRUD expansion, terms, sections, prerequisites, registration rules, completions, waitlists, automatic promotion, authentication, RBAC, migrations, PostgreSQL support, transactional capacity protection, audit logging, rate limiting, OpenAPI documentation, expanded tests, and CI

See [`PROVENANCE.md`](PROVENANCE.md) and [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for the explicit boundary.

## Portfolio

Explore the complete technical portfolio at **[perpsakach.github.io](https://perpsakach.github.io/)**.
