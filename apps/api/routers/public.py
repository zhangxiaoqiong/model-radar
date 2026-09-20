"""Public read endpoints: health, models, benchmarks, evaluations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend_core.domain import (
    Benchmark,
    BenchmarkCapabilityMap,
    BenchmarkMetric,
    BenchmarkVersion,
    Capability,
    Evaluation,
    ModelEndpoint,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    Provider,
)

from ..deps import get_db_session, row_dict
from ..pagination import apply_cursor, page_result

router = APIRouter()

RELEASE_COLUMNS = [
    "id", "slug", "canonical_name", "release_date", "knowledge_cutoff",
    "open_weight", "license", "status", "default_variant_id",
]
VARIANT_COLUMNS = [
    "id", "name", "variant_type", "reasoning_level", "context_window",
    "max_output_tokens", "supports_image", "supports_audio", "supports_video",
    "supports_reasoning", "supports_tool_calling", "supports_structured_output",
]
ENDPOINT_COLUMNS = [
    "id", "external_model_id", "endpoint_type", "api_base_url",
    "context_window", "max_output_tokens", "status",
]


@router.get("/health")
def health(session: Session = Depends(get_db_session)):
    db_ok = session.scalar(select(1)) == 1
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "error"}


@router.get("/api/v1/models")
def list_models(
    session: Session = Depends(get_db_session),
    provider: str | None = Query(default=None, description="provider slug"),
    q: str | None = Query(default=None, description="name/slug search"),
    status: str = Query(default="active"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    stmt = (
        select(ModelRelease)
        .join(ModelFamily, ModelRelease.family_id == ModelFamily.id)
        .join(Provider, ModelFamily.provider_id == Provider.id)
        .where(ModelRelease.status == status)
    )
    if provider:
        stmt = stmt.where(Provider.slug == provider)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            ModelRelease.canonical_name.like(like) | ModelRelease.slug.like(like)
        )
    stmt = apply_cursor(stmt, ModelRelease.id, cursor, limit)
    releases = session.scalars(stmt).unique().all()
    result = page_result(list(releases), limit)
    items = []
    for r in result["items"]:
        d = row_dict(r, RELEASE_COLUMNS)
        family = session.get(ModelFamily, r.family_id)
        prov = session.get(Provider, family.provider_id)
        d["provider"] = prov.slug
        d["family"] = family.slug
        items.append(d)
    return {"items": items, "next_cursor": result["next_cursor"]}


@router.get("/api/v1/models/{slug}")
def model_detail(slug: str, session: Session = Depends(get_db_session)):
    release = session.scalar(select(ModelRelease).where(ModelRelease.slug == slug))
    if release is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"model '{slug}' not found")

    family = session.get(ModelFamily, release.family_id)
    prov = session.get(Provider, family.provider_id)

    variants = session.scalars(
        select(ModelVariant)
        .where(ModelVariant.model_release_id == release.id)
        .order_by(ModelVariant.name)
    ).all()

    variant_ids = [v.id for v in variants]
    endpoints = (
        session.scalars(
            select(ModelEndpoint)
            .where(ModelEndpoint.model_variant_id.in_(variant_ids))
            .order_by(ModelEndpoint.external_model_id)
        ).all()
        if variant_ids
        else []
    )

    ep_dicts = []
    for e in endpoints:
        d = row_dict(e, ENDPOINT_COLUMNS)
        d["provider"] = session.get(Provider, e.provider_id).slug
        ep_dicts.append(d)

    return {
        **row_dict(release, RELEASE_COLUMNS),
        "provider": prov.slug,
        "family": family.slug,
        "variants": [row_dict(v, VARIANT_COLUMNS) for v in variants],
        "endpoints": ep_dicts,
    }


@router.get("/api/v1/models/{slug}/evaluations")
def model_evaluations(
    slug: str,
    session: Session = Depends(get_db_session),
    benchmark: str | None = Query(default=None, description="benchmark slug"),
    include_history: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    release = session.scalar(select(ModelRelease).where(ModelRelease.slug == slug))
    if release is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"model '{slug}' not found")

    variant_ids = session.scalars(
        select(ModelVariant.id).where(ModelVariant.model_release_id == release.id)
    ).all()

    stmt = select(Evaluation).where(Evaluation.model_variant_id.in_(variant_ids))
    superseded_ids = select(Evaluation.supersedes_evaluation_id).where(
        Evaluation.supersedes_evaluation_id.is_not(None)
    )
    if not include_history:
        stmt = stmt.where(Evaluation.id.not_in(superseded_ids))
    if benchmark:
        stmt = stmt.join(Benchmark, Evaluation.benchmark_id == Benchmark.id).where(
            Benchmark.slug == benchmark
        )
    stmt = apply_cursor(stmt, Evaluation.id, cursor, limit)
    evals = session.scalars(stmt).all()
    result = page_result(list(evals), limit)
    superseded_set = set(session.scalars(superseded_ids).all())

    EVAL_COLUMNS = [
        "id", "model_variant_id", "model_endpoint_id", "benchmark_id",
        "benchmark_version_id", "benchmark_metric_id", "source_id",
        "source_snapshot_id",
        "score", "evaluation_date", "evaluation_type", "sample_size",
        "confidence", "confidence_lower", "confidence_upper",
        "evaluation_identity_hash", "supersedes_evaluation_id",
        "last_confirmed_at", "last_confirmed_snapshot_id", "confirmation_count",
        "created_at",
    ]
    items = []
    for e in result["items"]:
        d = row_dict(e, EVAL_COLUMNS)
        bench = session.get(Benchmark, e.benchmark_id)
        d["benchmark_slug"] = bench.slug
        version_id = e.benchmark_version_id
        d["benchmark_version"] = (
            session.get(BenchmarkVersion, version_id).version if version_id else None
        )
        d["is_current"] = e.id not in superseded_set
        items.append(d)
    return {"items": items, "next_cursor": result["next_cursor"]}


@router.get("/api/v1/benchmarks")
def list_benchmarks(
    session: Session = Depends(get_db_session),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    stmt = apply_cursor(
        select(Benchmark).where(Benchmark.status == "active"), Benchmark.id, cursor, limit
    )
    rows = session.scalars(stmt).all()
    result = page_result(list(rows), limit)
    items = []
    for b in result["items"]:
        d = row_dict(b, ["id", "slug", "name", "category", "dynamic",
                         "dataset_public", "contamination_risk"])
        d["version_count"] = session.scalar(
            select(func.count()).where(BenchmarkVersion.benchmark_id == b.id)
        )
        items.append(d)
    return {"items": items, "next_cursor": result["next_cursor"]}


@router.get("/api/v1/benchmarks/{slug}")
def benchmark_detail(slug: str, session: Session = Depends(get_db_session)):
    bench = session.scalar(select(Benchmark).where(Benchmark.slug == slug))
    if bench is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"benchmark '{slug}' not found")

    versions = session.scalars(
        select(BenchmarkVersion).where(BenchmarkVersion.benchmark_id == bench.id)
    ).all()
    version_dicts = []
    for v in versions:
        metrics = session.scalars(
            select(BenchmarkMetric).where(BenchmarkMetric.benchmark_version_id == v.id)
        ).all()
        version_dicts.append({
            "id": v.id,
            "version": v.version,
            "metrics": [
                row_dict(m, ["id", "slug", "name", "dataset_split", "unit",
                             "score_direction", "normalization_method"])
                for m in metrics
            ],
        })

    cap_rows = session.execute(
        select(Capability, BenchmarkCapabilityMap.weight)
        .join(BenchmarkCapabilityMap, BenchmarkCapabilityMap.capability_id == Capability.id)
        .where(BenchmarkCapabilityMap.benchmark_id == bench.id)
    ).all()

    return {
        **row_dict(bench, ["id", "slug", "name", "category", "description",
                           "official_url", "dynamic", "dataset_public",
                           "contamination_risk"]),
        "versions": version_dicts,
        "capabilities": [
            {"slug": cap.slug, "name": cap.name, "weight": str(w)}
            for cap, w in cap_rows
        ],
    }


@router.get("/api/v1/compare/models")
def compare_models(
    items: str = Query(description="comma-separated variant_id[@endpoint_id] items"),
    session: Session = Depends(get_db_session),
):
    from fastapi import HTTPException

    tokens = [token.strip() for token in items.split(",") if token.strip()]
    if not 2 <= len(tokens) <= 5:
        raise HTTPException(status_code=422, detail="compare requires 2 to 5 items")

    superseded_ids = select(Evaluation.supersedes_evaluation_id).where(
        Evaluation.supersedes_evaluation_id.is_not(None)
    )
    result = []
    for token in tokens:
        variant_id, separator, endpoint_id = token.partition("@")
        variant = session.get(ModelVariant, variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail=f"variant '{variant_id}' not found")
        endpoint = session.get(ModelEndpoint, endpoint_id) if separator else None
        if separator and endpoint is None:
            raise HTTPException(status_code=404, detail=f"endpoint '{endpoint_id}' not found")
        if endpoint is not None and endpoint.model_variant_id != variant.id:
            raise HTTPException(status_code=422, detail="endpoint does not belong to variant")

        release = session.get(ModelRelease, variant.model_release_id)
        family = session.get(ModelFamily, release.family_id)
        provider = session.get(Provider, family.provider_id)
        evaluation_stmt = select(Evaluation).where(
            Evaluation.model_variant_id == variant.id,
            Evaluation.id.not_in(superseded_ids),
        )
        if endpoint is not None:
            evaluation_stmt = evaluation_stmt.where(
                Evaluation.model_endpoint_id == endpoint.id
            )
        evals = session.scalars(
            evaluation_stmt.order_by(Evaluation.created_at.desc())
        ).all()
        result.append(
            {
                "item": token,
                "provider": provider.slug,
                "family": family.slug,
                "release": row_dict(release, RELEASE_COLUMNS),
                "variant": row_dict(variant, VARIANT_COLUMNS),
                "endpoint": row_dict(endpoint, ENDPOINT_COLUMNS) if endpoint else None,
                "evaluations": [
                    row_dict(
                        evaluation,
                        [
                            "id", "benchmark_id", "benchmark_version_id",
                            "benchmark_metric_id", "score", "source_id",
                            "source_snapshot_id", "confidence", "evaluation_date",
                        ],
                    )
                    for evaluation in evals
                ],
            }
        )
    return {"items": result}
