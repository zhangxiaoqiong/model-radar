"""Transactional sync pipeline with a MySQL advisory lease."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend_core.db import new_uuid, utcnow
from backend_core.domain import (
    Benchmark,
    BenchmarkMetric,
    BenchmarkVersion,
    EntityResolutionQueue,
    EvaluationRun,
    ModelAlias,
    ModelFamily,
    ModelRelease,
    PipelineRun,
    PipelineStageRun,
    Provider,
)
from backend_core.services import upsert_evaluation

from .entity_resolution import match_external_model
from .normalizers import normalize_aa_evaluation
from .snapshot_store import store_snapshot

STAGE_ORDER = ["fetch_snapshot", "entity_resolution", "upsert_evaluations"]
LEASE_SECONDS = 15 * 60


class PipelineBusyError(RuntimeError):
    pass


class _StageTracker:
    def __init__(self, session: Session, run_id: str):
        self.session = session
        self.run_id = run_id
        self.stages: dict[str, PipelineStageRun] = {}

    def create_all(self) -> None:
        for name in STAGE_ORDER:
            stage = PipelineStageRun(
                run_id=self.run_id,
                stage_name=name,
                critical=name != "upsert_evaluations",
                status="pending",
                attempt=0,
                max_attempts=1,
            )
            self.session.add(stage)
            self.stages[name] = stage
        self.session.flush()

    def start(self, name: str) -> None:
        stage = self.stages[name]
        stage.status = "running"
        stage.started_at = utcnow()
        stage.attempt += 1
        self.session.flush()

    def succeed(self, name: str, detail: dict) -> None:
        stage = self.stages[name]
        stage.status = "success"
        stage.detail = detail
        stage.finished_at = utcnow()
        self.session.flush()

    def fail(self, name: str, error: Exception) -> None:
        stage = self.stages[name]
        stage.status = "failed"
        stage.error_message = f"{type(error).__name__}: {error}"
        stage.finished_at = utcnow()
        self.session.flush()

    def skip_rest(self, from_index: int) -> None:
        for name in STAGE_ORDER[from_index:]:
            self.stages[name].status = "skipped"
            self.stages[name].finished_at = utcnow()
        self.session.flush()


def _lease_name(pipeline_type: str) -> str:
    return f"llm-observatory:{pipeline_type}"[:64]


def _acquire_lease(session: Session, pipeline_type: str) -> str:
    name = _lease_name(pipeline_type)
    acquired = session.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": name})
    if acquired != 1:
        raise PipelineBusyError(f"pipeline {pipeline_type!r} is already running")
    return name


def _release_lease(session: Session, name: str) -> None:
    session.scalar(text("SELECT RELEASE_LOCK(:name)"), {"name": name})


def _mark_run_failed(
    run: PipelineRun,
    tracker: _StageTracker,
    stage_name: str,
    error: Exception,
    *,
    skip_from: int | None = None,
    partial: bool = False,
) -> PipelineRun:
    tracker.fail(stage_name, error)
    if skip_from is not None:
        tracker.skip_rest(skip_from)
    run.status = "partial" if partial else "failed"
    run.error_message = f"{type(error).__name__}: {error}"
    run.finished_at = utcnow()
    run.heartbeat_at = utcnow()
    return run


def recover_stale_runs(session: Session, *, now: datetime | None = None) -> int:
    """Close expired runs so a crashed worker cannot leave them running forever."""
    cutoff = now or utcnow()
    runs = session.scalars(
        select(PipelineRun)
        .where(
            PipelineRun.status == "running",
            PipelineRun.lease_expires_at.is_not(None),
            PipelineRun.lease_expires_at < cutoff,
        )
        .with_for_update()
    ).all()
    for run in runs:
        run.status = "failed"
        run.finished_at = cutoff
        run.error_message = "StaleRunError: worker lease expired"
        stages = session.scalars(
            select(PipelineStageRun).where(PipelineStageRun.run_id == run.id)
        ).all()
        for stage in stages:
            if stage.status == "running":
                stage.status = "failed"
                stage.error_message = "StaleRunError: worker lease expired"
                stage.finished_at = cutoff
            elif stage.status == "pending":
                stage.status = "skipped"
                stage.finished_at = cutoff
    if runs:
        session.flush()
    return len(runs)


def run_sync_pipeline(
    session: Session,
    *,
    source_id: str,
    fetch_fn,
    pipeline_type: str = "daily_sync",
    trigger: str = "schedule",
    existing_run: PipelineRun | None = None,
) -> PipelineRun:
    """Execute one run; failures are persisted on the run instead of escaping."""
    lock_name = _acquire_lease(session, pipeline_type)
    try:
        now = utcnow()
        run = existing_run or PipelineRun(
            id=new_uuid(), pipeline_type=pipeline_type, trigger=trigger, status="pending"
        )
        if existing_run is not None and existing_run.status != "pending":
            raise ValueError(f"existing pipeline run must be pending, got {existing_run.status}")
        if existing_run is None:
            session.add(run)
        run.status = "running"
        run.started_at = now
        run.lease_owner = "sync-worker"
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        run.heartbeat_at = now
        run.attempt = (run.attempt or 0) + 1
        session.flush()

        tracker = _StageTracker(session, run.id)
        tracker.create_all()

        rows: list[dict] = []
        snapshot = None
        tracker.start("fetch_snapshot")
        stage_tx = session.begin_nested()
        try:
            rows = fetch_fn()
            if not isinstance(rows, list):
                raise TypeError("fetch_fn must return a list of rows")
            payload = json.dumps(rows, sort_keys=True, ensure_ascii=False).encode("utf-8")
            snapshot = store_snapshot(session, source_id=source_id, payload=payload)
            tracker.succeed(
                "fetch_snapshot", {"row_count": len(rows), "snapshot_id": snapshot.id}
            )
            stage_tx.commit()
        except Exception as exc:
            stage_tx.rollback()
            return _mark_run_failed(run, tracker, "fetch_snapshot", exc, skip_from=1)

        tracker.start("entity_resolution")
        stage_tx = session.begin_nested()
        try:
            aliases = [
                (a.alias, a.model_variant_id)
                for a in session.scalars(
                    select(ModelAlias).where(ModelAlias.source_id == source_id)
                )
            ]
            release_rows = session.execute(
                select(ModelRelease, ModelFamily, Provider)
                .join(ModelFamily, ModelRelease.family_id == ModelFamily.id)
                .join(Provider, ModelFamily.provider_id == Provider.id)
            ).all()
            releases = [
                (r.slug, r.canonical_name, r.default_variant_id, provider.slug)
                for r, _family, provider in release_rows
                if r.default_variant_id
            ]

            matched: list[tuple[dict, str]] = []
            unmatched: list[tuple[dict, object]] = []
            for row in rows:
                name = str(row.get("model_name") or "").strip()
                if not name:
                    continue
                result = match_external_model(
                    name,
                    aliases,
                    releases,
                    external_provider=row.get("provider_slug"),
                )
                if result.variant_id:
                    matched.append((row, result.variant_id))
                else:
                    unmatched.append((row, result))

            queued = 0
            queued_external_ids = set(
                session.scalars(
                    select(EntityResolutionQueue.external_id).where(
                        EntityResolutionQueue.source_id == source_id,
                        EntityResolutionQueue.record_type == "model_variant",
                    )
                ).all()
            )
            for row, result in unmatched:
                name = str(row.get("model_name"))
                external_id = str(row.get("model_id") or row.get("id") or name)
                if external_id not in queued_external_ids:
                    session.add(
                        EntityResolutionQueue(
                            source_id=source_id,
                            record_type="model_variant",
                            external_id=external_id,
                            external_name=name,
                            raw_payload=row,
                            suggested_variant_id=result.suggested_variant_id,
                            match_confidence=result.confidence,
                            match_evidence=result.evidence,
                            status="pending",
                        )
                    )
                    queued_external_ids.add(external_id)
                    queued += 1
            tracker.succeed(
                "entity_resolution",
                {"matched": len(matched), "unmatched": len(unmatched), "queued": queued},
            )
            stage_tx.commit()
        except Exception as exc:
            stage_tx.rollback()
            return _mark_run_failed(run, tracker, "entity_resolution", exc, skip_from=2)

        tracker.start("upsert_evaluations")
        stage_tx = session.begin_nested()
        try:
            eval_run = EvaluationRun(
                id=new_uuid(),
                run_type="external",
                engine="external_aggregate",
                source_id=source_id,
                source_snapshot_id=snapshot.id if snapshot else None,
                status="running",
                started_at=utcnow(),
            )
            session.add(eval_run)
            session.flush()

            upserted = replayed = skipped_benchmark = 0
            for row, variant_id in matched:
                try:
                    canonical = normalize_aa_evaluation(row, source_id=source_id)
                except (ValueError, KeyError, TypeError):
                    skipped_benchmark += 1
                    continue

                bench = session.scalar(
                    select(Benchmark).where(Benchmark.slug == canonical["benchmark_slug"])
                )
                if bench is None:
                    skipped_benchmark += 1
                    continue
                version = session.scalar(
                    select(BenchmarkVersion)
                    .where(BenchmarkVersion.benchmark_id == bench.id)
                    .order_by(BenchmarkVersion.created_at.desc())
                    .limit(1)
                )
                if version is None:
                    skipped_benchmark += 1
                    continue
                metric = session.scalar(
                    select(BenchmarkMetric)
                    .where(BenchmarkMetric.benchmark_version_id == version.id)
                    .limit(1)
                )
                if metric is None:
                    skipped_benchmark += 1
                    continue

                evaluation_date = None
                if canonical["evaluation_date"]:
                    try:
                        evaluation_date = datetime.fromisoformat(canonical["evaluation_date"])
                    except ValueError:
                        pass

                result = upsert_evaluation(
                    session,
                    run_id=eval_run.id,
                    model_variant_id=variant_id,
                    model_endpoint_id=None,
                    benchmark_id=bench.id,
                    benchmark_version_id=version.id,
                    benchmark_metric_id=metric.id,
                    score=Decimal(canonical["score"]),
                    evaluation_date=evaluation_date,
                    source_id=source_id,
                    source_snapshot_id=snapshot.id if snapshot else None,
                    evaluator="Artificial Analysis",
                    sample_size=canonical["sample_size"],
                    evaluation_type="external",
                    external_evaluation_id=canonical["external_evaluation_id"],
                    raw_payload=canonical["raw"],
                )
                if result.action in ("skipped", "reconfirmed"):
                    replayed += 1
                else:
                    upserted += 1

            eval_run.status = "success"
            eval_run.finished_at = utcnow()
            tracker.succeed(
                "upsert_evaluations",
                {
                    "upserted": upserted,
                    "replayed": replayed,
                    "skipped_unknown_benchmark": skipped_benchmark,
                },
            )
            run.status = "partial" if (skipped_benchmark or unmatched) else "success"
            stage_tx.commit()
        except Exception as exc:
            stage_tx.rollback()
            return _mark_run_failed(
                run, tracker, "upsert_evaluations", exc, partial=True
            )

        run.finished_at = utcnow()
        run.heartbeat_at = utcnow()
        session.flush()
        return run
    finally:
        _release_lease(session, lock_name)
