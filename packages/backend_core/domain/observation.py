"""Observation entities: evidence, pricing, performance, field observations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DECIMAL, BigInteger, DateTime, ForeignKey, Integer, String, Text

from ..db import Base, UUIDMixin, MYSQL_TABLE_KWARGS, utcnow
from sqlalchemy.orm import Mapped, mapped_column


class Evidence(UUIDMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = MYSQL_TABLE_KWARGS

    model_variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_variant.id")
    )
    capability_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("capability.id"))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)

    evidence_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="benchmark / vendor / community / internal_eval",
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)

    source_url: Mapped[str | None] = mapped_column(String(512))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    confidence: Mapped[str | None] = mapped_column(String(16), comment="high / medium / low")
    raw_content: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class EvidenceLink(UUIDMixin, Base):
    """Explicit evidence-to-fact links (target existence validated in app layer)."""

    __tablename__ = "evidence_link"
    __table_args__ = MYSQL_TABLE_KWARGS

    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="evaluation / pricing / performance / field_observation / model_event / benchmark_version",
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="supports / contradicts / explains"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class ModelPricing(UUIDMixin, Base):
    """Time-versioned pricing — never overwrite; append and close intervals."""

    __tablename__ = "model_pricing"
    __table_args__ = MYSQL_TABLE_KWARGS

    model_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_variant.id"), nullable=False, index=True
    )
    # NULL for model-level aggregates (e.g. AA median pricing on Free tier)
    model_endpoint_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_endpoint.id")
    )

    provider_name: Mapped[str | None] = mapped_column(String(128))

    input_price_per_million: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 6))
    output_price_per_million: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 6))
    cached_input_price: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 6))

    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")

    effective_from: Mapped[datetime | None] = mapped_column(DateTime)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime)

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(16))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36))

    # fingerprint fields: variant, endpoint, prices, currency,
    # effective_from, source_id — deliberately excludes snapshot/observed_at
    # so an unchanged price replayed from a new snapshot stays deduplicated
    pricing_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class ModelPerformance(UUIDMixin, Base):
    __tablename__ = "model_performance"
    __table_args__ = MYSQL_TABLE_KWARGS

    model_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_variant.id"), nullable=False, index=True
    )
    model_endpoint_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_endpoint.id")
    )

    provider_name: Mapped[str | None] = mapped_column(String(128))

    tokens_per_second: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2))
    time_to_first_token_ms: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2))
    latency_ms: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2))

    prompt_length: Mapped[int | None] = mapped_column(Integer)

    measured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    confidence: Mapped[str | None] = mapped_column(String(16))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36))

    performance_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class FieldObservation(UUIDMixin, Base):
    """V1: whitelist fields only (context_window / max_output_tokens).
    Canonical value is materialized on the entity; this table is the audit trail."""

    __tablename__ = "field_observation"
    __table_args__ = MYSQL_TABLE_KWARGS

    entity_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="model_variant / model_endpoint"
    )
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    field_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="V1: context_window / max_output_tokens"
    )
    value: Mapped[str] = mapped_column(String(256), nullable=False)

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))

    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(16))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36))

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
