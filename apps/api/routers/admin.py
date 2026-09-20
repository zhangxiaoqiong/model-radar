"""Admin endpoints: resolution queue review, pipeline status, sync trigger.

V1a: single-token auth (deps.require_admin); every mutation writes AdminAuditLog.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_core.db import new_uuid, utcnow
from backend_core.domain import (
    AdminAuditLog,
    EntityResolutionQueue,
    ModelAlias,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    PipelineRun,
    Provider,
)

from ..deps import get_db_session, require_admin, row_dict
from ..pagination import apply_cursor, page_result

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


def _audit(
    session: Session, request: Request, action: str, target_type: str,
    target_id: str | None, before: dict | None, after: dict | None,
) -> None:
    session.add(AdminAuditLog(
        actor_id="admin", action=action, target_type=target_type, target_id=target_id,
        before_value=before, after_value=after,
        request_id=getattr(request.state, "request_id", None),
    ))


def _load_item(session: Session, item_id: str) -> EntityResolutionQueue:
    item = session.scalar(
        select(EntityResolutionQueue)
        .where(EntityResolutionQueue.id == item_id)
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"resolution item '{item_id}' not found")
    return item


def _check_version(item: EntityResolutionQueue, expected_version: int | None) -> None:
    """Optimistic lock: version only advances when resolved (pending edits in V1a
    are append-only via re-enqueue). A mismatch means concurrent modification."""
    if expected_version is not None and item.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"version conflict: expected {expected_version}, current {item.version}",
        )


class VersionBody(BaseModel):
    expected_version: int = Field(ge=1)


class RejectBody(VersionBody):
    note: str | None = None


class CreateModelBody(VersionBody):
    provider_slug: str
    family_slug: str = Field(max_length=64)
    canonical_name: str = Field(max_length=128)
    release_slug: str = Field(max_length=64)
    variant_name: str = Field(default="standard", max_length=128)
    variant_type: str = Field(default="standard")


@router.get("/resolution-queue")
def list_resolution_queue(
    session: Session = Depends(get_db_session),
    status: str = Query(default="pending"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    stmt = apply_cursor(
        select(EntityResolutionQueue).where(EntityResolutionQueue.status == status),
        EntityResolutionQueue.id, cursor, limit,
    )
    rows = session.scalars(stmt).all()
    result = page_result(list(rows), limit)
    cols = ["id", "source_id", "record_type", "external_id", "external_name",
            "suggested_variant_id", "suggested_release_id", "match_confidence",
            "status", "version", "created_at"]
    return {"items": [row_dict(i, cols) for i in result["items"]],
            "next_cursor": result["next_cursor"]}


@router.post("/resolution-queue/{item_id}/approve")
def approve_resolution(
    item_id: str,
    body: VersionBody,
    session: Session = Depends(get_db_session),
    request: Request = None,
    _admin: str = Depends(require_admin),
):
    """Approve the suggested mapping: binds the external name to the variant
    via ModelAlias so future syncs resolve automatically."""
    item = _load_item(session, item_id)
    _check_version(item, body.expected_version)
    if item.status != "pending":
        raise HTTPException(status_code=422, detail=f"item already {item.status}")
    if not item.suggested_variant_id:
        raise HTTPException(
            status_code=422,
            detail="no suggested_variant_id — use /map or /create-model instead",
        )

    before = row_dict(item, ["status", "version"])
    variant_id = item.suggested_variant_id

    alias = session.scalar(
        select(ModelAlias).where(
            ModelAlias.source_id == item.source_id,
            ModelAlias.alias == (item.external_name or item.external_id),
        )
    )
    if alias is None:
        session.add(ModelAlias(
            model_variant_id=variant_id,
            source_id=item.source_id,
            alias=item.external_name or item.external_id,
            external_id=item.external_id,
        ))
    elif alias.model_variant_id != variant_id:
        raise HTTPException(
            status_code=409,
            detail="alias already maps to a different model variant",
        )

    item.status = "approved"
    item.version += 1
    item.resolved_by = "admin"
    item.resolved_at = utcnow()
    session.flush()
    _audit(session, request, "resolution_queue.approve", "entity_resolution_queue",
           item.id, before, row_dict(item, ["status", "version", "suggested_variant_id"]))
    return row_dict(item, ["id", "status", "version", "suggested_variant_id"])


@router.post("/resolution-queue/{item_id}/reject")
def reject_resolution(
    item_id: str,
    body: RejectBody,
    session: Session = Depends(get_db_session),
    request: Request = None,
    _admin: str = Depends(require_admin),
):
    item = _load_item(session, item_id)
    if item.status != "pending":
        raise HTTPException(status_code=422, detail=f"item already {item.status}")
    _check_version(item, body.expected_version)

    before = row_dict(item, ["status", "version"])
    item.status = "rejected"
    item.version += 1
    item.resolution_note = body.note
    item.resolved_by = "admin"
    item.resolved_at = utcnow()
    session.flush()
    _audit(session, request, "resolution_queue.reject", "entity_resolution_queue",
           item.id, before, row_dict(item, ["status", "version"]))
    return row_dict(item, ["id", "status", "version"])


@router.post("/resolution-queue/{item_id}/map")
def map_resolution(
    item_id: str,
    body: RejectBody,
    session: Session = Depends(get_db_session),
    variant_id: str = Query(description="target model_variant id"),
    request: Request = None,
    _admin: str = Depends(require_admin),
):
    """Map the queue item to an explicit variant, then approve."""
    item = _load_item(session, item_id)
    if item.status != "pending":
        raise HTTPException(status_code=422, detail=f"item already {item.status}")
    variant = session.get(ModelVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail=f"variant '{variant_id}' not found")
    _check_version(item, body.expected_version)

    before = row_dict(item, ["status", "version"])
    item.suggested_variant_id = variant_id
    item.status = "mapped"
    item.version += 1
    item.resolution_note = body.note
    item.resolved_by = "admin"
    item.resolved_at = utcnow()
    alias_value = item.external_name or item.external_id
    alias = session.scalar(
        select(ModelAlias).where(
            ModelAlias.source_id == item.source_id,
            ModelAlias.alias == alias_value,
        )
    )
    if alias is not None and alias.model_variant_id != variant_id:
        raise HTTPException(status_code=409, detail="alias already maps to another variant")
    if alias is None:
        session.add(ModelAlias(
            model_variant_id=variant_id,
            source_id=item.source_id,
            alias=alias_value,
            external_id=item.external_id,
        ))
    session.flush()
    _audit(session, request, "resolution_queue.map", "entity_resolution_queue",
           item.id, before, row_dict(item, ["status", "version", "suggested_variant_id"]))
    return row_dict(item, ["id", "status", "version", "suggested_variant_id"])


@router.post("/resolution-queue/{item_id}/create-model", status_code=201)
def create_model_from_resolution(
    item_id: str,
    body: CreateModelBody,
    session: Session = Depends(get_db_session),
    request: Request = None,
    _admin: str = Depends(require_admin),
):
    """Manual model creation from an unmatched external record (spec §10.3) —
    external syncs never auto-create; this is the only creation path."""
    item = _load_item(session, item_id)
    if item.status != "pending":
        raise HTTPException(status_code=422, detail=f"item already {item.status}")
    _check_version(item, body.expected_version)

    provider = session.scalar(select(Provider).where(Provider.slug == body.provider_slug))
    if provider is None:
        raise HTTPException(status_code=422, detail=f"provider '{body.provider_slug}' not found")
    if session.scalar(select(ModelRelease).where(ModelRelease.slug == body.release_slug)):
        raise HTTPException(status_code=409, detail=f"release '{body.release_slug}' exists")

    family = session.scalar(
        select(ModelFamily).where(
            ModelFamily.provider_id == provider.id, ModelFamily.slug == body.family_slug
        )
    )
    if family is None:
        family = ModelFamily(provider_id=provider.id, slug=body.family_slug,
                             name=body.family_slug.replace("-", " ").title())
        session.add(family)
        session.flush()

    release = ModelRelease(family_id=family.id, canonical_name=body.canonical_name,
                           slug=body.release_slug, source_id=item.source_id)
    session.add(release)
    session.flush()
    variant = ModelVariant(model_release_id=release.id, name=body.variant_name,
                           variant_type=body.variant_type, source_id=item.source_id)
    session.add(variant)
    session.flush()
    release.default_variant_id = variant.id

    # bind the external name so future syncs resolve to the new model
    session.add(ModelAlias(
        model_variant_id=variant.id,
        source_id=item.source_id,
        alias=item.external_name or item.external_id,
        external_id=item.external_id,
    ))

    before = row_dict(item, ["status", "version"])
    item.status = "created"
    item.version += 1
    item.suggested_release_id = release.id
    item.suggested_variant_id = variant.id
    item.resolved_by = "admin"
    item.resolved_at = utcnow()
    session.flush()
    _audit(session, request, "resolution_queue.create_model", "entity_resolution_queue",
           item.id, before,
           {"status": item.status, "release_id": release.id, "variant_id": variant.id})
    return {
        "status": item.status,
        "version": item.version,
        "release": row_dict(release, ["id", "slug", "canonical_name", "default_variant_id"]),
        "variant_id": variant.id,
    }


@router.get("/pipelines")
def list_pipelines(
    session: Session = Depends(get_db_session),
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    stmt = select(PipelineRun)
    if status:
        stmt = stmt.where(PipelineRun.status == status)
    stmt = apply_cursor(stmt, PipelineRun.id, cursor, limit)
    rows = session.scalars(stmt).all()
    result = page_result(list(rows), limit)
    cols = ["id", "pipeline_type", "trigger", "status", "started_at", "finished_at",
            "error_message", "attempt", "created_at"]
    return {"items": [row_dict(r, cols) for r in result["items"]],
            "next_cursor": result["next_cursor"]}


@router.post("/sync", status_code=202)
def trigger_sync(
    session: Session = Depends(get_db_session),
    request: Request = None,
    _admin: str = Depends(require_admin),
):
    """Enqueue a manual sync pipeline run. The scheduler/worker picks it up
    (pipeline execution is a background process, never in-request)."""
    run = PipelineRun(
        id=new_uuid(),
        pipeline_type="manual",
        trigger="manual",
        status="pending",
    )
    session.add(run)
    session.flush()
    _audit(session, request, "pipeline.trigger_sync", "pipeline_run", run.id,
           None, {"pipeline_type": "manual"})
    return {"run_id": run.id, "status": "pending"}
