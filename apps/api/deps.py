"""Shared dependencies: DB session, admin auth, serialization helpers."""

from __future__ import annotations

import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Header, Request
from sqlalchemy.orm import Session

from backend_core.config import get_settings
from backend_core.db import get_session_factory


def get_db_session() -> Session:
    """Request-scoped session; commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class UnauthorizedError(Exception):
    def __init__(self, detail: str = "admin token required or invalid"):
        self.detail = detail


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> str:
    """V1a single-token admin auth (RBAC deferred per spec §12)."""
    token = get_settings().admin_api_token
    if not token or not x_admin_token or not secrets.compare_digest(x_admin_token, token):
        raise UnauthorizedError()
    return "admin"


def jsonable(value: Any) -> Any:
    """Convert ORM-friendly types to JSON-safe primitives."""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def row_dict(obj: Any, columns: list[str]) -> dict:
    return jsonable({c: getattr(obj, c) for c in columns})
