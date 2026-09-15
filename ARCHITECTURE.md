# Architecture

This document describes the current architecture of the enhanced course-registration backend and its explicit transaction and security boundaries.

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
  +-- reconstructed core API routes (`app/__init__.py`)
  +-- shared registration policy/service (`app/registration_service.py`)
  +-- waitlist HTTP workflow (`app/waitlist.py`)
  +-- transactional capacity guard (`app/capacity.py`)
  |
  v
SQLAlchemy sessions (`app/db.py`)
  |
  v
SQLite (development/tests) or PostgreSQL (production-oriented runtime)
```

`run.py` uses the secure application factory. During secure-runtime composition, the waitlist module installs the shared registration service over the reconstructed section-enrollment mutation endpoints while preserving their existing URL rules and endpoint names. This keeps the historical reconstruction boundary intact while making the enhanced runtime use one registration-policy implementation.

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

## Registration service boundary

`app/registration_service.py` owns the enhanced section-registration policy used by the secure runtime. It centralizes:

- the server-controlled registration policy date;
- registration-window enforcement;
- prerequisite-completion evaluation;
- same-course/same-term blocking;
- schedule-conflict detection;
- section capacity pre-checks;
- enrollment creation/reactivation;
- waitlist admission/cancellation;
- promotion-time eligibility re-evaluation; and
- coordinated section drop plus waitlist promotion.

The HTTP adapters remain responsible for request parsing, authorization middleware participation, response mapping, and transaction commit/rollback. The service functions operate on a caller-owned SQLAlchemy `Session`, making transaction ownership explicit.

## Registration policy clock

Registration-window decisions in the enhanced runtime are server controlled. A client-supplied `as_of` field is not used to determine whether registration is open.

For deterministic tests, `REGISTRATION_POLICY_DATE` may be configured as an ISO date, a `date` object, or a callable returning a `date`. Without an override, the service uses the server's current date.

This prevents a client from bypassing a closed registration window by submitting an earlier date.

## Registration invariants

A section registration is accepted only when the relevant policy checks succeed:

1. student and section exist;
2. the server policy date is inside the academic term registration window;
3. the student is not already active in the same section;
4. required prerequisite courses have recorded completion evidence;
5. the student is not already registered for the same course in the term;
6. the target section does not overlap an existing active section schedule;
7. section capacity is available; and
8. the final seat is still available when the transaction flushes/commits.

The service-level capacity check supplies an early domain response. The authoritative final-seat protection is the SQLAlchemy transaction guard in `app/capacity.py`.

## Final-seat concurrency strategy

On PostgreSQL, active seat allocation locks the target `sections` row with `SELECT ... FOR UPDATE`. After acquiring the row lock, the transaction recounts active section enrollments and rejects the mutation if the resulting active count would exceed capacity.

The GitHub Actions pipeline exercises this against PostgreSQL 17 with two concurrent transactions competing for one seat. The invariant asserted by the integration test is:

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

A student may join only when the section is full and the student currently satisfies registration rules other than seat availability.

Promotion scans waiting entries in FIFO order and selects the first **currently eligible** student. Eligibility is re-evaluated at promotion time, including the registration window, prerequisites, duplicate-course rule, and schedule-conflict rule. A temporarily ineligible candidate remains waiting while a later eligible candidate may be promoted.

### Atomic drop + promotion

Dropping an active section enrollment and promoting the next eligible waiter are coordinated through one SQLAlchemy session and one commit boundary:

```text
BEGIN
  mark enrollment dropped
  FLUSH seat release
  re-evaluate FIFO waitlist
  create/reactivate promoted enrollment (if eligible)
  mark waitlist entry promoted
COMMIT
```

The intermediate flush materializes the released seat for subsequent queries but is **not** a commit. If the promotion workflow raises an error before commit, the caller rolls the transaction back and the original drop is rolled back as well. This rollback behavior is covered by an automated service test.

If the registration window has closed by promotion time, no student is promoted and the waiting entries remain waiting.

## Security boundary

The secure runtime uses three roles:

- `student`: catalog reads plus operations on the linked student's own registration/waitlist resources;
- `registrar`: operational registration and catalog administration;
- `admin`: registrar capabilities plus account administration and audit-log access.

Student ownership checks are exercised against the secure runtime for section-registration and waitlist operations, including rejection of cross-student create/list requests.

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

The repository does not claim managed-cloud deployment, infrastructure-as-code, external secret management, external Prometheus/Grafana hosting, or production-scale load validation.

## Compatibility boundary

`app/__init__.py` remains the reconstructed core application and still contains the original inline section-mutation implementation for compatibility with reconstruction-focused tests and historical structure. The canonical enhanced runtime is `app.secure:create_app`, which installs `app/registration_service.py` for section mutation and waitlist policy.

This distinction is deliberate: it avoids representing enhanced service-layer code as recovered historical source while still giving the deployed runtime one centralized policy path.

A future cleanup could physically move more non-registration CRUD handlers from `app/__init__.py` into blueprints, but that is an organizational refactor rather than a missing registration invariant.

A separate repository abstraction is also lower priority because SQLAlchemy already provides an effective persistence abstraction at this project size. It should be introduced only if query complexity or test isolation materially benefits from it.

## Provenance boundary

The richer architecture documented here is modern portfolio engineering. It is classified as **ENHANCED**, not recovered historical coursework. See [`PROVENANCE.md`](PROVENANCE.md) for the evidence boundary.
