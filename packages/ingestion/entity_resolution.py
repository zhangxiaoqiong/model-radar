"""Entity resolution: external model names -> registry variants (spec §10).

Strategy (in order):
1. exact alias match (case-insensitive)                     -> confidence 1.0
2. normalized slug / canonical-name similarity (difflib)    -> best score
Auto-map threshold 0.85; anything below goes to the manual resolution queue.
External syncs NEVER auto-create models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

AUTO_MAP_THRESHOLD = 0.85

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    """lowercase, punctuation -> space, collapse whitespace."""
    return _NON_ALNUM.sub(" ", name.lower()).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class MatchResult:
    variant_id: str | None
    confidence: float
    method: str | None = None
    evidence: dict = field(default_factory=dict)
    suggested_variant_id: str | None = None


def match_external_model(
    external_name: str,
    aliases: list[tuple[str, str]],
    releases: list[tuple],
    external_provider: str | None = None,
) -> MatchResult:
    """Resolve safely, requiring provider agreement whenever it is available.

    releases are ``(slug, canonical_name, variant_id[, provider_slug])``.
    """
    wanted = external_name.strip().lower()
    for alias, variant_id in aliases:
        if alias.strip().lower() == wanted:
            return MatchResult(variant_id, 1.0, "alias",
                               {"matched_alias": alias})

    target = normalize_name(external_name)
    best: tuple[float, str, str, str] | None = None  # (score, method, slug, variant_id)
    for release in releases:
        slug, canonical, variant_id = release[:3]
        provider_slug = release[3] if len(release) > 3 else None
        if external_provider and provider_slug and external_provider != provider_slug:
            continue
        for method, candidate in (("slug", normalize_name(slug)),
                                  ("canonical", normalize_name(canonical))):
            score = 1.0 if candidate == target else similarity(target, candidate)
            if best is None or score > best[0]:
                best = (score, method, slug, variant_id)

    if best is None:
        return MatchResult(None, 0.0, evidence={"reason": "no releases"})

    score, method, slug, variant_id = best
    if score >= AUTO_MAP_THRESHOLD:
        return MatchResult(variant_id, round(score, 4), method,
                           {"matched_release": slug, "target": target})
    # below threshold: no auto-map; report best candidate as evidence for review
    return MatchResult(None, round(score, 4), evidence={
        "best_candidate": slug, "best_score": round(score, 4), "target": target,
    }, suggested_variant_id=variant_id)
