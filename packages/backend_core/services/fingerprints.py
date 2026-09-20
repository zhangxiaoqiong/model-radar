"""Fingerprint helpers: canonicalization + hashing for idempotent persistence.

Two keys per evaluation (spec §8.3):
- evaluation_identity_hash: WHAT was measured (Model x Benchmark x config)
- observation_fingerprint:  WHAT was observed (identity + score/CI/sample/snapshot)

Replay rules implemented by the evaluation upsert service:
- same observation_fingerprint            -> skip (pure replay)
- same identity, observation_unchanged    -> skip (re-confirmation; no bloat)
- same identity, observation changed      -> new row chained via supersedes
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# canonicalization


def _canonical_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        # normalize scale: 72.3 == 72.30
        return repr(value.normalize())
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _canonical_value(v) for k, v in sorted(value.items(), key=lambda kv: kv[0])}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(v) for v in value]
    return value


def canonical_json(data: dict[str, Any]) -> str:
    """Deterministic JSON: null/empty-dict/missing collapse to the same output."""
    cleaned = {k: _canonical_value(v) for k, v in data.items() if v not in (None, {}, [])}
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# evaluation keys


def evaluation_identity_hash(
    *,
    model_variant_id: str,
    model_endpoint_id: str | None,
    benchmark_id: str,
    benchmark_version_id: str | None,
    benchmark_metric_id: str,
    source_id: str,
    evaluator: str | None,
    harness: str | None,
    harness_version: str | None,
    reasoning_setting: str | None,
    temperature: Decimal | None,
    random_seed: int | None,
    few_shot_count: int | None,
    agent_scaffold: str | None,
    agent_scaffold_version: str | None,
    dataset_revision: str | None,
    scorer_version: str | None,
    runtime_image: str | None,
    prompt_config: dict | None,
    decoding_config: dict | None,
) -> str:
    payload = canonical_json(
        {
            "model_variant_id": model_variant_id,
            "model_endpoint_id": model_endpoint_id,
            "benchmark_id": benchmark_id,
            "benchmark_version_id": benchmark_version_id,
            "benchmark_metric_id": benchmark_metric_id,
            "source_id": source_id,
            "evaluator": evaluator,
            "harness": harness,
            "harness_version": harness_version,
            "reasoning_setting": reasoning_setting,
            "temperature": temperature,
            "random_seed": random_seed,
            "few_shot_count": few_shot_count,
            "agent_scaffold": agent_scaffold,
            "agent_scaffold_version": agent_scaffold_version,
            "dataset_revision": dataset_revision,
            "scorer_version": scorer_version,
            "runtime_image": runtime_image,
            "prompt_config": prompt_config,
            "decoding_config": decoding_config,
        }
    )
    return sha256_hex(payload)


def observation_fingerprint(
    identity_hash: str,
    *,
    score: Decimal,
    confidence_lower: Decimal | None,
    confidence_upper: Decimal | None,
    sample_size: int | None,
    external_evaluation_id: str | None,
    source_snapshot_id: str | None,
) -> str:
    payload = canonical_json(
        {
            "identity": identity_hash,
            "score": score,
            "confidence_lower": confidence_lower,
            "confidence_upper": confidence_upper,
            "sample_size": sample_size,
            "external_evaluation_id": external_evaluation_id,
            "source_snapshot_id": source_snapshot_id,
        }
    )
    return sha256_hex(payload)


def observation_fields_unchanged(
    *,
    score: Decimal,
    confidence_lower: Decimal | None,
    confidence_upper: Decimal | None,
    sample_size: int | None,
    prev_score: Decimal,
    prev_confidence_lower: Decimal | None,
    prev_confidence_upper: Decimal | None,
    prev_sample_size: int | None,
) -> bool:
    """True when the *material observation* is identical to the previous one —
    snapshot identity and timestamps deliberately excluded. A new snapshot with
    the same score is a re-confirmation, not a new observation."""

    def norm(x: Decimal | None) -> str | None:
        return None if x is None else repr(x.normalize())

    return (
        norm(score) == norm(prev_score)
        and norm(confidence_lower) == norm(prev_confidence_lower)
        and norm(confidence_upper) == norm(prev_confidence_upper)
        and sample_size == prev_sample_size
    )


# ---------------------------------------------------------------------------
# pricing / performance keys


def pricing_fingerprint(
    *,
    model_variant_id: str,
    model_endpoint_id: str | None,
    input_price_per_million: Decimal | None,
    output_price_per_million: Decimal | None,
    cached_input_price: Decimal | None,
    currency: str,
    effective_from: str | None,
    source_id: str,
    observed_at: str | None = None,  # accepted and deliberately ignored
) -> str:
    payload = canonical_json(
        {
            "model_variant_id": model_variant_id,
            "model_endpoint_id": model_endpoint_id,
            "input_price_per_million": input_price_per_million,
            "output_price_per_million": output_price_per_million,
            "cached_input_price": cached_input_price,
            "currency": currency,
            "effective_from": effective_from,
            "source_id": source_id,
        }
    )
    return sha256_hex(payload)
