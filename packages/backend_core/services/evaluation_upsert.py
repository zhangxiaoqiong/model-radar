"""Evaluation upsert — the idempotent ingestion path for evaluation observations.

Rules (spec §8.3, plus review fix for daily bloat):
1. observation_fingerprint already exists          -> skip (pure replay)
2. identity latest observation materially equal   -> skip (re-confirmation)
3. identity exists, material fields changed       -> insert new row,
   supersedes previous, report action "superseded"
4. no prior observation for identity              -> insert (created)

The evaluation table is append-only: no row is ever updated in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import utcnow
from ..domain import Evaluation
from .fingerprints import (
    evaluation_identity_hash,
    observation_fields_unchanged,
    observation_fingerprint,
)


@dataclass
class UpsertResult:
    action: str  # created / skipped / reconfirmed / superseded
    evaluation_id: str
    identity_hash: str
    observation_fingerprint: str
    previous_evaluation_id: str | None = None
    previous_score: Decimal | None = None
    score: Decimal | None = None


def upsert_evaluation(
    session: Session,
    *,
    run_id: str,
    model_variant_id: str,
    model_endpoint_id: str | None,
    benchmark_id: str,
    benchmark_version_id: str | None,
    benchmark_metric_id: str,
    score: Decimal,
    evaluation_date: datetime | None,
    source_id: str,
    source_snapshot_id: str | None,
    evaluator: str | None,
    evaluation_type: str,
    sample_size: int | None,
    reasoning_setting: str | None = None,
    temperature: Decimal | None = None,
    random_seed: int | None = None,
    few_shot_count: int | None = None,
    harness: str | None = None,
    harness_version: str | None = None,
    agent_scaffold: str | None = None,
    agent_scaffold_version: str | None = None,
    dataset_revision: str | None = None,
    scorer_version: str | None = None,
    runtime_image: str | None = None,
    prompt_config: dict | None = None,
    decoding_config: dict | None = None,
    cost_usd: Decimal | None = None,
    confidence_lower: Decimal | None = None,
    confidence_upper: Decimal | None = None,
    confidence: str | None = None,
    external_evaluation_id: str | None = None,
    raw_payload: dict | None = None,
) -> UpsertResult:
    score = Decimal(str(score))
    temperature = Decimal(str(temperature)) if temperature is not None else None
    cost_usd = Decimal(str(cost_usd)) if cost_usd is not None else None
    confidence_lower = (
        Decimal(str(confidence_lower)) if confidence_lower is not None else None
    )
    confidence_upper = (
        Decimal(str(confidence_upper)) if confidence_upper is not None else None
    )
    identity_hash = evaluation_identity_hash(
        model_variant_id=model_variant_id,
        model_endpoint_id=model_endpoint_id,
        benchmark_id=benchmark_id,
        benchmark_version_id=benchmark_version_id,
        benchmark_metric_id=benchmark_metric_id,
        source_id=source_id,
        evaluator=evaluator,
        harness=harness,
        harness_version=harness_version,
        reasoning_setting=reasoning_setting,
        temperature=temperature,
        random_seed=random_seed,
        few_shot_count=few_shot_count,
        agent_scaffold=agent_scaffold,
        agent_scaffold_version=agent_scaffold_version,
        dataset_revision=dataset_revision,
        scorer_version=scorer_version,
        runtime_image=runtime_image,
        prompt_config=prompt_config,
        decoding_config=decoding_config,
    )
    fingerprint = observation_fingerprint(
        identity_hash,
        score=score,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        sample_size=sample_size,
        external_evaluation_id=external_evaluation_id,
        source_snapshot_id=source_snapshot_id,
    )

    # 1. pure replay
    existing = session.scalar(
        select(Evaluation).where(Evaluation.observation_fingerprint == fingerprint)
    )
    if existing is not None:
        return UpsertResult(
            action="skipped",
            evaluation_id=existing.id,
            identity_hash=identity_hash,
            observation_fingerprint=fingerprint,
        )

    # latest observation for this identity (append-only chain head)
    latest = session.scalar(
        select(Evaluation)
        .where(Evaluation.evaluation_identity_hash == identity_hash)
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
        .limit(1)
    )

    # 2. re-confirmation: same material observation from a new snapshot
    if latest is not None and observation_fields_unchanged(
        score=score,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        sample_size=sample_size,
        prev_score=latest.score,
        prev_confidence_lower=latest.confidence_lower,
        prev_confidence_upper=latest.confidence_upper,
        prev_sample_size=latest.sample_size,
    ):
        latest.last_confirmed_at = utcnow()
        latest.last_confirmed_snapshot_id = source_snapshot_id
        latest.confirmation_count += 1
        session.flush()
        return UpsertResult(
            action="reconfirmed",
            evaluation_id=latest.id,
            identity_hash=identity_hash,
            observation_fingerprint=fingerprint,
        )

    # 3./4. append a new immutable observation
    evaluation = Evaluation(
        run_id=run_id,
        model_variant_id=model_variant_id,
        model_endpoint_id=model_endpoint_id,
        benchmark_id=benchmark_id,
        benchmark_version_id=benchmark_version_id,
        benchmark_metric_id=benchmark_metric_id,
        score=score,
        evaluation_date=evaluation_date,
        source_id=source_id,
        source_snapshot_id=source_snapshot_id,
        evaluator=evaluator,
        evaluation_type=evaluation_type,
        sample_size=sample_size,
        reasoning_setting=reasoning_setting,
        temperature=temperature,
        random_seed=random_seed,
        few_shot_count=few_shot_count,
        harness=harness,
        harness_version=harness_version,
        agent_scaffold=agent_scaffold,
        agent_scaffold_version=agent_scaffold_version,
        dataset_revision=dataset_revision,
        scorer_version=scorer_version,
        runtime_image=runtime_image,
        prompt_config=prompt_config,
        decoding_config=decoding_config,
        cost_usd=cost_usd,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        confidence=confidence,
        external_evaluation_id=external_evaluation_id,
        evaluation_identity_hash=identity_hash,
        observation_fingerprint=fingerprint,
        supersedes_evaluation_id=latest.id if latest is not None else None,
        raw_payload=raw_payload,
        created_at=utcnow(),
    )
    session.add(evaluation)
    session.flush()

    return UpsertResult(
        action="superseded" if latest is not None else "created",
        evaluation_id=evaluation.id,
        identity_hash=identity_hash,
        observation_fingerprint=fingerprint,
        previous_evaluation_id=latest.id if latest is not None else None,
        previous_score=latest.score if latest is not None else None,
        score=score,
    )
