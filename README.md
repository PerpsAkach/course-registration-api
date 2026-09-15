# Course Registration REST API

> Flask + SQLAlchemy registration backend with academic terms, course sections, prerequisites, schedule validation, waitlists, RBAC, PostgreSQL concurrency protection, migrations, auditing, rate limiting, Prometheus metrics, OpenAPI/Swagger documentation, Docker/Gunicorn deployment support, and automated CI.

[![CI](https://github.com/PerpsAkach/course-registration-api/actions/workflows/ci.yml/badge.svg)](https://github.com/PerpsAkach/course-registration-api/actions/workflows/ci.yml)
[![Portfolio](https://img.shields.io/badge/Portfolio-perpsakach.github.io-d7ff5f?style=flat-square&labelColor=11151a)](https://perpsakach.github.io/)
![Flask](https://img.shields.io/badge/Flask-REST%20API-111827?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-2563eb?style=flat-square)
![Testing](https://img.shields.io/badge/Testing-pytest-0f766e?style=flat-square)
![Status](https://img.shields.io/badge/Status-Reconstructed%20%2B%20Enhanced-6b7280?style=flat-square)

## Overview

This repository began as a portfolio reconstruction of a course-registration/database-systems project and was deliberately extended into a substantially richer backend engineering project.

The current enhanced runtime models students, courses, academic terms, sections, schedules, prerequisites, completions, section registration, waitlists, authentication/RBAC, database migrations, PostgreSQL concurrency controls, operational audit events, request throttling, metrics, API documentation, and a containerized runtime.

The evidence boundary remains explicit:

**Recovered project concept → reconstructed core → enhanced portfolio backend**

The modern capabilities below are portfolio engineering enhancements, not claims about the exact historical coursework implementation.

## Current capabilities

- student and course CRUD, search, and pagination
- academic terms and registration windows
- course sections with instructor, location, meeting days/times, and capacity
- prerequisite relationships and completion evidence
- shared enhanced registration-policy/service layer
- server-controlled registration-window policy date
- same-course/same-term prevention
- schedule-conflict detection
- section-level capacity validation
- PostgreSQL `SELECT ... FOR UPDATE` final-seat protection
- real PostgreSQL concurrent final-seat integration test
- section enrollment creation/reactivation/drop
- FIFO waitlists, cancellation, rejoin, and automatic promotion
- promotion-time policy revalidation
- atomic drop + waitlist-promotion transaction coordination
- password-hashed authentication with eight-hour signed bearer tokens
- `student`, `registrar`, and `admin` RBAC
- student ownership enforcement for self-service registration/waitlists
- account-wide token revocation and password change
- structured request audit logging and request IDs
- configurable rate limiting
- Alembic migrations
- PostgreSQL runtime support through `psycopg`
- OpenAPI 3.1 specification and Swagger UI
- Prometheus-compatible request metrics
- Docker + Gunicorn runtime and PostgreSQL Compose stack
- pytest regression/integration coverage and GitHub Actions CI

## Architecture

```mermaid
flowchart LR
    Client[API Client] --> Runtime[Secure Flask Runtime]
    Runtime --> Auth[Authentication + RBAC]
    Runtime --> Limits[Rate Limiting]
    Runtime --> Audit[Audit Logging]
    Runtime --> Metrics[Prometheus Metrics]
    Runtime --> Core[Reconstructed Core Routes]
    Runtime --> Service[Registration Service]
    Runtime --> Wait[Waitlist HTTP Workflow]
    Service --> Capacity[Transactional Capacity Guard]

    Auth --> DB[(SQLAlchemy / Relational DB)]
    Audit --> DB
    Core --> DB
    Service --> DB
    Wait --> Service
    Capacity --> DB
```

The executable entry point in `run.py` uses `app.secure:create_app`, the canonical enhanced runtime.

### Main code organization

```text
app/
├── __init__.py              # reconstructed core REST API / compatibility layer
├── registration_service.py  # shared enhanced registration + waitlist policy
├── waitlist.py              # waitlist HTTP endpoints
├── capacity.py              # transactional final-seat guard
├── auth.py                  # authentication, accounts, RBAC, token revocation
├── audit.py                 # structured request audit trail
├── rate_limit.py            # request throttling
├── observability.py         # Prometheus metrics
├── docs.py                  # OpenAPI + Swagger surface
├── db.py                    # SQLAlchemy engine/session configuration
├── models.py                # relational domain model
└── secure.py                # production-oriented application composition

migrations/                  # Alembic migration environment and revisions
docs/openapi.yaml            # OpenAPI 3.1 contract
Dockerfile                    # Gunicorn application image
compose.yaml                  # local API + PostgreSQL 17 stack
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the transaction, security, compatibility, and deployment boundaries.

## Registration decision flow

```mermaid
flowchart TD
    A[Section registration] --> B{Server policy date inside window?}
    B -- No --> X1[409 registration_closed]
    B -- Yes --> C{Already active in section?}
    C -- Yes --> X2[409 already_enrolled]
    C -- No --> D{Prerequisites complete?}
    D -- No --> X3[409 prerequisites_not_met]
    D -- Yes --> E{Same course active this term?}
    E -- Yes --> X4[409 already_registered_for_course]
    E -- No --> F{Schedule conflict?}
    F -- Yes --> X5[409 schedule_conflict]
    F -- No --> G{Seat available?}
    G -- No --> X6[409 section_full]
    G -- Yes --> H[Create or reactivate enrollment]
    H --> I[Transactional capacity guard]
    I --> J[201 Created]
```

The enhanced runtime does **not** trust a client-supplied `as_of` date to decide whether registration is open. Tests can set `REGISTRATION_POLICY_DATE`; otherwise the server's current date is used.

## Waitlist and atomic promotion

A student may join a waitlist only when the section is full and the student otherwise satisfies current registration policy.

When a seat opens, waiting entries are evaluated FIFO. The first currently eligible candidate is promoted. The service re-checks the registration window, prerequisites, same-course rule, and schedule conflicts at promotion time. Temporarily ineligible candidates remain waiting and may be passed by a later eligible candidate.

A drop and resulting promotion share one SQLAlchemy transaction:

```text
BEGIN
  mark current enrollment dropped
  flush seat release
  evaluate waitlist under current policy
  create/reactivate promoted enrollment if eligible
  mark waitlist entry promoted
COMMIT
```

The intermediate flush is not a commit. A dedicated test injects a promotion failure and verifies rollback restores the original active enrollment and leaves the waitlist unchanged.

If the registration window has closed when the seat opens, no waitlist entry is promoted.

## Final-seat concurrency protection

The shared registration service performs an early capacity check. The authoritative final-seat protection is `app/capacity.py`.

On PostgreSQL, the target `sections` row is locked with `SELECT ... FOR UPDATE`, active enrollments are recounted inside the transaction, and an over-capacity allocation is rejected.

CI exercises this with PostgreSQL 17 using two concurrent transactions competing for a single seat and verifies:

```text
capacity = 1
concurrent attempts = 2
committed registrations = 1
capacity rejections = 1
final active enrollment count = 1
```

This is real PostgreSQL concurrency integration coverage. It is **not** presented as a high-volume production load benchmark.

## Authentication and authorization

The secure runtime protects API routes by default.

| Role | Intended access |
|---|---|
| `student` | Read catalog data and operate on the linked student's own registration/waitlist resources |
| `registrar` | Manage operational registration and catalog resources |
| `admin` | Registrar capabilities plus user/account administration and audit-log access |

Authentication uses Werkzeug password hashing and time-limited signed bearer tokens (`itsdangerous`), not JWT. Token lifetime is eight hours.

Account-wide token revocation is available through:

```text
POST /api/auth/logout-all
```

Changing a password through `POST /api/auth/password` also invalidates previously issued tokens by incrementing the account token version.

### Bootstrap and login

```bash
curl -X POST http://127.0.0.1:5000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.edu",
    "password": "ChangeThisStrongPassword"
  }'
```

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

For deployment, set a strong application secret:

```bash
export APP_SECRET_KEY="replace-with-a-long-random-secret"
```

The repository still contains a development fallback secret; that fallback is not appropriate for a production deployment.

## Audit logging and request tracing

Mutating requests (`POST`, `PATCH`, `PUT`, `DELETE`) are recorded in `audit_events` with request ID, authenticated actor ID when available, method, path, response status, and timestamp.

Request bodies and credentials are intentionally not persisted.

Admins can inspect recent events through:

```text
GET /api/audit-events?limit=100
```

Responses include `X-Request-ID` for trace correlation.

## Rate limiting

The secure runtime uses Flask-Limiter.

```text
Global default: 300 requests/minute per remote address
Login:          10 requests/minute
Bootstrap:       5 requests/hour
```

Configuration:

```text
RATELIMIT_DEFAULT
RATELIMIT_LOGIN
RATELIMIT_BOOTSTRAP
RATELIMIT_STORAGE_URI
```

`memory://` is suitable for development/tests. Multi-worker production deployment should use a shared limiter backend.

Rate-limit violations return HTTP `429` with:

```json
{"error": "rate_limit_exceeded"}
```

## Observability and documentation

- `GET /api/health` — application health
- `GET /metrics` — Prometheus-compatible request counters and latency histograms
- `GET /docs` — Swagger UI
- `GET /openapi.yaml` — machine-readable OpenAPI 3.1 contract

Metrics use normalized route templates rather than raw URLs to avoid unbounded path-label cardinality.

## Endpoint groups

### Public / authentication

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/bootstrap` | One-time first-admin creation |
| POST | `/api/auth/login` | Authenticate and receive bearer token |
| GET | `/api/auth/me` | Current authenticated account |
| POST | `/api/auth/logout-all` | Revoke all existing bearer tokens for current account |
| POST | `/api/auth/password` | Change current password and revoke existing tokens |
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

The reconstructed course-level `/api/enrollments` endpoints remain available as a compatibility workflow. The section-level registration API is the richer enhanced path.

## Database integrity and migrations

The relational model uses application validation plus SQL-level constraints for unique identifiers, positive credits/capacities, unique course/term/section combinations, unique enrollment/waitlist relationships, controlled lifecycle states, prerequisite self-reference prevention, and foreign keys across the registration domain.

Alembic manages schema evolution. Current revisions include the frozen baseline, structured audit events, and account token-version support. CI verifies:

```text
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

The application defaults to SQLite for lightweight local use and supports PostgreSQL through `psycopg`.

## Tests and CI

The test suite covers, among other behaviors:

- student/course CRUD, search, and pagination
- terms, sections, prerequisites, and completion records
- registration-window, prerequisite, duplicate-course, and schedule-conflict rules
- server-controlled policy date and rejection of client date bypass attempts
- section capacity and reactivation behavior
- waitlist join/cancel/rejoin/full-section requirements
- FIFO eligible promotion and skipping a currently ineligible earlier candidate
- no promotion after registration closes
- atomic drop/promotion rollback semantics
- authentication, RBAC, token revocation, and password change
- secure-runtime own-student registration/waitlist access and cross-student rejection
- audit logging and request tracing
- rate limiting
- OpenAPI structure and Swagger surface
- Prometheus metrics
- Alembic upgrade/downgrade cycles
- real PostgreSQL final-seat concurrency
- production Docker image build

GitHub Actions runs the migration checks, unit/API suite, PostgreSQL integration test, and container build on `main` pushes and pull requests.

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

PostgreSQL example:

```bash
export DATABASE_URL="postgresql+psycopg://user:password@host:5432/course_registration"
export APP_SECRET_KEY="replace-with-a-long-random-secret"
alembic upgrade head
```

Local container stack:

```bash
docker compose up --build
```

`flask --app run.py init-db` remains available for simple reconstruction/local workflows, but Alembic is the preferred schema-management path for the enhanced backend.

## Remaining production gaps

This is a substantial portfolio backend, but it is not represented as a complete university production platform. Remaining gaps include:

- high-volume PostgreSQL load/stress testing
- password reset/recovery
- per-token/session inventory and selective revocation/refresh architecture
- shared production rate-limit backend deployment
- external Prometheus/Grafana hosting and centralized log aggregation
- managed cloud deployment / infrastructure-as-code
- external secret-management integration
- prerequisite-cycle detection
- canonical normalized meeting-day persistence

A general repository/data-access abstraction is intentionally not treated as mandatory at the current project scale because SQLAlchemy already provides the relevant persistence boundary.

## Provenance

Historical evidence supports the broad existence of a Python/Flask/SQL course-registration/database-systems project, but the exact historical endpoint set, source bytes, database engine, schema, and richer domain behavior have not been recovered.

Accordingly:

- **RECOVERED:** broad project concept and academic context
- **RECONSTRUCTED:** initial student/course/enrollment Flask API
- **ENHANCED:** richer domain model, registration service, policy rules, waitlists, concurrency controls, security, migrations, operations/observability, documentation, deployment tooling, expanded tests, and CI
- **UNVERIFIED:** exact historical implementation details not supported by recovered artifacts

See [`PROVENANCE.md`](PROVENANCE.md) and [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for the explicit boundary.

## Portfolio

Explore the complete technical portfolio at **[perpsakach.github.io](https://perpsakach.github.io/)**.
