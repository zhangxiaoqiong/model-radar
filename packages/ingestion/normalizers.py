"""Normalizers: source-specific payload rows -> canonical evaluation inputs.

Canonical output keys (consumed by the ingestion pipeline before
upsert_evaluation): model_slug, benchmark_slug, score, sample_size,
evaluation_date, external_evaluation_id, evaluation_type, source_id.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def _decimal_str(value) -> str:
    d = Decimal(str(value)).normalize()
    if not d.is_finite():
        raise InvalidOperation("score must be finite")
    return format(d, "f")


def _parse_date(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text[: len(fmt) + 2], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_aa_evaluation(row: dict, *, source_id: str) -> dict:
    """Artificial Analysis index row -> canonical evaluation input.

    Tolerant to unknown fields; strict about a usable score.
    """
    score_raw = row.get("value", row.get("score"))
    if score_raw is None or score_raw == "":
        raise ValueError(f"row without score: {row!r}")
    try:
        score = _decimal_str(score_raw)
    except InvalidOperation as exc:
        raise ValueError(f"unparseable score {score_raw!r}") from exc

    model_name = str(row.get("model_name") or "").strip()
    benchmark_slug = str(row.get("index_name") or "").strip()
    if not model_name or not benchmark_slug:
        raise ValueError("row requires model_name and index_name")
    sample = row.get("sample_size") or row.get("samples")
    sample_size = int(sample) if sample is not None else None
    if sample_size is not None and sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    return {
        "model_slug": model_name,
        "provider_slug": row.get("provider_slug"),
        "benchmark_slug": benchmark_slug,
        "score": score,
        "sample_size": sample_size,
        "evaluation_date": _parse_date(row.get("date")),
        "external_evaluation_id": (
            str(row["id"]) if row.get("id") is not None else None
        ),
        "evaluation_type": "external",
        "source_id": source_id,
        "raw": row,
    }
