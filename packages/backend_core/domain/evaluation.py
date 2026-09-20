"""Evaluation warehouse: run (execution) + evaluation (immutable observation)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DECIMAL, BigInteger, DateTime, ForeignKey, Integer, String, Text

from ..db import Base, UUIDMixin, MYSQL_TABLE_KWARGS, utcnow
from sqlalchemy.orm import Mapped, mapped_column


class EvaluationRun(UUIDMixin, Base):
    __tablename__ = "evaluation_run"
    __table_args__ = MYSQL_TABLE_KWARGS

    run_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="external / internal"
    )
    engine: Mapped[str | None] = mapped_column(
        String(32), comment="promptfoo / lm_eval / external_aggregate"
    )

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))
    source_snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_snapshot.id")
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="pending / running / success / failed / partial / cancelled",
    )

    # Worker lease (used from V1d onwards for internal eval workers)
    worker_id: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    config: Mapped[dict | None] = mapped_column(JSON)
    cost_usd: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 4))

    queued_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Evaluation(UUIDMixin, Base):
    """One immutable observation of a score. Never updated in place —
    a changed score creates a new row chained via supersedes_evaluation_id."""

    __tablename__ = "evaluation"
    __table_args__ = MYSQL_TABLE_KWARGS

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluation_run.id"), nullable=False, index=True
    )

    model_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_variant.id"), nullable=False, index=True
    )
    # Set when the serving channel is known (internal evals: required).
    model_endpoint_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_endpoint.id")
    )

    benchmark_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark.id"), nullable=False, index=True
    )
    # Nullable on purpose: external aggregates (e.g. AA headline indices) often
    # carry no benchmark version; presentation layer must show "version unknown".
    benchmark_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("benchmark_version.id")
    )
    benchmark_metric_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_metric.id"), nullable=False
    )

    score: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)

    evaluation_date: Mapped[datetime | None] = mapped_column(DateTime)

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_snapshot.id")
    )

    evaluator: Mapped[str | None] = mapped_column(String(128))
    evaluation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="external / vendor / internal"
    )

    sample_size: Mapped[int | None] = mapped_column(Integer)

    reasoning_setting: Mapped[str | None] = mapped_column(String(64))
    temperature: Mapped[Decimal | None] = mapped_column(DECIMAL(5, 3))
    random_seed: Mapped[int | None] = mapped_column(BigInteger)
    few_shot_count: Mapped[int | None] = mapped_column(Integer)

    harness: Mapped[str | None] = mapped_column(String(64))
    harness_version: Mapped[str | None] = mapped_column(String(32))

    agent_scaffold: Mapped[str | None] = mapped_column(String(64))
    agent_scaffold_version: Mapped[str | None] = mapped_column(String(64))

    dataset_revision: Mapped[str | None] = mapped_column(String(128))
    scorer_version: Mapped[str | None] = mapped_column(String(64))
    runtime_image: Mapped[str | None] = mapped_column(String(256))

    prompt_config: Mapped[dict | None] = mapped_column(JSON)
    decoding_config: Mapped[dict | None] = mapped_column(JSON)

    cost_usd: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 4))

    confidence_lower: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 4))
    confidence_upper: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 4))
    confidence: Mapped[str | None] = mapped_column(String(16))

    external_evaluation_id: Mapped[str | None] = mapped_column(String(256))

    # Stable identity of Model x Benchmark x config (see services.fingerprints)
    evaluation_identity_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    # Immutable observation version key — replay of the same observation is a no-op
    observation_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )

    supersedes_evaluation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("evaluation.id")
    )

    # Material result fields above remain immutable. These fields only record
    # that a later source snapshot re-confirmed the same observation.
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_confirmed_snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_snapshot.id")
    )
    confirmation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
