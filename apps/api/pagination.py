"""Cursor pagination on UUIDv7 id (lexicographic ≈ creation time, newest first)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Select


def apply_cursor(
    stmt: Select,
    id_column: ColumnElement,
    cursor: str | None,
    limit: int,
) -> Select:
    stmt = stmt.order_by(id_column.desc()).limit(limit + 1)
    if cursor:
        stmt = stmt.where(id_column < cursor)
    return stmt


def page_result(items: list[Any], limit: int) -> dict:
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        next_cursor = items[-1].id
    return {"items": items, "next_cursor": next_cursor}
