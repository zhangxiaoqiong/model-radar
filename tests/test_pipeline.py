"""Sync pipeline orchestrator tests (DB-backed, fake source fetch)."""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

os.environ.setdefault("DB_NAME", "model_radar_test")

from sqlalchemy import select  # noqa: E402


@pytest.fixture()
def engine():
    from sqlalchemy import create_engine
    from backend_core.config import get_settings
    from backend_core.db import Base
    import backend_core.domain  # noqa: F401  (register all metadata before drop_all)

    get_settings.cache_clear()
    eng = create_engine(get_settings().database_url, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    from backend_core.db import make_session_factory

    s = make_session_factory(engine)()
    yield s
    s.rollback()
    s.close()


@pytest.fixture()
def registry(session):
    """Provider/source/family/release/variant + benchmark chain."""
    from backend_core.domain import (
        Benchmark, BenchmarkMetric, BenchmarkVersion, ModelFamily,
        ModelRelease, ModelVariant, Provider, Source,
    )

    provider = Provider(slug="openai", name="OpenAI", provider_type="vendor")
    source = Source(slug="artificial_analysis", name="AA",
                    source_type="independent_eval", reliability_level="high",
                    api_available=True)
    session.add_all([provider, source])
    session.flush()
    family = ModelFamily(provider_id=provider.id, slug="gpt", name="GPT")
    session.add(family)
    session.flush()
    release = ModelRelease(family_id=family.id, canonical_name="GPT-5.2", slug="gpt-5.2")
    session.add(release)
    session.flush()
    variant = ModelVariant(model_release_id=release.id, name="standard",
                           variant_type="standard")
    session.add(variant)
    session.flush()
    release.default_variant_id = variant.id
    bench = Benchmark(slug="gpqa-diamond", name="GPQA Diamond", category="reasoning",
                      source_id=source.id)
    session.add(bench)
    session.flush()
    version = BenchmarkVersion(benchmark_id=bench.id, version="diamond")
    session.add(version)
    session.flush()
    metric = BenchmarkMetric(benchmark_version_id=version.id, slug="accuracy",
                             name="Accuracy", dataset_split="", unit="percent",
                             score_direction="higher_better",
                             normalization_method="minmax")
    session.add(metric)
    session.commit()
    return {"source_id": source.id, "variant_id": variant.id,
            "benchmark_id": bench.id, "version_id": version.id,
            "metric_id": metric.id}


def test_pipeline_success_upserts_and_enqueues(engine, session, registry, tmp_path, monkeypatch):
    from backend_core.domain import EntityResolutionQueue, Evaluation, EvaluationRun
    from ingestion.pipeline import run_sync_pipeline

    monkeypatch.setattr("ingestion.snapshot_store.raw_dir", lambda: tmp_path)

    rows = [
        {"model_name": "gpt-5.2", "index_name": "gpqa-diamond", "value": 48.2,
         "sample_size": 500, "id": "aa-1"},
        {"model_name": "gpt-5.2", "index_name": "gpqa-diamond", "value": 48.2,
         "sample_size": 500, "id": "aa-1"},  # pure replay
        {"model_name": "mystery-model-x", "index_name": "gpqa-diamond",
         "value": 12.0, "id": "aa-2", "model_id": "aa-model-2"},  # unmatched -> one queue per model
        {"model_name": "mystery-model-x", "index_name": "another-index",
         "value": 15.0, "id": "aa-2b", "model_id": "aa-model-2"},
        {"model_name": "mystery-model-x", "index_name": "gpqa-diamond",
         "value": 12.0, "id": "aa-2c", "model_id": "aa-model-2"},
        {"model_name": "gpt-5.2", "index_name": "unknown-benchmark",
         "value": 90.0, "id": "aa-3"},  # unknown benchmark -> skipped
    ]

    run = run_sync_pipeline(session, source_id=registry["source_id"],
                            fetch_fn=lambda: rows)
    session.commit()

    assert run.status == "partial"  # unknown benchmark skipped

    evals = session.scalars(
        select(Evaluation).where(Evaluation.model_variant_id == registry["variant_id"])
    ).all()
    assert len(evals) == 1  # replay + reconfirm did not duplicate

    queue = session.scalars(
        select(EntityResolutionQueue).where(
            EntityResolutionQueue.external_name == "mystery-model-x")
    ).all()
    assert len(queue) == 1
    assert queue[0].status == "pending"

    # run rows recorded: one run + stages
    from backend_core.domain import PipelineStageRun
    stages = session.scalars(
        select(PipelineStageRun).where(PipelineStageRun.run_id == run.id)
    ).all()
    assert {s.stage_name for s in stages} >= {"fetch_snapshot", "entity_resolution",
                                              "upsert_evaluations"}

    # a second identical pipeline run must not create anything new
    run2 = run_sync_pipeline(session, source_id=registry["source_id"],
                             fetch_fn=lambda: rows)
    session.commit()
    evals2 = session.scalars(
        select(Evaluation).where(Evaluation.model_variant_id == registry["variant_id"])
    ).all()
    assert len(evals2) == 1
    queue2 = session.scalars(
        select(EntityResolutionQueue).where(
            EntityResolutionQueue.external_name == "mystery-model-x")
    ).all()
    assert len(queue2) == 1
    assert run2.status == "partial"


def test_pipeline_critical_fetch_failure_blocks_downstream(engine, session, registry, tmp_path, monkeypatch):
    from backend_core.domain import PipelineStageRun
    from ingestion.pipeline import run_sync_pipeline

    monkeypatch.setattr("ingestion.snapshot_store.raw_dir", lambda: tmp_path)

    def boom():
        raise RuntimeError("network down")

    run = run_sync_pipeline(session, source_id=registry["source_id"], fetch_fn=boom)
    session.commit()

    assert run.status == "failed"
    assert run.error_message is not None
    stages = session.scalars(
        select(PipelineStageRun).where(PipelineStageRun.run_id == run.id)
    ).all()
    fetch_stage = [s for s in stages if s.stage_name == "fetch_snapshot"][0]
    assert fetch_stage.status == "failed"
    downstream = [s for s in stages if s.stage_name != "fetch_snapshot"]
    assert all(s.status == "skipped" for s in downstream)
    # failed run must have a run row recorded too
    from backend_core.domain import EvaluationRun
    assert session.scalars(select(EvaluationRun)).all() == []


def test_pipeline_consumes_existing_manual_run_and_recovers_from_db_error(
    engine, session, registry, tmp_path, monkeypatch
):
    from backend_core.domain import PipelineRun, PipelineStageRun
    from ingestion.pipeline import run_sync_pipeline

    monkeypatch.setattr("ingestion.snapshot_store.raw_dir", lambda: tmp_path)
    pending = PipelineRun(
        pipeline_type="daily_sync", trigger="manual", status="pending"
    )
    session.add(pending)
    session.commit()
    pending_id = pending.id

    # The missing source violates the snapshot FK during flush. The stage
    # savepoint must roll back while leaving the run writable for diagnostics.
    run = run_sync_pipeline(
        session,
        source_id="missing-source",
        fetch_fn=lambda: [],
        trigger="manual",
        existing_run=pending,
    )
    session.commit()

    assert run.id == pending_id
    assert run.status == "failed"
    assert "IntegrityError" in run.error_message
    stages = session.scalars(
        select(PipelineStageRun).where(PipelineStageRun.run_id == pending_id)
    ).all()
    assert {stage.stage_name: stage.status for stage in stages} == {
        "fetch_snapshot": "failed",
        "entity_resolution": "skipped",
        "upsert_evaluations": "skipped",
    }


def test_recover_stale_pipeline_run(session):
    from backend_core.db import utcnow
    from backend_core.domain import PipelineRun, PipelineStageRun
    from ingestion.pipeline import recover_stale_runs

    expired = utcnow() - timedelta(minutes=1)
    run = PipelineRun(
        pipeline_type="daily_sync",
        trigger="schedule",
        status="running",
        lease_expires_at=expired,
    )
    session.add(run)
    session.flush()
    session.add_all([
        PipelineStageRun(run_id=run.id, stage_name="fetch_snapshot", status="running"),
        PipelineStageRun(run_id=run.id, stage_name="entity_resolution", status="pending"),
    ])
    session.commit()

    assert recover_stale_runs(session) == 1
    session.commit()
    session.refresh(run)
    assert run.status == "failed"
    assert "lease expired" in run.error_message
    stages = session.scalars(
        select(PipelineStageRun).where(PipelineStageRun.run_id == run.id)
    ).all()
    assert {stage.stage_name: stage.status for stage in stages} == {
        "fetch_snapshot": "failed",
        "entity_resolution": "skipped",
    }


def test_discovery_adds_recent_models_idempotently(session, registry, tmp_path, monkeypatch):
    from datetime import date
    from backend_core.domain import ModelAlias, ModelRelease
    from ingestion.catalog_discovery import discover_aa_models

    monkeypatch.setattr("ingestion.snapshot_store.raw_dir", lambda: tmp_path)
    models = [
        {
            "id": "new-1", "name": "Fresh Model (high)", "slug": "fresh-model",
            "release_date": "2026-09-01",
            "model_creator": {"name": "New Vendor"},
            "evaluations": {"artificial_analysis_intelligence_index": 42},
        },
        {
            "id": "old-1", "name": "Old Model", "slug": "old-model",
            "release_date": "2025-09-01",
            "model_creator": {"name": "New Vendor"},
        },
    ]
    first = discover_aa_models(
        session, source_id=registry["source_id"], models=models, today=date(2026, 9, 22)
    )
    session.commit()
    second = discover_aa_models(
        session, source_id=registry["source_id"], models=models, today=date(2026, 9, 22)
    )
    session.commit()

    assert first == {"recent": 1, "created": 1, "updated": 0}
    assert second == {"recent": 1, "created": 0, "updated": 1}
    release = session.scalar(select(ModelRelease).where(ModelRelease.canonical_name == "Fresh Model (high)"))
    assert release is not None
    assert release.release_date == date(2026, 9, 1)
    assert release.source_id == registry["source_id"]
    assert release.source_snapshot_id is not None
    assert release.default_variant_id is not None
    alias = session.scalar(select(ModelAlias).where(ModelAlias.alias == "fresh-model"))
    assert alias.model_variant_id == release.default_variant_id
    assert session.scalar(select(ModelRelease).where(ModelRelease.canonical_name == "Old Model")) is None
