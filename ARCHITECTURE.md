# Architecture

This document describes the current architecture of the enhanced course-registration backend and identifies the next refactoring boundary.

## Runtime composition

```text
Client
  |
  v
Flask secure runtime (`app.secure:create_app`)
  |
  +-- authentication / RBAC (`app/auth.py`)
  +-- rate limiting (`app/rate_limit.py`)
  +-- request audit trail (`app/audit.py`)
  +-- Prometheus metrics (`app/observability.py`)
  +-- interactive docs (`app/docs.py`)
  +-- core API routes (`app/__init__.py`)
  +-- waitlist workflow (`app/waitlist.py`)
  +-- transactional capacity guard (`app/capacity.py`)
  |
  v
SQLAlchemy sessions (`app/db.py`)
  |
  v
SQLite (development/tests) or PostgreSQL (production-oriented runtime)
```

## Domain model

The registration domain is centered on:

```text
Student
  |
  +-- CourseCompletion ----> Course
  |
  +-- SectionEnrollment ---> Section ---> Course
  |                           |
  |                           +-------> AcademicTerm
  |
  +-- WaitlistEntry --------> Section

Course
  |
  +-- Prerequisite ---------> required Course
```

Authentication and operations add two supporting domains:

```text
UserAccount ---> optional Student ownership link
AuditEvent  ---> optional authenticated actor
```

## Registration invariants

A section registration is accepted only when the relevant policy checks succeed:

1. student and section exist;
2. the request falls within the academic term registration window;
3. the student is not already active in the same section;
4. required prerequisite courses have recorded completion evidence;
5. the student is not already registered for the same course in the term;
6. the target section does not overlap an existing active section schedule;
7. section capacity is available;
8. the final seat is still available when the transaction commits.

The route-level capacity check supplies an early domain response. The authoritative final-seat protection is the transactional guard in `app/capacity.py`.

## Final-seat concurrency strategy

On PostgreSQL, active seat allocation locks the target `sections` row with `SELECT ... FOR UPDATE`. After acquiring the row lock, the transaction recounts active section enrollments and rejects the mutation if the resulting active count would exceed capacity.

The GitHub Actions pipeline exercises this against PostgreSQL 17 with two concurrent transactions competing for one seat. The invariant asserted by the test is:

```text
capacity = 1
concurrent registration attempts = 2
successful commits = 1
capacity rejections = 1
final active enrollment count = 1
```

This is integration-level concurrency validation, not a high-volume load benchmark.

## Waitlist behavior

Waitlist entries have three states:

```text
waiting -> promoted
waiting -> cancelled
cancelled/promoted -> waiting  (explicit rejoin where policy permits)
```

Promotion scans waiting entries in FIFO order and selects the first currently eligible student. Eligibility includes prerequisite, duplicate-course, and schedule-conflict checks. A student who is temporarily ineligible remains waiting while a later eligible candidate can be promoted.

Automatic promotion currently runs after a successful section-enrollment drop. The capacity transaction guard still protects the resulting active-seat mutation.

## Security boundary

The secure runtime uses three roles:

- `student`: catalog reads plus operations on the linked student's own registration/waitlist resources;
- `registrar`: operational registration and catalog administration;
- `admin`: registrar capabilities plus account administration and audit-log access.

Bearer tokens are time-limited and include an account token version. Password changes and `/api/auth/logout-all` increment that version, invalidating previously issued tokens for the account.

## Operational controls

The enhanced runtime includes:

- structured audit events without request-body capture;
- request IDs exposed through `X-Request-ID`;
- configurable Flask-Limiter policies;
- Prometheus-compatible request counters and latency histograms;
- `/api/health` for application health;
- `/metrics` for scraping;
- `/docs` and `/openapi.yaml` for API discovery.

## Database evolution

Alembic owns schema evolution. CI verifies migration reversibility with:

```text
upgrade head -> downgrade base -> upgrade head
```

The repository supports SQLite for lightweight development and PostgreSQL for production-oriented execution and row-lock concurrency semantics.

## Deployment boundary

The repository contains:

- a Gunicorn-based `Dockerfile`;
- `compose.yaml` for API + PostgreSQL 17;
- database health checks;
- API health checks;
- environment-driven database and secret configuration.

The repository does not claim managed-cloud deployment, infrastructure-as-code, external secret management, or production Prometheus/Grafana hosting.

## Next architectural refactor

The largest remaining structural issue is that `app/__init__.py` still owns a broad set of HTTP handlers and embeds registration policy decisions directly in route functions.

The next refactor should introduce a registration service boundary approximately like this:

```text
HTTP route
   |
   v
RegistrationService
   |
   +-- evaluate registration window
   +-- evaluate prerequisites
   +-- evaluate same-course rule
   +-- evaluate schedule conflicts
   +-- allocate/reactivate enrollment
   +-- coordinate drop + waitlist promotion
   |
   v
SQLAlchemy session / transactional capacity guard
```

The target is not to introduce abstraction for its own sake. The service layer should centralize rules that are currently shared conceptually by direct registration and waitlist promotion, make transaction boundaries explicit, and leave Flask handlers responsible primarily for HTTP parsing and response mapping.

A separate repository abstraction is lower priority because SQLAlchemy already provides an effective persistence abstraction for the current project size. It should only be introduced if query complexity or test isolation materially benefits from it.

## Provenance boundary

The richer architecture documented here is modern portfolio engineering. It must remain classified as **ENHANCED**, not recovered historical coursework. See [`PROVENANCE.md`](PROVENANCE.md) for the evidence boundary.
