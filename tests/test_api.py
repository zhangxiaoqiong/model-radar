"""API integration tests: FastAPI app + real MySQL (model_radar_test).

Run: DB_NAME=model_radar_test python -m pytest tests/test_api.py
Schema is created via Base.metadata.create_all (alembic is for prod migration history).
"""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault("DB_NAME", "model_radar_test")
os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402

from backend_core.config import get_settings  # noqa: E402
from backend_core.db import Base, make_session_factory  # noqa: E402
from backend_core.domain import (  # noqa: E402
    AdminAuditLog,
    Benchmark,
    BenchmarkMetric,
    BenchmarkVersion,
    EntityResolutionQueue,
    ModelAlias,
    ModelEndpoint,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    Provider,
    Source,
)
from backend_core.services import upsert_evaluation  # noqa: E402


ADMIN_TOKEN = "test-admin-token"


@pytest.fixture(scope="module")
def engine():
    get_settings.cache_clear()
    url = get_settings().database_url
    eng = create_engine(url, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    factory = make_session_factory(engine)
    s = factory()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(scope="module")
def seeded(engine):
    """Seed one full model chain + one benchmark + one evaluation."""
    factory = make_session_factory(engine)
    s = factory()
    provider = Provider(slug="openai", name="OpenAI", provider_type="vendor")
    source = Source(slug="artificial_analysis", name="Artificial Analysis",
                     source_type="independent_eval", reliability_level="high",
                     api_available=True)
    s.add_all([provider, source])
    s.flush()
    family = ModelFamily(provider_id=provider.id, slug="gpt", name="GPT")
    s.add(family)
    s.flush()
    release = ModelRelease(family_id=family.id, canonical_name="GPT-5.2",
                           slug="gpt-5.2")
    s.add(release)
    s.flush()
    variant = ModelVariant(model_release_id=release.id, name="standard",
                           variant_type="standard", reasoning_level="medium")
    s.add(variant)
    s.flush()
    release.default_variant_id = variant.id
    endpoint = ModelEndpoint(model_variant_id=variant.id, provider_id=provider.id,
                             external_model_id="gpt-5.2", endpoint_type="official_api")
    s.add(endpoint)
    bench = Benchmark(slug="swe-bench-verified", name="SWE-bench Verified",
                      category="coding", source_id=source.id)
    s.add(bench)
    s.flush()
    version = BenchmarkVersion(benchmark_id=bench.id, version="verified")
    s.add(version)
    s.flush()
    metric = BenchmarkMetric(benchmark_version_id=version.id, slug="resolved",
                             name="Resolved %", dataset_split="", unit="percent",
                             score_direction="higher_better",
                             normalization_method="minmax")
    s.add(metric)
    s.commit()
    yield {
        "provider_id": provider.id, "source_id": source.id,
        "release_id": release.id, "release_slug": release.slug,
        "variant_id": variant.id, "endpoint_id": endpoint.id,
        "benchmark_id": bench.id, "benchmark_slug": bench.slug,
        "version_id": version.id, "metric_id": metric.id,
    }
    s.close()


@pytest.fixture()
def client(engine):
    from api.deps import get_db_session
    from api.main import create_app

    app = create_app()
    factory = make_session_factory(engine)

    def override():
        s = factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = override
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Public endpoints

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_models_list_returns_seeded_model(client, seeded):
    r = client.get("/api/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["slug"] == "gpt-5.2"
    assert body["items"][0]["canonical_name"] == "GPT-5.2"
    assert "items" in body and "next_cursor" in body


def test_models_list_filters_by_provider(client, seeded):
    r = client.get("/api/v1/models", params={"provider": "anthropic"})
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_models_list_summary_includes_variant_and_endpoint(client, seeded):
    r = client.get("/api/v1/models", params={"include_summary": True})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["variant"]["id"] == seeded["variant_id"]
    assert item["endpoint"]["id"] == seeded["endpoint_id"]
    assert item["evaluations"] == []


def test_models_detail_with_variants_and_endpoints(client, seeded):
    r = client.get(f"/api/v1/models/{seeded['release_slug']}")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "gpt-5.2"
    assert len(body["variants"]) == 1
    assert body["variants"][0]["name"] == "standard"
    assert len(body["endpoints"]) == 1
    assert body["endpoints"][0]["external_model_id"] == "gpt-5.2"


def test_models_detail_404_problem_json(client, seeded):
    r = client.get("/api/v1/models/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["title"] == "Not Found"


def test_benchmarks_list(client, seeded):
    r = client.get("/api/v1/benchmarks")
    assert r.status_code == 200
    assert r.json()["items"][0]["slug"] == "swe-bench-verified"


def test_model_evaluations_empty_then_one(client, seeded, session):
    r = client.get(f"/api/v1/models/{seeded['release_slug']}/evaluations")
    assert r.status_code == 200
    assert r.json()["items"] == []

    from backend_core.services import upsert_evaluation
    from backend_core.db import new_uuid
    from backend_core.domain import EvaluationRun
    run = EvaluationRun(id=new_uuid(), run_type="external", source_id=seeded["source_id"],
                        status="success")
    session.add(run)
    session.flush()
    result = upsert_evaluation(
        session, run_id=run.id, model_variant_id=seeded["variant_id"],
        model_endpoint_id=None,
        benchmark_id=seeded["benchmark_id"], benchmark_version_id=seeded["version_id"],
        benchmark_metric_id=seeded["metric_id"], score="48.2",
        evaluation_date=None,
        source_id=seeded["source_id"], source_snapshot_id=None,
        evaluator="Artificial Analysis", sample_size=500,
        evaluation_type="external",
    )
    assert result.action == "created"
    session.commit()

    r = client.get(f"/api/v1/models/{seeded['release_slug']}/evaluations")
    body = r.json()
    assert r.status_code == 200
    assert len(body["items"]) == 1
    assert str(body["items"][0]["score"]) == "48.2"
    assert body["items"][0]["benchmark_slug"] == "swe-bench-verified"
    assert body["items"][0]["source_id"] == seeded["source_id"]
    assert body["items"][0]["is_current"] is True

    replacement = upsert_evaluation(
        session, run_id=run.id, model_variant_id=seeded["variant_id"],
        model_endpoint_id=None,
        benchmark_id=seeded["benchmark_id"], benchmark_version_id=seeded["version_id"],
        benchmark_metric_id=seeded["metric_id"], score="49.1",
        evaluation_date=None,
        source_id=seeded["source_id"], source_snapshot_id=None,
        evaluator="Artificial Analysis", sample_size=500,
        evaluation_type="external",
    )
    assert replacement.action == "superseded"
    session.commit()

    current = client.get(f"/api/v1/models/{seeded['release_slug']}/evaluations")
    assert [item["score"] for item in current.json()["items"]] == ["49.1"]
    history = client.get(
        f"/api/v1/models/{seeded['release_slug']}/evaluations",
        params={"include_history": True},
    )
    assert len(history.json()["items"]) == 2
    assert {item["is_current"] for item in history.json()["items"]} == {True, False}

    comparison = client.get(
        "/api/v1/compare/models",
        params={
            "items": (
                f"{seeded['variant_id']},"
                f"{seeded['variant_id']}@{seeded['endpoint_id']}"
            )
        },
    )
    assert comparison.status_code == 200
    compared = comparison.json()["items"]
    assert len(compared[0]["evaluations"]) == 1
    assert compared[1]["endpoint"]["id"] == seeded["endpoint_id"]
    assert compared[1]["evaluations"] == []


# ---------------------------------------------------------------------------
# Admin auth

def test_admin_requires_token(client, seeded):
    r = client.get("/api/v1/admin/resolution-queue")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")


def test_admin_rejects_wrong_token(client, seeded):
    r = client.get("/api/v1/admin/resolution-queue", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 401


def test_admin_accepts_correct_token(client, seeded):
    r = client.get("/api/v1/admin/resolution-queue",
                   headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Resolution queue actions

def _make_queue_item(session, seeded, **kw):
    external_id = f"openai/gpt-5.2-x-{uuid.uuid4().hex[:8]}"
    item = EntityResolutionQueue(
        source_id=seeded["source_id"], record_type="model_variant",
        external_id=external_id, external_name=external_id,
        raw_payload={"name": external_id},
        status="pending",
        **kw,
    )
    session.add(item)
    session.commit()
    return item.id


def test_resolution_queue_approve_maps_alias_and_audits(client, seeded, session):
    item_id = _make_queue_item(session, seeded,
                               suggested_variant_id=seeded["variant_id"],
                               match_confidence=0.9)
    r = client.post(f"/api/v1/admin/resolution-queue/{item_id}/approve",
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                    json={"expected_version": 1})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    item = session.get(EntityResolutionQueue, item_id)
    assert item.status == "approved"
    assert item.resolved_at is not None
    item = session.get(EntityResolutionQueue, item_id)
    alias = session.scalar(select(ModelAlias).where(ModelAlias.external_id == item.external_id))
    assert alias is not None
    assert alias.model_variant_id == seeded["variant_id"]

    audit = session.scalar(select(AdminAuditLog).where(AdminAuditLog.target_id == item_id))
    assert audit is not None
    assert audit.action == "resolution_queue.approve"


def test_resolution_queue_approve_without_suggestion_fails(client, seeded, session):
    item_id = _make_queue_item(session, seeded)
    r = client.post(f"/api/v1/admin/resolution-queue/{item_id}/approve",
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                    json={"expected_version": 1})
    assert r.status_code == 422
    # item unchanged
    session.rollback()
    item = session.get(EntityResolutionQueue, item_id)
    assert item.status == "pending"


def test_resolution_queue_reject(client, seeded, session):
    item_id = _make_queue_item(session, seeded)
    r = client.post(f"/api/v1/admin/resolution-queue/{item_id}/reject",
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                    json={"note": "not a real model", "expected_version": 1})
    assert r.status_code == 200
    session.rollback()
    item = session.get(EntityResolutionQueue, item_id)
    assert item.status == "rejected"
    assert item.resolution_note == "not a real model"


def test_resolution_queue_create_model(client, seeded, session):
    item_id = _make_queue_item(session, seeded)
    r = client.post(f"/api/v1/admin/resolution-queue/{item_id}/create-model",
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                    json={
                        "provider_slug": "openai",
                        "family_slug": "gpt",
                        "canonical_name": "GPT-5.2X",
                        "release_slug": "gpt-5.2x",
                        "variant_name": "standard",
                        "expected_version": 1,
                    })
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "created"
    assert body["release"]["slug"] == "gpt-5.2x"

    session.rollback()
    release = session.scalar(select(ModelRelease).where(ModelRelease.slug == "gpt-5.2x"))
    assert release is not None
    assert release.default_variant_id is not None
    item = session.get(EntityResolutionQueue, item_id)
    assert item.status == "created"
    # created release must be linked back from the queue item
    assert item.suggested_release_id == release.id


def test_resolution_queue_conflict_version(client, seeded, session):
    """Optimistic-lock: stale version must not overwrite."""
    item_id = _make_queue_item(session, seeded)
    # tamper the version directly (simulating a concurrent edit)
    session.get(EntityResolutionQueue, item_id).version = 5
    session.commit()
    r = client.post(f"/api/v1/admin/resolution-queue/{item_id}/reject",
                    headers={"X-Admin-Token": ADMIN_TOKEN}, json={"expected_version": 1})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Cross-cutting: request id

def test_request_id_echoed_and_generated(client):
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    r2 = client.get("/health")
    assert r2.headers["x-request-id"]
    try:
        uuid.UUID(r2.headers["x-request-id"])
    except ValueError:
        pytest.fail("x-request-id is not a UUID")
