"""Discover recent model releases from the Artificial Analysis model feed."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend_core.db import new_uuid, utcnow
from backend_core.domain import (
    ModelAlias, ModelFamily, ModelPerformance, ModelPricing, ModelRelease,
    ModelVariant, Provider, Source,
)

from .snapshot_store import store_snapshot


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _number(value) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _base_name(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", value).strip()


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

    variant_ids = [alias.model_variant_id for alias in aliases.values()]
    existing_prices = set(session.scalars(
        select(ModelPricing.pricing_fingerprint)
        .where(ModelPricing.model_variant_id.in_(variant_ids))
    ))
    existing_performance = set(session.scalars(
        select(ModelPerformance.performance_fingerprint)
        .where(ModelPerformance.model_variant_id.in_(variant_ids))
    ))
    new_prices = []
    new_performance = []
    for model in recent:
        alias = aliases.get(str(model.get("slug") or model["name"]).strip().lower())
        if alias is None:
            continue
        variant_id = alias.model_variant_id
        pricing = model.get("pricing") or {}
        input_price = _number(pricing.get("price_1m_input_tokens"))
        output_price = _number(pricing.get("price_1m_output_tokens"))
        cached_price = _number(pricing.get("price_1m_cache_hit_tokens"))
        if input_price is not None or output_price is not None:
            fingerprint = _fingerprint(
                variant_id, source_id, input_price, output_price, cached_price, "USD"
            )
            if fingerprint not in existing_prices:
                new_prices.append(ModelPricing(
                    id=new_uuid(), model_variant_id=variant_id,
                    provider_name="Artificial Analysis model-level reference",
                    input_price_per_million=input_price,
                    output_price_per_million=output_price,
                    cached_input_price=cached_price, currency="USD",
                    source_id=source_id, source_snapshot_id=snapshot.id,
                    observed_at=now, confidence="medium",
                    pricing_fingerprint=fingerprint,
                ))
                existing_prices.add(fingerprint)

        performance = model.get("performance") or {}
        speed = _number(performance.get("median_output_tokens_per_second"))
        first_token = _number(performance.get("median_time_to_first_token_seconds"))
        latency = _number(performance.get("median_end_to_end_response_time_seconds"))
        if speed is not None or first_token is not None or latency is not None:
            fingerprint = _fingerprint(
                variant_id, source_id, speed, first_token, latency
            )
            if fingerprint not in existing_performance:
                new_performance.append(ModelPerformance(
                    id=new_uuid(), model_variant_id=variant_id,
                    provider_name="Artificial Analysis median",
                    tokens_per_second=speed,
                    time_to_first_token_ms=first_token * 1000 if first_token is not None else None,
                    latency_ms=latency * 1000 if latency is not None else None,
                    measured_at=now, source_id=source_id,
                    source_snapshot_id=snapshot.id, confidence="medium",
                    performance_fingerprint=fingerprint,
                    raw_payload=performance,
                ))
                existing_performance.add(fingerprint)
    session.add_all(new_prices + new_performance)
    session.flush()
    return {"recent": len(recent), "created": created, "updated": updated}


def enrich_openrouter_models(
    session: Session, *, aa_source_id: str, aa_models: list[dict],
    openrouter_models: list[dict],
) -> dict[str, int]:
    """Attach only unambiguous provider + base-name matches from OpenRouter."""
    candidates: dict[tuple[str, str], list[dict]] = {}
    for row in openrouter_models:
        model_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        if not model_id or model_id.startswith("~") or ":" in model_id or ": " not in name:
            continue
        provider_name, model_name = name.split(": ", 1)
        key = (_name_key(provider_name), _name_key(model_name))
        candidates.setdefault(key, []).append(row)

    aliases = {
        alias.alias.lower(): alias.model_variant_id
        for alias in session.scalars(
            select(ModelAlias).where(ModelAlias.source_id == aa_source_id)
        )
    }
    variant_ids = list(aliases.values())
    variant_rows = session.execute(
        select(ModelVariant, ModelFamily)
        .join(ModelRelease, ModelVariant.model_release_id == ModelRelease.id)
        .join(ModelFamily, ModelRelease.family_id == ModelFamily.id)
        .where(ModelVariant.id.in_(variant_ids))
    ).all()
    variants = {variant.id: (variant, family) for variant, family in variant_rows}
    matches = []
    for aa_model in recent_aa_models(aa_models):
        creator = (aa_model.get("model_creator") or {}).get("name")
        key = (_name_key(str(creator or "")), _name_key(_base_name(str(aa_model["name"]))))
        found = candidates.get(key, [])
        variant_id = aliases.get(str(aa_model.get("slug") or aa_model["name"]).lower())
        if len(found) == 1 and variant_id in variants:
            matches.append((variant_id, found[0]))
    if not matches:
        return {"matched": 0}

    source = session.scalar(select(Source).where(Source.slug == "openrouter"))
    if source is None:
        source = Source(
            id=new_uuid(), slug="openrouter", name="OpenRouter",
            source_type="aggregator", reliability_level="medium",
            base_url="https://openrouter.ai/api/v1/models", api_available=True,
        )
        session.add(source)
        session.flush()
    snapshot = store_snapshot(
        session, source_id=source.id,
        payload=json.dumps([row for _, row in matches], sort_keys=True, ensure_ascii=False).encode("utf-8"),
        stats={"kind": "model_enrichment", "matched": len(matches)},
    )
    observed = utcnow()
    for variant_id, row in matches:
        variant, family = variants[variant_id]
        context = row.get("context_length")
        if isinstance(context, int) and context > 0:
            variant.context_window = context
        architecture = row.get("architecture") or {}
        input_modes = architecture.get("input_modalities")
        output_modes = architecture.get("output_modalities")
        if isinstance(input_modes, list):
            variant.supports_text = "text" in input_modes
            variant.supports_image = "image" in input_modes
            variant.supports_audio = "audio" in input_modes or "speech" in input_modes
            variant.supports_video = "video" in input_modes
        if isinstance(output_modes, list):
            variant.supports_image = variant.supports_image or "image" in output_modes
            variant.supports_audio = variant.supports_audio or "audio" in output_modes
            variant.supports_video = variant.supports_video or "video" in output_modes
        parameters = row.get("supported_parameters")
        if isinstance(parameters, list):
            variant.supports_reasoning = bool(
                row.get("reasoning") or
                {"reasoning", "reasoning_effort", "include_reasoning"} & set(parameters)
            )
            variant.supports_tool_calling = "tools" in parameters
            variant.supports_structured_output = bool(
                {"structured_outputs", "response_format"} & set(parameters)
            )
        description = row.get("description")
        if isinstance(description, str) and description.strip():
            family.description = description.strip()
        variant.source_id = source.id
        variant.source_snapshot_id = snapshot.id
        variant.observed_at = observed
        variant.confidence = "medium"
    session.flush()
    return {"matched": len(matches)}
