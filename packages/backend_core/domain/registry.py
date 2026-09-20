"""Registry entities: Provider, Family, Release, Variant, Endpoint, Alias, Source."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)

from ..db import Base, TimestampMixin, UUIDMixin, MYSQL_TABLE_KWARGS, utcnow
from sqlalchemy.orm import Mapped, mapped_column


class Provider(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "provider"
    __table_args__ = MYSQL_TABLE_KWARGS

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="vendor / aggregator / platform"
    )
    website_url: Mapped[str | None] = mapped_column(String(512))
    country: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)


class Source(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "source"
    __table_args__ = MYSQL_TABLE_KWARGS

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="independent_eval / vendor / aggregator / internal"
    )
    reliability_level: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="high / medium / low"
    )
    base_url: Mapped[str | None] = mapped_column(String(512))
    api_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ModelFamily(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_family"
    __table_args__ = (
        UniqueConstraint("provider_id", "slug", name="uq_family_provider_slug"),
        MYSQL_TABLE_KWARGS,
    )

    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("provider.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class ModelRelease(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_release"
    __table_args__ = MYSQL_TABLE_KWARGS

    family_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_family.id"), nullable=False
    )
    # Circular FK to model_variant deliberately NOT enforced in DDL:
    # MySQL has no deferred constraints; validated at application layer,
    # backfilled by the seed / resolution service after variants exist.
    default_variant_id: Mapped[str | None] = mapped_column(String(36))

    canonical_name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    release_date: Mapped[date | None] = mapped_column(Date)
    knowledge_cutoff: Mapped[date | None] = mapped_column(Date)

    architecture_type: Mapped[str | None] = mapped_column(String(64))
    parameter_count: Mapped[int | None] = mapped_column(BigInteger)

    open_weight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    license: Mapped[str | None] = mapped_column(String(128))

    official_url: Mapped[str | None] = mapped_column(String(512))
    model_card_url: Mapped[str | None] = mapped_column(String(512))
    technical_report_url: Mapped[str | None] = mapped_column(String(512))

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(16))

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class ModelVariant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_variant"
    __table_args__ = (
        UniqueConstraint("model_release_id", "name", name="uq_variant_release_name"),
        MYSQL_TABLE_KWARGS,
    )

    model_release_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_release.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    variant_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="standard / thinking / preview / distilled / ..."
    )

    reasoning_level: Mapped[str | None] = mapped_column(
        String(32), comment="none / low / medium / high"
    )

    context_window: Mapped[int | None] = mapped_column(BigInteger)
    max_output_tokens: Mapped[int | None] = mapped_column(BigInteger)

    supports_text: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_image: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_audio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_video: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    supports_reasoning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_tool_calling: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_structured_output: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(16))


class ModelEndpoint(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_endpoint"
    __table_args__ = (
        UniqueConstraint("provider_id", "external_model_id", name="uq_endpoint_provider_extid"),
        MYSQL_TABLE_KWARGS,
    )

    model_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_variant.id"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(36), ForeignKey("provider.id"), nullable=False)

    external_model_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="provider-side model identifier"
    )

    endpoint_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="official_api / third_party_api / self_hosted"
    )
    api_base_url: Mapped[str | None] = mapped_column(String(512))

    # Endpoint-level limits may override variant-level values (e.g. OpenRouter truncation)
    context_window: Mapped[int | None] = mapped_column(BigInteger)
    max_output_tokens: Mapped[int | None] = mapped_column(BigInteger)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))


class ModelAlias(UUIDMixin, Base):
    __tablename__ = "model_alias"
    __table_args__ = (
        UniqueConstraint("source_id", "alias", name="uq_alias_source_alias"),
        MYSQL_TABLE_KWARGS,
    )

    model_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("model_variant.id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(256), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
