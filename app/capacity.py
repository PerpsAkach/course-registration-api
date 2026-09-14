from __future__ import annotations

from collections import defaultdict

from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session

from .models import Section, SectionEnrollment


class SectionCapacityExceeded(Exception):
    """Raised when a transaction would overfill a course section."""

    def __init__(self, section_id: int):
        self.section_id = section_id
        super().__init__(f"section {section_id} is full")


def section_lock_statement(section_id: int):
    """Lock one section row for the duration of the seat-allocation transaction.

    PostgreSQL renders this as ``SELECT ... FOR UPDATE``. That row lock
    serializes competing registrations for the same section so the final-seat
    capacity check cannot be evaluated concurrently by two transactions.
    """
    return select(Section).where(Section.id == section_id).with_for_update()


def _status_history(enrollment: SectionEnrollment):
    return inspect(enrollment).attrs.status.history


@event.listens_for(Session, "before_flush")
def enforce_section_capacity(session: Session, _flush_context, _instances) -> None:
    """Serialize active-seat changes and reject transactions over capacity.

    The section row is locked before the active-enrollment count is evaluated.
    This provides a concurrency-safe final-seat guard on databases that support
    row-level ``FOR UPDATE`` locking, notably PostgreSQL.
    """
    deltas: dict[int, int] = defaultdict(int)

    for obj in session.new:
        if not isinstance(obj, SectionEnrollment) or obj.section_id is None:
            continue
        # SQLAlchemy column defaults are populated during flush, so a newly
        # constructed enrollment can still expose ``status is None`` here even
        # though its persisted default is ``active``.
        if (obj.status or "active") == "active":
            deltas[obj.section_id] += 1

    for obj in session.dirty:
        if not isinstance(obj, SectionEnrollment) or obj.section_id is None:
            continue
        history = _status_history(obj)
        if not history.has_changes():
            continue
        previous = history.deleted[0] if history.deleted else None
        current = history.added[0] if history.added else obj.status
        if previous != "active" and current == "active":
            deltas[obj.section_id] += 1
        elif previous == "active" and current != "active":
            deltas[obj.section_id] -= 1

    for section_id in sorted(deltas):
        delta = deltas[section_id]
        if delta <= 0:
            continue

        section = session.scalar(section_lock_statement(section_id))
        if section is None:
            continue

        persisted_active = session.scalar(
            select(func.count())
            .select_from(SectionEnrollment)
            .where(
                SectionEnrollment.section_id == section_id,
                SectionEnrollment.status == "active",
            )
        ) or 0

        # Dirty active->dropped rows are still visible as active in the database
        # until this flush, so subtract those pending releases from the count.
        pending_releases = 0
        for obj in session.dirty:
            if not isinstance(obj, SectionEnrollment) or obj.section_id != section_id:
                continue
            history = _status_history(obj)
            if not history.has_changes():
                continue
            previous = history.deleted[0] if history.deleted else None
            current = history.added[0] if history.added else obj.status
            if previous == "active" and current != "active":
                pending_releases += 1

        resulting_active = persisted_active - pending_releases + delta
        if resulting_active > section.capacity:
            raise SectionCapacityExceeded(section_id)
