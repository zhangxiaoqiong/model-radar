"""Operations: snapshots, events, pipelines, resolution queue, insights, audit."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DECIMAL, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from ..db import Base, TimestampMixin, UUIDMixin, MYSQL_TABLE_KWARGS, utcnow
from sqlalchemy.orm import Mapped, mapped_column


class SourceSnapshot(UUIDMixin, Base):
    """Metadata for a raw source payload. Payload itself lives in external storage
    (file / object store) at `storage_uri`; small payloads may be inlined via
    source_snapshot_blob. Expiry deletes the payload, never this metadata row."""

    __tablename__ = "source_snapshot"
    __table_args__ = (
        UniqueConstraint("source_id", "checksum", name="uq_snapshot_source_checksum"),
        MYSQL_TABLE_KWARGS,
    )

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_encoding: Mapped[str | None] = mapped_column(String(32))
    content_length: Mapped[int] = mapped_column(nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA-256 of payload")
    stats: Mapped[dict | None] = mapped_column(JSON)
    license_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="retain",
        comment="retain / metadata_only / no_redistribution",
    )
    redaction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    retention_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class ModelEvent(UUIDMixin, Base):
    __tablename__ = "model_event"
    __table_args__ = MYSQL_TABLE_KWARGS

    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # at least one business subject is required (app-layer validated)
    model_release_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_release.id"))
    model_variant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_variant.id"))
    model_endpoint_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_endpoint.id"))
    benchmark_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("benchmark.id"))
    benchmark_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("benchmark_version.id"))
    evaluation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation.id"))
    model_pricing_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_pricing.id"))
    model_performance_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("model_performance.id"))
    field_observation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("field_observation.id"))

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)

    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    before_value: Mapped[dict | None] = mapped_column(JSON)
    after_value: Mapped[dict | None] = mapped_column(JSON)

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))
    change_detection_run_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_before_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_after_id: Mapped[str | None] = mapped_column(String(36))

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class EntityResolutionQueue(UUIDMixin, Base):
    __tablename__ = "entity_resolution_queue"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "record_type", "external_id",
            name="uq_resolution_source_type_external",
        ),
        MYSQL_TABLE_KWARGS,
    )

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    record_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="model_variant",
        comment="V1 fixed to model_variant; benchmark/endpoint in V1b+",
    )
    external_id: Mapped[str | None] = mapped_column(String(256))
    external_name: Mapped[str] = mapped_column(String(256), nullable=False)

    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    suggested_variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_variant.id")
    )
    suggested_release_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_release.id")
    )

    match_confidence: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    match_evidence: Mapped[dict | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="pending / approved / rejected / created / mapped",
    )

    resolution_note: Mapped[str | None] = mapped_column(String(512))

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resolved_by: Mapped[str | None] = mapped_column(String(128))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class PipelineRun(UUIDMixin, Base):
    __tablename__ = "pipeline_run"
    __table_args__ = MYSQL_TABLE_KWARGS

    pipeline_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="daily_sync / manual / backfill"
    )
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, comment="schedule / manual")

    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="pending / running / success / partial / failed",
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    error_message: Mapped[str | None] = mapped_column(Text)

    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class PipelineStageRun(UUIDMixin, Base):
    __tablename__ = "pipeline_stage_run"
    __table_args__ = MYSQL_TABLE_KWARGS

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("pipeline_run.id"), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="pending / running / success / failed / skipped",
    )

    detail: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    retry_backoff_seconds: Mapped[int | None] = mapped_column(Integer)
    critical: Mapped[bool] = mapped_column(nullable=False, default=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class AdminAuditLog(UUIDMixin, Base):
    __tablename__ = "admin_audit_log"
    __table_args__ = MYSQL_TABLE_KWARGS

    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(36))
    before_value: Mapped[dict | None] = mapped_column(JSON)
    after_value: Mapped[dict | None] = mapped_column(JSON)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


# ---------------------------------------------------------------------------
# Derived (recomputable) data — normalization & capability snapshots (V1c)

class NormalizationRun(UUIDMixin, Base):
    __tablename__ = "normalization_run"
    __table_args__ = MYSQL_TABLE_KWARGS

    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    cohort_definition: Mapped[dict | None] = mapped_column(JSON)
    as_of_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class NormalizedEvaluation(UUIDMixin, Base):
    __tablename__ = "normalized_evaluation"
    __table_args__ = (
        UniqueConstraint("normalization_run_id", "evaluation_id", name="uq_normeval_run_eval"),
        MYSQL_TABLE_KWARGS,
    )

    normalization_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("normalization_run.id"), nullable=False
    )
    evaluation_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation.id"), nullable=False)
    normalized_score: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    sample_count: Mapped[int] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class CapabilityScoreSnapshot(UUIDMixin, Base):
    __tablename__ = "capability_score_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "normalization_run_id", "model_variant_id", "capability_id",
            name="uq_capss_run_variant_cap",
        ),
        MYSQL_TABLE_KWARGS,
    )

    normalization_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("normalization_run.id"), nullable=False
    )
    model_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_variant.id"), nullable=False
    )
    capability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("capability.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    evidence_summary: Mapped[dict | None] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ---------------------------------------------------------------------------
# LLM-generated insights (narrative only — never facts; spec §33/§34)

class GeneratedInsight(UUIDMixin, Base):
    __tablename__ = "generated_insight"
    __table_args__ = MYSQL_TABLE_KWARGS

    model_variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_variant.id")
    )
    insight_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="model_summary / comparison / change_brief"
    )

    model_used: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)

    input_evidence_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="generation input snapshot only; authoritative links below"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class GeneratedInsightEvidence(Base):
    __tablename__ = "generated_insight_evidence"
    __table_args__ = MYSQL_TABLE_KWARGS

    generated_insight_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generated_insight.id"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence.id"), primary_key=True)
