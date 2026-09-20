"""Idempotent seed loader: providers, sources, capabilities, benchmarks,
tracked models (release + variants + endpoints + default_variant backfill).

Safe to re-run — everything upserts by natural keys.

Usage:
    python scripts/seed.py            # uses .env DB settings
    DB_NAME=model_radar_test python scripts/seed.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_core.config import get_settings  # noqa: E402
from backend_core.db import create_db_engine, make_session_factory, utcnow  # noqa: E402
from backend_core.domain import (  # noqa: E402
    Benchmark,
    BenchmarkCapabilityMap,
    BenchmarkMetric,
    BenchmarkVersion,
    Capability,
    ModelAlias,
    ModelEndpoint,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    Provider,
    Source,
)
from sqlalchemy import select  # noqa: E402

SEEDS = ROOT / "data" / "seeds"

PROVIDERS = [
    # slug, name, type, website
    ("openai", "OpenAI", "vendor", "https://openai.com"),
    ("anthropic", "Anthropic", "vendor", "https://www.anthropic.com"),
    ("google", "Google", "vendor", "https://deepmind.google"),
    ("deepseek", "DeepSeek", "vendor", "https://www.deepseek.com"),
    ("alibaba", "Alibaba (Qwen)", "vendor", "https://qwen.ai"),
    ("meta", "Meta", "vendor", "https://ai.meta.com"),
    ("xai", "xAI", "vendor", "https://x.ai"),
    ("mistral", "Mistral AI", "vendor", "https://mistral.ai"),
    ("zhipu", "Zhipu AI", "vendor", "https://zhipuai.cn"),
    ("openrouter", "OpenRouter", "aggregator", "https://openrouter.ai"),
]

SOURCES = [
    # slug, name, source_type, reliability, api_available, base_url
    ("artificial_analysis", "Artificial Analysis", "independent_eval", "high", True,
     "https://artificialanalysis.ai/api/v2"),
    ("livebench", "LiveBench", "independent_eval", "high", False,
     "https://livebench.ai"),
    ("openrouter", "OpenRouter", "aggregator", "medium", True,
     "https://openrouter.ai/api"),
    ("official_metadata", "Official Provider Metadata", "vendor", "high", False, None),
    ("curated_seed", "Curated Development Seed", "internal", "low", False, None),
]


def load_yaml(name: str) -> list[dict]:
    with open(SEEDS / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def seed_providers_and_sources(session) -> None:
    for slug, name, ptype, website in PROVIDERS:
        obj = session.scalar(select(Provider).where(Provider.slug == slug))
        if obj is None:
            session.add(Provider(slug=slug, name=name, provider_type=ptype, website_url=website))
            print(f"  + provider {slug}")
    for slug, name, stype, rel, api, base in SOURCES:
        obj = session.scalar(select(Source).where(Source.slug == slug))
        if obj is None:
            session.add(
                Source(slug=slug, name=name, source_type=stype, reliability_level=rel,
                       api_available=api, base_url=base)
            )
            print(f"  + source {slug}")
    session.flush()


def seed_capabilities(session) -> dict[str, str]:
    slug_to_id: dict[str, str] = {}
    for row in load_yaml("capabilities.yaml"):
        obj = session.scalar(select(Capability).where(Capability.slug == row["slug"]))
        if obj is None:
            obj = Capability(
                slug=row["slug"], name=row["name"],
                parent_id=slug_to_id.get(row.get("parent")),
                level=row["level"], sort_order=row["sort_order"],
            )
            session.add(obj)
            session.flush()
            print(f"  + capability {row['slug']}")
        slug_to_id[row["slug"]] = obj.id
    return slug_to_id


def seed_benchmarks(session, cap_ids: dict[str, str]) -> None:
    official_source = session.scalar(select(Source).where(Source.slug == "official_metadata"))
    for row in load_yaml("tracked_benchmarks.yaml"):
        bench = session.scalar(select(Benchmark).where(Benchmark.slug == row["slug"]))
        if bench is None:
            bench = Benchmark(
                slug=row["slug"], name=row["name"], category=row.get("category"),
                description=row.get("description"), official_url=row.get("official_url"),
                source_id=official_source.id,
                dataset_public=row.get("dataset_public", True),
                dynamic=row.get("dynamic", False),
                contamination_risk=row.get("contamination_risk"),
            )
            session.add(bench)
            session.flush()
            print(f"  + benchmark {row['slug']}")

        version = session.scalar(
            select(BenchmarkVersion).where(
                BenchmarkVersion.benchmark_id == bench.id,
                BenchmarkVersion.version == row["version"],
            )
        )
        if version is None:
            version = BenchmarkVersion(benchmark_id=bench.id, version=row["version"])
            session.add(version)
            session.flush()
            print(f"    + version {row['version']}")

        m = row["metric"]
        metric = session.scalar(
            select(BenchmarkMetric).where(
                BenchmarkMetric.benchmark_version_id == version.id,
                BenchmarkMetric.slug == m["slug"],
                BenchmarkMetric.dataset_split == "",
            )
        )
        if metric is None:
            session.add(BenchmarkMetric(
                benchmark_version_id=version.id, slug=m["slug"], name=m["name"],
                dataset_split="", unit=m["unit"], score_direction=m["score_direction"],
                normalization_method=m.get("normalization_method", "minmax"),
            ))
            print(f"    + metric {m['slug']}")

        for cap in row.get("capabilities", []):
            exists = session.scalar(
                select(BenchmarkCapabilityMap).where(
                    BenchmarkCapabilityMap.benchmark_id == bench.id,
                    BenchmarkCapabilityMap.capability_id == cap_ids[cap["slug"]],
                )
            )
            if exists is None:
                session.add(BenchmarkCapabilityMap(
                    benchmark_id=bench.id, capability_id=cap_ids[cap["slug"]],
                    weight=cap["weight"],
                ))


def seed_models(session) -> int:
    count = 0
    seed_source = session.scalar(select(Source).where(Source.slug == "curated_seed"))
    assert seed_source is not None
    for row in load_yaml("tracked_models.yaml"):
        provider = session.scalar(select(Provider).where(Provider.slug == row["provider"]))
        assert provider is not None, f"provider {row['provider']} missing"
        family = session.scalar(
            select(ModelFamily).where(
                ModelFamily.provider_id == provider.id, ModelFamily.slug == row["family"]
            )
        )
        if family is None:
            family = ModelFamily(provider_id=provider.id, slug=row["family"],
                                 name=row["family"].replace("-", " ").title())
            session.add(family)
            session.flush()
            print(f"  + family {row['family']}")

        release = session.scalar(
            select(ModelRelease).where(ModelRelease.slug == row["release_slug"])
        )
        if release is None:
            release = ModelRelease(
                family_id=family.id,
                canonical_name=row["canonical_name"],
                slug=row["release_slug"],
                release_date=date.fromisoformat(row["release_date"]) if row.get("release_date") else None,
                knowledge_cutoff=date.fromisoformat(row["knowledge_cutoff"]) if row.get("knowledge_cutoff") else None,
                open_weight=row.get("open_weight", False),
                license=row.get("license"),
                status=row.get("status", "preview"),
                source_id=seed_source.id,
                observed_at=utcnow(),
                confidence="low",
            )
            session.add(release)
            session.flush()
            print(f"  + release {row['release_slug']}")

        supports = row.get("supports", {})
        default_variant = None
        for v in row.get("variants", [{"name": "standard", "variant_type": "standard"}]):
            variant = session.scalar(
                select(ModelVariant).where(
                    ModelVariant.model_release_id == release.id,
                    ModelVariant.name == v["name"],
                )
            )
            if variant is None:
                variant = ModelVariant(
                    model_release_id=release.id,
                    name=v["name"],
                    variant_type=v.get("variant_type", "standard"),
                    reasoning_level=v.get("reasoning_level"),
                    context_window=row.get("context_window"),
                    max_output_tokens=row.get("max_output_tokens"),
                    supports_image=supports.get("image", False),
                    supports_audio=supports.get("audio", False),
                    supports_video=supports.get("video", False),
                    supports_reasoning=supports.get("reasoning", False),
                    supports_tool_calling=supports.get("tool_calling", False),
                    supports_structured_output=supports.get("structured_output", False),
                    source_id=seed_source.id,
                    observed_at=utcnow(),
                    confidence="low",
                )
                session.add(variant)
                session.flush()
                print(f"    + variant {v['name']}")
            if default_variant is None:
                default_variant = variant

        if release.default_variant_id != default_variant.id:
            # app-layer validated circular reference (spec §5.3)
            assert default_variant.model_release_id == release.id
            release.default_variant_id = default_variant.id

        for e in row.get("endpoints", []):
            ep_provider = session.scalar(
                select(Provider).where(Provider.slug == e["provider"])
            )
            assert ep_provider is not None, f"endpoint provider {e['provider']} missing"
            endpoint = session.scalar(
                select(ModelEndpoint).where(
                    ModelEndpoint.provider_id == ep_provider.id,
                    ModelEndpoint.external_model_id == e["external_model_id"],
                )
            )
            if endpoint is None:
                session.add(ModelEndpoint(
                    model_variant_id=default_variant.id,
                    provider_id=ep_provider.id,
                    external_model_id=e["external_model_id"],
                    endpoint_type=e["endpoint_type"],
                    api_base_url=e.get("api_base_url"),
                    context_window=row.get("context_window"),
                    max_output_tokens=row.get("max_output_tokens"),
                    source_id=seed_source.id,
                ))
                print(f"    + endpoint {e['provider']}/{e['external_model_id']}")

        # official alias for entity resolution: "<provider>/<slug>" from OpenRouter
        or_source = session.get(Source, session.scalar(
            select(Source.id).where(Source.slug == "openrouter")))
        for e in row.get("endpoints", []):
            if e["provider"] == "openrouter":
                alias = session.scalar(
                    select(ModelAlias).where(
                        ModelAlias.source_id == or_source.id,
                        ModelAlias.alias == e["external_model_id"],
                    )
                )
                if alias is None:
                    session.add(ModelAlias(
                        model_variant_id=default_variant.id,
                        source_id=or_source.id,
                        alias=e["external_model_id"],
                        external_id=e["external_model_id"],
                    ))
                    print(f"    + alias {e['external_model_id']}")
        count += 1
    return count


def main() -> None:
    get_settings.cache_clear()
    engine = create_db_engine(get_settings().database_url)
    session = make_session_factory(engine)()
    try:
        print("Seeding providers & sources...")
        seed_providers_and_sources(session)
        print("Seeding capabilities...")
        cap_ids = seed_capabilities(session)
        print("Seeding benchmarks...")
        seed_benchmarks(session, cap_ids)
        print("Seeding models...")
        n = seed_models(session)
        session.commit()
        print(f"Done. {n} tracked releases processed.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
