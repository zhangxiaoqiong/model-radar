"""Normalizer + snapshot store tests.

Normalizer is pure logic (AA payload rows -> canonical evaluation inputs);
snapshot store uses the DB (model_radar_test) + local raw dir.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DB_NAME", "model_radar_test")

from ingestion.normalizers import normalize_aa_evaluation  # noqa: E402


def test_normalize_aa_evaluation_full_row():
    row = {
        "model_name": "gpt-5.2",
        "index_name": "swe-bench-verified",
        "value": 48.2,
        "sample_size": 500,
        "date": "2026-09-18",
        "id": "aa-eval-123",
    }
    out = normalize_aa_evaluation(row, source_id="src-1")
    assert out["score"] == "48.2"
    assert out["external_evaluation_id"] == "aa-eval-123"
    assert out["sample_size"] == 500
    assert out["evaluation_type"] == "external"
    assert out["source_id"] == "src-1"
    assert out["benchmark_slug"] == "swe-bench-verified"
    assert out["model_slug"] == "gpt-5.2"


def test_normalize_handles_string_scores_and_missing_fields():
    row = {"model_name": "claude-opus-4-5", "index_name": "gpqa-diamond", "value": "71.40"}
    out = normalize_aa_evaluation(row, source_id="src-1")
    assert out["score"] == "71.4"
    assert out["sample_size"] is None
    assert out["evaluation_date"] is None
    assert out["external_evaluation_id"] is None


def test_normalize_rejects_row_without_score():
    with pytest.raises(ValueError):
        normalize_aa_evaluation(
            {"model_name": "x", "index_name": "y"}, source_id="src-1"
        )


def test_normalize_preserves_trailing_precision_semantics():
    """Scores are canonicalized via Decimal so '72.30' -> '72.3' only in value,
    numeric meaning preserved."""
    out = normalize_aa_evaluation(
        {"model_name": "m", "index_name": "b", "value": "72.30"}, source_id="s"
    )
    assert float(out["score"]) == 72.3


# ---------------------------------------------------------------------------
# Snapshot store (DB + local file)

@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine
    from backend_core.config import get_settings
    from backend_core.db import Base

    get_settings.cache_clear()
    eng = create_engine(get_settings().database_url, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine, tmp_path):
    from backend_core.db import make_session_factory

    s = make_session_factory(engine)()
    yield s
    s.rollback()
    s.close()


def test_store_snapshot_roundtrip_and_idempotency(engine, session, tmp_path, monkeypatch):
    from backend_core.domain import Source, SourceSnapshot
    from ingestion.snapshot_store import store_snapshot

    monkeypatch.setattr("ingestion.snapshot_store.raw_dir", lambda: tmp_path)
    src = Source(slug="artificial_analysis", name="AA", source_type="independent_eval",
                 reliability_level="high", api_available=True)
    session.add(src)
    session.commit()

    payload = b'{"data": [1, 2, 3]}'
    snap1 = store_snapshot(session, source_id=src.id, payload=payload)
    session.commit()
    assert snap1.storage_uri.startswith(str(tmp_path))
    assert snap1.checksum and len(snap1.checksum) == 64
    # payload written
    with open(snap1.storage_uri, "rb") as f:
        assert f.read() == payload

    # replaying identical payload returns the same snapshot row (checksum unique)
    snap2 = store_snapshot(session, source_id=src.id, payload=payload)
    session.commit()
    assert snap2.id == snap1.id

    # different payload -> new snapshot
    snap3 = store_snapshot(session, source_id=src.id, payload=b'{"data": [4]}')
    session.commit()
    assert snap3.id != snap1.id
