"""Raw snapshot storage: payload bytes -> local file + SourceSnapshot metadata.

Payload content never enters Git; only checksummed metadata rows reference the
file path (spec §40.5.5). Identical payloads deduplicate via
UNIQUE(source_id, checksum).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_core.config import get_settings
from backend_core.db import utcnow
from backend_core.domain import SourceSnapshot


def raw_dir() -> Path:
    path = Path(get_settings().snapshot_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_snapshot(
    session: Session,
    *,
    source_id: str,
    payload: bytes,
    snapshot_time: datetime | None = None,
    stats: dict | None = None,
    license_policy: str = "retain",
) -> SourceSnapshot:
    """Persist payload to <snapshot_dir>/<source_id>/<checksum>.json and return
    the metadata row. Replays of the same payload return the existing row."""
    checksum = hashlib.sha256(payload).hexdigest()

    existing = session.scalar(
        select(SourceSnapshot).where(
            SourceSnapshot.source_id == source_id,
            SourceSnapshot.checksum == checksum,
        )
    )
    if existing is not None:
        return existing

    directory = raw_dir() / source_id
    directory.mkdir(parents=True, exist_ok=True)
    storage_uri = str(directory / f"{checksum}.json")
    Path(storage_uri).write_bytes(payload)

    snapshot = SourceSnapshot(
        source_id=source_id,
        snapshot_time=snapshot_time or utcnow(),
        storage_uri=storage_uri,
        content_encoding="identity",
        content_length=len(payload),
        checksum=checksum,
        stats=stats,
        license_policy=license_policy,
    )
    session.add(snapshot)
    session.flush()
    return snapshot
