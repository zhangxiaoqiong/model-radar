"""TDD: evaluation upsert semantics against a real MySQL test database.

Spec §8.3 + review fix #1:
- pure replay (same fingerprint)        -> no new row
- re-confirmation (identity, same score)-> no new row (no daily bloat)
- changed score                          -> new row + supersedes chain + change flag
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

os.environ.setdefault("DB_NAME", "model_radar_test")

from sqlalchemy import select  # noqa: E402

from backend_core.db import create_db_engine, make_session_factory, utcnow  # noqa: E402
from backend_core.domain import (  # noqa: E402
    Benchmark,
    BenchmarkMetric,
    BenchmarkVersion,
    Evaluation,
    EvaluationRun,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    Provider,
    Source,
    SourceSnapshot,
)
from backend_core.services.evaluation_upsert import upsert_evaluation  # noqa: E402

pytestmark = []


@pytest.fixture(scope="module")
def session_factory():
    from backend_core.config import get_settings

    get_settings.cache_clear()
    engine = create_db_engine(get_settings().database_url)
    yield make_session_factory(engine)
    engine.dispose()


@pytest.fixture()
def session(session_factory):
    s = session_factory()
    yield s
    s.rollback()
    s.close()


@pytest.fixture()
def ctx(session):
    """Minimal registry context: provider -> family -> release -> variant, benchmark, source."""
    import uuid as _uuid

    suffix = _uuid.uuid4().hex[:8]
    provider = Provider(slug=f"test-prov-{suffix}", name="Test Provider",
                        provider_type="vendor")
    session.add(provider)
    session.flush()
    family = ModelFamily(provider_id=provider.id, slug=f"test-fam-{suffix}",
                         name="Test Family")
    session.add(family)
    session.flush()
    release = ModelRelease(family_id=family.id, canonical_name="Test Model X",
                           slug=f"test-model-x-{suffix}")
    session.add(release)
    session.flush()
    variant = ModelVariant(model_release_id=release.id, name="standard",
                           variant_type="standard", supports_tool_calling=True)
    session.add(variant)
    session.flush()
    source = Source(slug=f"test-src-{suffix}", name="Test Source",
                    source_type="independent_eval", reliability_level="high")
    session.add(source)
    session.flush()
    snapshots = {}
    for label in ("snap-1", "snap-2"):
        snapshot = SourceSnapshot(
            source_id=source.id,
            snapshot_time=utcnow(),
            storage_uri=f"memory://{label}",
            content_length=2,
            checksum=(label.encode().hex() * 32)[:64],
            license_policy="retain",
            redaction_status="none",
        )
        session.add(snapshot)
        session.flush()
        snapshots[label] = snapshot.id
    benchmark = Benchmark(slug=f"test-bench-{suffix}", name="Test Benchmark")
    session.add(benchmark)
    session.flush()
    version = BenchmarkVersion(benchmark_id=benchmark.id, version="v1")
    session.add(version)
    session.flush()
    metric = BenchmarkMetric(
        benchmark_version_id=version.id, slug="pass_rate", name="Pass Rate",
        unit="percent", score_direction="higher_better",
    )
    session.add(metric)
    session.flush()
    run = EvaluationRun(run_type="external", engine="external_aggregate",
                        source_id=source.id, status="success")
    session.add(run)
    session.flush()
    session.commit()
    yield {
        "variant": variant, "source": source, "benchmark": benchmark,
        "version": version, "metric": metric, "run": run, "snapshots": snapshots,
    }


def _payload(ctx, score, sample=500, snapshot="snap-1"):
    return dict(
        run_id=ctx["run"].id,
        model_variant_id=ctx["variant"].id,
        model_endpoint_id=None,
        benchmark_id=ctx["benchmark"].id,
        benchmark_version_id=ctx["version"].id,
        benchmark_metric_id=ctx["metric"].id,
        score=Decimal(score),
        evaluation_date=utcnow(),
        source_id=ctx["source"].id,
        source_snapshot_id=ctx["snapshots"][snapshot],
        evaluator="TestEvaluator",
        evaluation_type="external",
        sample_size=sample,
        reasoning_setting="high",
    )


class TestUpsertEvaluation:
    def test_first_insert_creates_row(self, session, ctx):
        result = upsert_evaluation(session, **_payload(ctx, "72.3"))
        assert result.action == "created"
        assert result.evaluation_id is not None

    def test_pure_replay_is_skipped(self, session, ctx):
        a = upsert_evaluation(session, **_payload(ctx, "72.3"))
        b = upsert_evaluation(session, **_payload(ctx, "72.3"))
        assert a.evaluation_id == b.evaluation_id
        assert b.action == "skipped"

    def test_reconfirmation_in_new_snapshot_is_skipped(self, session, ctx):
        a = upsert_evaluation(session, **_payload(ctx, "72.3", snapshot="snap-1"))
        b = upsert_evaluation(session, **_payload(ctx, "72.30", snapshot="snap-2"))
        assert a.evaluation_id == b.evaluation_id
        assert b.action == "reconfirmed"

    def test_changed_score_creates_new_observation_with_supersedes(self, session, ctx):
        a = upsert_evaluation(session, **_payload(ctx, "72.3"))
        b = upsert_evaluation(session, **_payload(ctx, "73.1"))
        assert b.action == "superseded"
        assert b.evaluation_id != a.evaluation_id
        new = session.get(Evaluation, b.evaluation_id)
        assert new.supersedes_evaluation_id == a.evaluation_id

    def test_changed_sample_size_creates_new_observation(self, session, ctx):
        a = upsert_evaluation(session, **_payload(ctx, "72.3", sample=500))
        b = upsert_evaluation(session, **_payload(ctx, "72.3", sample=1000))
        assert b.action == "superseded"
        assert b.evaluation_id != a.evaluation_id

    def test_supersedes_chain_resolves_to_latest(self, session, ctx):
        a = upsert_evaluation(session, **_payload(ctx, "72.3"))
        b = upsert_evaluation(session, **_payload(ctx, "73.1"))
        c = upsert_evaluation(session, **_payload(ctx, "74.0"))
        # latest for this identity must be c, chain length 3, nothing overwritten
        ids = session.scalars(
            select(Evaluation.id).where(
                Evaluation.evaluation_identity_hash == a.identity_hash
            )
        ).all()
        assert set(ids) == {a.evaluation_id, b.evaluation_id, c.evaluation_id}
