"""Benchmark registry + capability taxonomy."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    DECIMAL,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from ..db import Base, TimestampMixin, UUIDMixin, MYSQL_TABLE_KWARGS, utcnow
from sqlalchemy.orm import Mapped, mapped_column


class Benchmark(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "benchmark"
    __table_args__ = MYSQL_TABLE_KWARGS

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    category: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)

    official_url: Mapped[str | None] = mapped_column(String(512))

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(16))

    dataset_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dynamic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contamination_risk: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class BenchmarkVersion(UUIDMixin, Base):
    __tablename__ = "benchmark_version"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "version", name="uq_benchver_bench_version"),
        MYSQL_TABLE_KWARGS,
    )

    benchmark_id: Mapped[str] = mapped_column(String(36), ForeignKey("benchmark.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date)
    dataset_size: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source.id"))
    source_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class BenchmarkMetric(UUIDMixin, Base):
    __tablename__ = "benchmark_metric"
    __table_args__ = (
        # dataset_split NOT NULL DEFAULT '' — MySQL UNIQUE ignores NULLs,
        # a NULL split would allow unlimited duplicates (review finding #2).
        UniqueConstraint(
            "benchmark_version_id", "slug", "dataset_split", name="uq_metric_ver_slug_split"
        ),
        MYSQL_TABLE_KWARGS,
    )

    benchmark_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_version.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_split: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )

    unit: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="percent / ratio / elo / milliseconds / ..."
    )

    score_direction: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="higher_better / lower_better"
    )
    normalization_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="minmax", comment="minmax / percentile / none / custom"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Capability(UUIDMixin, Base):
    __tablename__ = "capability"
    __table_args__ = MYSQL_TABLE_KWARGS

    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("capability.id"))
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class BenchmarkCapabilityMap(Base):
    __tablename__ = "benchmark_capability_map"
    __table_args__ = MYSQL_TABLE_KWARGS

    benchmark_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark.id"), primary_key=True
    )
    capability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("capability.id"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=False, default=1.0)
