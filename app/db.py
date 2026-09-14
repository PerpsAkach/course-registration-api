from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionFactory = None


def normalize_database_url(url: str) -> str:
    """Normalize common deployment URLs to SQLAlchemy 2.x driver URLs."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def configure_database(url: str) -> Engine:
    global _engine, _SessionFactory
    url = normalize_database_url(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(
        url,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=not url.startswith("sqlite"),
    )

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


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not configured")
    return _engine


def new_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Database not configured")
    return _SessionFactory()
