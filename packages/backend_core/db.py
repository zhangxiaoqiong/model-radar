"""Database engine, session factory and declarative base.

Conventions (spec §5.0):
- InnoDB, utf8mb4 / utf8mb4_unicode_ci on every table
- CHAR(36) UUID primary keys, app-generated (UUIDv7 via uuid6 package)
- naive-UTC DATETIME columns written by the application layer
- PyMySQL connections pinned to time_zone '+00:00'
- no CHECK constraints / functional indexes (MySQL 5.7) — validation in app
"""

from __future__ import annotations

from datetime import datetime, timezone

from uuid6 import uuid7

from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

MYSQL_TABLE_KWARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def new_uuid() -> str:
    """Time-ordered UUIDv7 as 36-char string — lexicographic order ≈ creation time."""
    return str(uuid7())


def utcnow() -> datetime:
    """Naive UTC timestamp for DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, nullable=False
    )


def create_db_engine(url: str, *, pool_pre_ping: bool = True, **kwargs):
    """Engine factory. Connections are pinned to UTC via init_command."""
    connect_args = {"init_command": "SET time_zone='+00:00'", "charset": "utf8mb4"}
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=3600,
        **kwargs,
    )


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


from .config import get_settings  # noqa: E402

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine(get_settings().database_url)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = make_session_factory(get_engine())
    return _SessionLocal
