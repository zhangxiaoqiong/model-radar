"""Public read endpoints: health, status, models, benchmarks, evaluations, compare.

Query policy: the DB is remote, so every response is built from a bounded
number of batched queries (no per-row lookups). N+1 patterns are banned here.
"""

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
    EntityResolutionQueue,
    Evaluation,
    ModelEndpoint,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    PipelineRun,
    Provider,
    Source,
    SourceSnapshot,
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


def _superseded_ids():
    return select(Evaluation.supersedes_evaluation_id).where(
        Evaluation.supersedes_evaluation_id.is_not(None)
    )


@router.get("/health")
def health(session: Session = Depends(get_db_session)):
    db_ok = session.scalar(select(1)) == 1
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "error"}


@router.get("/api/v1/status")
def status(session: Session = Depends(get_db_session)):
    """Freshness snapshot for the UI header: latest source snapshot, latest
    pipeline run, current evaluation count, pending resolution work."""
    latest_snapshot_time = session.scalar(
        select(func.max(SourceSnapshot.snapshot_time))
    )
    latest_run = session.scalar(
        select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(1)
    )
    return {
        "latest_snapshot_time": latest_snapshot_time,
        "latest_pipeline": (
            {
                "id": latest_run.id,
                "type": latest_run.pipeline_type,
                "status": latest_run.status,
                "finished_at": latest_run.finished_at,
            }
            if latest_run
            else None
        ),
        "evaluation_count": session.scalar(
            select(func.count()).select_from(Evaluation)
        ),
        "current_evaluation_count": session.scalar(
            select(func.count())
            .select_from(Evaluation)
            .where(Evaluation.id.not_in(_superseded_ids()))
        ),
        "pending_resolution_count": session.scalar(
            select(func.count())
            .select_from(EntityResolutionQueue)
            .where(EntityResolutionQueue.status == "pending")
        ),
    }


@router.get("/api/v1/models")
def list_models(
    session: Session = Depends(get_db_session),
    provider: str | None = Query(default=None, description="provider slug"),
    q: str | None = Query(default=None, description="name/slug search"),
    status: str = Query(default="active"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    include_summary: bool = Query(default=False),
):
    # 1 query: releases + provider/family slugs, cursor-paginated
    stmt = (
        select(
            ModelRelease,
            Provider.slug.label("provider_slug"),
            Provider.name.label("provider_name"),
            ModelFamily.slug.label("family_slug"),
        )
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
    stmt = stmt.order_by(ModelRelease.id.desc()).limit(limit + 1)
    if cursor:
        stmt = stmt.where(ModelRelease.id < cursor)

    rows = session.execute(stmt).all()
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1][0].id
    items = [
        {**row_dict(release, RELEASE_COLUMNS),
         "provider": provider_slug, "provider_name": provider_name, "family": family_slug}
        for release, provider_slug, provider_name, family_slug in rows
    ]
    result = {"items": items, "next_cursor": next_cursor}
    if not include_summary or not rows:
        return result

    # summary: 3 more queries total (variants, endpoints, current evaluations)
    variant_ids = [release.default_variant_id for release, _, _, _ in rows
                   if release.default_variant_id]
    variants_by_id = {
        v.id: v
        for v in session.scalars(
            select(ModelVariant).where(ModelVariant.id.in_(variant_ids))
        )
    } if variant_ids else {}

    first_endpoint_by_variant: dict[str, ModelEndpoint] = {}
    if variant_ids:
        for endpoint in session.scalars(
            select(ModelEndpoint)
            .where(ModelEndpoint.model_variant_id.in_(variant_ids))
            .order_by(
                ModelEndpoint.model_variant_id,
                ModelEndpoint.endpoint_type,
                ModelEndpoint.external_model_id,
            )
        ):
            first_endpoint_by_variant.setdefault(endpoint.model_variant_id, endpoint)

    evaluations_by_variant: dict[str, list[dict]] = {}
    if variant_ids:
        eval_rows = session.execute(
            select(Evaluation, Benchmark.slug, Benchmark.name, Source.name)
            .join(Benchmark, Evaluation.benchmark_id == Benchmark.id)
            .join(Source, Evaluation.source_id == Source.id)
            .where(
                Evaluation.model_variant_id.in_(variant_ids),
                Evaluation.id.not_in(_superseded_ids()),
            )
            .order_by(Evaluation.created_at.desc())
        ).all()
        for evaluation, benchmark_slug, benchmark_name, source_name in eval_rows:
            evaluations_by_variant.setdefault(evaluation.model_variant_id, []).append({
                "benchmark_slug": benchmark_slug,
                "benchmark_name": benchmark_name,
                "score": str(evaluation.score),
                "source": source_name,
                "source_snapshot_id": evaluation.source_snapshot_id,
                "observed_at": row_dict(evaluation, ["created_at"])["created_at"],
            })

    for item in result["items"]:
        variant = variants_by_id.get(item.get("default_variant_id"))
        endpoint = first_endpoint_by_variant.get(variant.id) if variant else None
        item["variant"] = row_dict(variant, VARIANT_COLUMNS) if variant else None
        item["endpoint"] = row_dict(endpoint, ENDPOINT_COLUMNS) if endpoint else None
        item["evaluations"] = (
            evaluations_by_variant.get(variant.id, []) if variant else []
        )
    return result


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

    # one joined query for endpoints + their provider slugs
    variant_ids = [v.id for v in variants]
    ep_rows = (
        session.execute(
            select(ModelEndpoint, Provider.slug)
            .join(Provider, ModelEndpoint.provider_id == Provider.id)
            .where(ModelEndpoint.model_variant_id.in_(variant_ids))
            .order_by(ModelEndpoint.external_model_id)
        ).all()
        if variant_ids
        else []
    )
    ep_dicts = [
        {**row_dict(endpoint, ENDPOINT_COLUMNS), "provider": provider_slug}
        for endpoint, provider_slug in ep_rows
    ]

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

    # one joined query: evaluations + benchmark slug + version label
    stmt = (
        select(Evaluation, Benchmark.slug, BenchmarkVersion.version)
        .join(Benchmark, Evaluation.benchmark_id == Benchmark.id)
        .outerjoin(
            BenchmarkVersion, Evaluation.benchmark_version_id == BenchmarkVersion.id
        )
        .where(Evaluation.model_variant_id.in_(variant_ids))
    )
    if not include_history:
        stmt = stmt.where(Evaluation.id.not_in(_superseded_ids()))
    if benchmark:
        stmt = stmt.where(Benchmark.slug == benchmark)

    stmt = stmt.order_by(Evaluation.id.desc()).limit(limit + 1)
    if cursor:
        stmt = stmt.where(Evaluation.id < cursor)
    eval_rows = session.execute(stmt).all()

    superseded_set = set(session.scalars(_superseded_ids()).all())

    next_cursor = None
    if len(eval_rows) > limit:
        eval_rows = eval_rows[:limit]
        next_cursor = eval_rows[-1][0].id

    items = []
    for evaluation, benchmark_slug, version_label in eval_rows:
        d = row_dict(evaluation, EVAL_COLUMNS)
        d["benchmark_slug"] = benchmark_slug
        d["benchmark_version"] = version_label
        d["is_current"] = evaluation.id not in superseded_set
        items.append(d)
    return {"items": items, "next_cursor": next_cursor}


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

    # one aggregate query for the page's version counts
    page_ids = [b.id for b in result["items"]]
    counts = dict(
        session.execute(
            select(BenchmarkVersion.benchmark_id, func.count())
            .where(BenchmarkVersion.benchmark_id.in_(page_ids))
            .group_by(BenchmarkVersion.benchmark_id)
        ).all()
    ) if page_ids else {}
    items = [
        {**row_dict(b, ["id", "slug", "name", "category", "dynamic",
                        "dataset_public", "contamination_risk"]),
         "version_count": counts.get(b.id, 0)}
        for b in result["items"]
    ]
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
    version_ids = [v.id for v in versions]
    metrics_by_version: dict[str, list[BenchmarkMetric]] = {}
    if version_ids:
        for metric in session.scalars(
            select(BenchmarkMetric)
            .where(BenchmarkMetric.benchmark_version_id.in_(version_ids))
        ):
            metrics_by_version.setdefault(metric.benchmark_version_id, []).append(metric)
    version_dicts = [
        {
            "id": v.id,
            "version": v.version,
            "metrics": [
                row_dict(m, ["id", "slug", "name", "dataset_split", "unit",
                             "score_direction", "normalization_method"])
                for m in metrics_by_version.get(v.id, [])
            ],
        }
        for v in versions
    ]

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

    # Parse first, then validate with batched lookups. Comparison is limited to
    # five items, but it still should not add roundtrips per selected model.
    requested: list[tuple[str, str, str | None]] = []
    for token in tokens:
        variant_id, separator, endpoint_id = token.partition("@")
        endpoint_id = endpoint_id if separator else None  # bare token -> no endpoint filter
        requested.append((token, variant_id, endpoint_id))

    variant_ids = [variant_id for _, variant_id, _ in requested]
    endpoint_ids = [endpoint_id for _, _, endpoint_id in requested if endpoint_id]

    release_rows = session.execute(
        select(ModelVariant, ModelRelease, ModelFamily, Provider)
        .join(ModelRelease, ModelVariant.model_release_id == ModelRelease.id)
        .join(ModelFamily, ModelRelease.family_id == ModelFamily.id)
        .join(Provider, ModelFamily.provider_id == Provider.id)
        .where(ModelVariant.id.in_(variant_ids))
    ).all()
    context_by_variant = {v.id: (v, r, f, p) for v, r, f, p in release_rows}
    endpoints = (
        session.scalars(select(ModelEndpoint).where(ModelEndpoint.id.in_(endpoint_ids))).all()
        if endpoint_ids else []
    )
    endpoint_by_id = {endpoint.id: endpoint for endpoint in endpoints}

    for _, variant_id, endpoint_id in requested:
        if variant_id not in context_by_variant:
            raise HTTPException(status_code=404, detail=f"variant '{variant_id}' not found")
        endpoint = endpoint_by_id.get(endpoint_id) if endpoint_id else None
        if endpoint_id and endpoint is None:
            raise HTTPException(status_code=404, detail=f"endpoint '{endpoint_id}' not found")
        if endpoint is not None and endpoint.model_variant_id != variant_id:
            raise HTTPException(status_code=422, detail="endpoint does not belong to variant")

    evaluations_by_variant: dict[str, list[dict]] = {}
    eval_rows = session.execute(
        select(Evaluation, Benchmark.slug, BenchmarkVersion.version)
        .join(Benchmark, Evaluation.benchmark_id == Benchmark.id)
        .outerjoin(BenchmarkVersion, Evaluation.benchmark_version_id == BenchmarkVersion.id)
        .where(
            Evaluation.model_variant_id.in_(variant_ids),
            Evaluation.id.not_in(_superseded_ids()),
        )
        .order_by(Evaluation.created_at.desc())
    ).all()
    for evaluation, benchmark_slug, version_label in eval_rows:
        d = row_dict(evaluation, ["id", "model_endpoint_id", "benchmark_id", "benchmark_version_id",
                                  "benchmark_metric_id", "score", "source_id",
                                  "source_snapshot_id", "confidence", "evaluation_date"])
        d["benchmark_slug"] = benchmark_slug
        d["benchmark_version"] = version_label
        evaluations_by_variant.setdefault(evaluation.model_variant_id, []).append(d)

    result = []
    for token, variant_id, endpoint_id in requested:
        variant, release, family, provider = context_by_variant[variant_id]
        variant_evaluations = list(evaluations_by_variant.get(variant_id, []))
        if endpoint_id is not None:
            variant_evaluations = [
                e for e in variant_evaluations if e["model_endpoint_id"] == endpoint_id
            ]
        result.append({
            "item": token,
            "provider": provider.slug,
            "family": family.slug,
            "release": row_dict(release, RELEASE_COLUMNS),
            "variant": row_dict(variant, VARIANT_COLUMNS),
            "endpoint": (
                row_dict(endpoint_by_id[endpoint_id], ENDPOINT_COLUMNS)
                if endpoint_id else None
            ),
            "evaluations": variant_evaluations,
        })
    return {"items": result}
