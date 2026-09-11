# Implementation Status

This file distinguishes functionality that exists in the current public repository from functionality that was previously discussed, reconstructed in richer local drafts, or identified as a future extension.

## Implemented in the public repository

| Capability | Status | Evidence |
|---|---|---|
| Health endpoint | Implemented | `GET /api/health` |
| Create student | Implemented | `POST /api/students` |
| List students | Implemented | `GET /api/students` |
| Create course | Implemented | `POST /api/courses` |
| List courses | Implemented | `GET /api/courses` |
| Create enrollment | Implemented | `POST /api/enrollments` |
| Reactivate dropped enrollment | Implemented | Existing enrollment status set back to `active` |
| Duplicate active-enrollment prevention | Implemented | Returns `409 already_enrolled` |
| Course capacity check | Implemented | Counts active enrollments before creation |
| Unique student number | Implemented | Database uniqueness constraint + application check |
| Unique student email | Implemented | Database uniqueness constraint + application check |
| Unique course code | Implemented | Database uniqueness constraint + application check |
| Unique student/course relationship | Implemented | `UniqueConstraint(student_id, course_id)` |
| Positive course credits | Implemented | SQL check constraint + route validation |
| Positive course capacity | Implemented | SQL check constraint + route validation |
| Enrollment lifecycle status | Implemented | `active` / `dropped` model constraint |
| Database initialization CLI | Implemented | `flask --app run.py init-db` |
| Basic pytest API test | Implemented | health + student/course/enrollment flow |

## Not currently implemented in the public repository

| Capability | Status |
|---|---|
| Get student by ID | Not implemented |
| Update student | Not implemented |
| Delete student | Not implemented |
| Get course by ID | Not implemented |
| Update course | Not implemented |
| Delete course | Not implemented |
| Get/delete enrollment by ID | Not implemented |
| Drop-enrollment endpoint | Not implemented |
| Student-to-courses lookup | Not implemented |
| Course-to-students lookup | Not implemented |
| Search | Not implemented |
| Pagination | Not implemented |
| Dedicated service layer | Not implemented |
| Dedicated repository layer | Not implemented |
| `seed-db` CLI command | Not implemented |
| Authentication / authorization | Not implemented |
| Semesters / sections | Not implemented |
| Prerequisites | Not implemented |
| Waitlists | Not implemented |
| Registration windows | Not implemented |
| Schedule conflict detection | Not implemented |
| Concurrency-safe seat allocation | Not implemented |

## Historical evidence status

Available artifacts support the broad historical context of a Flask/SQL course-registration project, but no currently available artifact proves the exact historical endpoint set, database engine, source bytes, or richer layered implementation.

Until stronger historical evidence is recovered, the public portfolio should describe only the capabilities above as implemented.