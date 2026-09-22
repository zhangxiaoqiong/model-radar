"""Discover recent model releases from the Artificial Analysis model feed."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_core.db import new_uuid, utcnow
from backend_core.domain import ModelAlias, ModelFamily, ModelRelease, ModelVariant, Provider

from .snapshot_store import store_snapshot


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def recent_aa_models(models: list[dict], *, today: date | None = None, days: int = 90) -> list[dict]:
    cutoff = (today or date.today()) - timedelta(days=days)
    result = []
    for model in models:
        try:
            released = date.fromisoformat(str(model.get("release_date") or "")[:10])
        except ValueError:
            continue
        creator = model.get("model_creator") or {}
        if cutoff <= released <= (today or date.today()) and model.get("id") and model.get("name") and creator.get("name"):
            result.append(model)
    return result


def discover_aa_models(
    session: Session, *, source_id: str, models: list[dict], today: date | None = None
) -> dict[str, int]:
    """Idempotently add source-backed releases; unknown fields remain unknown."""
    recent = recent_aa_models(models, today=today)
    if not recent:
        return {"recent": 0, "created": 0, "updated": 0}
    payload = json.dumps(recent, ensure_ascii=False, sort_keys=True).encode("utf-8")
    snapshot = store_snapshot(
        session, source_id=source_id, payload=payload,
        stats={"kind": "model_catalog", "model_count": len(recent)},
    )
    providers = {p.slug: p for p in session.scalars(select(Provider))}
    releases = {r.slug: r for r in session.scalars(select(ModelRelease))}
    aliases = {a.alias.lower(): a for a in session.scalars(
        select(ModelAlias).where(ModelAlias.source_id == source_id)
    )}
    now = utcnow()
    created = updated = 0
    seen = set()
    new_providers = []
    new_families = []
    new_releases = []
    new_variants = []
    new_aliases = []
    for model in recent:
        external_id = str(model["id"])
        if external_id in seen:
            continue
        seen.add(external_id)
        creator_name = str(model["model_creator"]["name"]).strip()
        provider_slug = _slug(creator_name)[:64]
        if not provider_slug:
            continue
        provider = providers.get(provider_slug)
        if provider is None:
            provider = Provider(id=new_uuid(), slug=provider_slug, name=creator_name, provider_type="vendor")
            new_providers.append(provider)
            providers[provider_slug] = provider

        model_slug = _slug(str(model.get("slug") or model["name"]))
        if not model_slug:
            continue
        suffix = hashlib.sha256(external_id.encode()).hexdigest()[:10]
        release_slug = f"aa-{model_slug[:48]}-{suffix}"
        release = releases.get(release_slug)
        released = date.fromisoformat(str(model["release_date"])[:10])
        if release is None:
            family = ModelFamily(
                id=new_uuid(), provider_id=provider.id,
                slug=f"aa-{suffix}", name=str(model["name"])[:128],
            )
            release = ModelRelease(
                id=new_uuid(), family_id=family.id, canonical_name=str(model["name"])[:128],
                slug=release_slug, release_date=released, source_id=source_id,
                source_snapshot_id=snapshot.id, observed_at=now,
                confidence="medium", status="preview",
            )
            variant = ModelVariant(
                id=new_uuid(), model_release_id=release.id, name="standard",
                variant_type="standard", source_id=source_id,
                source_snapshot_id=snapshot.id, observed_at=now, confidence="medium",
            )
            release.default_variant_id = variant.id
            new_families.append(family)
            new_releases.append(release)
            new_variants.append(variant)
            releases[release_slug] = release
            created += 1
        else:
            release.canonical_name = str(model["name"])[:128]
            release.release_date = released
            release.source_snapshot_id = snapshot.id
            release.observed_at = now
            updated += 1

        # AA evaluation rows identify a model by its slug. Preserve an existing
        # reviewed alias instead of silently redirecting historical evaluations.
        alias = str(model.get("slug") or model["name"]).strip()
        if alias and alias.lower() not in aliases:
            mapped = ModelAlias(
                id=new_uuid(), source_id=source_id, model_variant_id=release.default_variant_id,
                alias=alias, external_id=external_id,
            )
            new_aliases.append(mapped)
            aliases[alias.lower()] = mapped
    for batch in (new_providers, new_families, new_releases, new_variants, new_aliases):
        if batch:
            session.add_all(batch)
            session.flush()
    return {"recent": len(recent), "created": created, "updated": updated}
