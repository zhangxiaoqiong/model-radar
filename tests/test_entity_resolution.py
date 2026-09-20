"""Entity resolution matcher tests (pure logic, no DB)."""

from __future__ import annotations

from ingestion.entity_resolution import (
    MatchResult,
    match_external_model,
    normalize_name,
    similarity,
)


def test_normalize_name_collapses_punctuation_and_case():
    assert normalize_name("GPT-5.2  (Preview)") == "gpt 5 2 preview"
    assert normalize_name("Claude_Opus-4.5") == "claude opus 4 5"


def test_similarity_identical_is_one():
    assert similarity("gpt 5 2", "gpt 5 2") == 1.0


def test_similarity_orders_sensibly():
    high = similarity("gpt 5 2", "gpt 5 2 mini")
    low = similarity("gpt 5 2", "claude opus 4 5")
    assert high > low


ALIASES = [
    ("openai/gpt-5.2", "v-gpt52"),
    ("anthropic/claude-opus-4.5", "v-opus45"),
]
RELEASES = [
    ("gpt-5.2", "GPT-5.2", "v-gpt52"),
    ("gpt-5.2-mini", "GPT-5.2 mini", "v-gpt52mini"),
    ("claude-opus-4-5", "Claude Opus 4.5", "v-opus45"),
    ("glm-4-6", "GLM-4.6", "v-glm46"),
]


def test_exact_alias_match_wins_with_full_confidence():
    r = match_external_model("openai/gpt-5.2", ALIASES, RELEASES)
    assert r.variant_id == "v-gpt52"
    assert r.confidence == 1.0
    assert r.method == "alias"


def test_normalized_slug_match_high_confidence():
    r = match_external_model("gpt-5.2", ALIASES, RELEASES)
    assert r.variant_id == "v-gpt52"
    assert r.confidence >= 0.9
    assert r.method in ("slug", "canonical")


def test_no_match_returns_none():
    r = match_external_model("totally-unknown-model", ALIASES, RELEASES)
    assert r.variant_id is None
    assert r.confidence < 0.85


def test_below_threshold_returns_none_variant():
    # partial overlap should stay under the auto-map threshold
    r = match_external_model("gpt-5.2-mini-preview-2026", ALIASES, RELEASES)
    assert r.confidence < 0.85


def test_match_result_is_dataclass_with_evidence():
    r = match_external_model("openai/gpt-5.2", ALIASES, RELEASES)
    assert isinstance(r, MatchResult)
    assert r.evidence is not None
