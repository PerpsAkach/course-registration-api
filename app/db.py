from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_SessionFactory = None


def configure_database(url: str):
    global _engine, _SessionFactory
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, future=True, connect_args=connect_args)

    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _SessionFactory = sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        autoflush=False,
        future=True,
    )
    return _engine


def get_engine():
    if _engine is None:
        raise RuntimeError("Database not configured")
    return _engine


def new_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Database not configured")
    return _SessionFactory()
