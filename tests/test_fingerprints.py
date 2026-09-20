"""TDD: fingerprint canonicalization, stability and observation-diff semantics.

Spec §8.3: identity = Model x Benchmark x config (stable across replays);
observation = identity + score + CI + sample size (immutable version key).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend_core.services.fingerprints import (
    evaluation_identity_hash,
    observation_fingerprint,
    observation_fields_unchanged,
    pricing_fingerprint,
)

BASE_IDENTITY = dict(
    model_variant_id="v-1",
    model_endpoint_id=None,
    benchmark_id="b-1",
    benchmark_version_id="ver-1",
    benchmark_metric_id="m-1",
    source_id="s-1",
    evaluator="AA",
    harness=None,
    harness_version=None,
    reasoning_setting="high",
    temperature=Decimal("0.0"),
    random_seed=42,
    few_shot_count=0,
    agent_scaffold=None,
    agent_scaffold_version=None,
    dataset_revision=None,
    scorer_version=None,
    runtime_image="eval@sha256:test",
    prompt_config={"temperature": 0.0, "system": "You are a coder."},
    decoding_config=None,
)


class TestIdentityHash:
    def test_is_order_insensitive_for_json_fields(self):
        a = {**BASE_IDENTITY, "prompt_config": {"a": 1, "b": {"x": 2, "y": 3}}}
        b = {**BASE_IDENTITY, "prompt_config": {"b": {"y": 3, "x": 2}, "a": 1}}
        assert evaluation_identity_hash(**a) == evaluation_identity_hash(**b)

    def test_treats_null_and_empty_and_missing_as_equivalent(self):
        a = {**BASE_IDENTITY, "prompt_config": None, "decoding_config": None}
        b = {**BASE_IDENTITY, "prompt_config": {}, "decoding_config": None}
        assert evaluation_identity_hash(**a) == evaluation_identity_hash(**b)

    def test_ignores_score_and_sample(self):
        h1 = evaluation_identity_hash(**BASE_IDENTITY)
        h2 = evaluation_identity_hash(**{**BASE_IDENTITY, "prompt_config": BASE_IDENTITY["prompt_config"]})
        assert h1 == h2  # identity never sees observation fields

    def test_changes_when_reasoning_setting_changes(self):
        h1 = evaluation_identity_hash(**BASE_IDENTITY)
        h2 = evaluation_identity_hash(**{**BASE_IDENTITY, "reasoning_setting": "low"})
        assert h1 != h2

    def test_changes_when_endpoint_changes(self):
        h1 = evaluation_identity_hash(**BASE_IDENTITY)
        h2 = evaluation_identity_hash(**{**BASE_IDENTITY, "model_endpoint_id": "e-9"})
        assert h1 != h2

    @pytest.mark.parametrize(
        ("field", "value"),
        [("temperature", Decimal("0.7")), ("random_seed", 7),
         ("few_shot_count", 5), ("runtime_image", "eval@sha256:other")],
    )
    def test_changes_when_reproducibility_config_changes(self, field, value):
        h1 = evaluation_identity_hash(**BASE_IDENTITY)
        h2 = evaluation_identity_hash(**{**BASE_IDENTITY, field: value})
        assert h1 != h2


class TestObservationFingerprint:
    def test_stable_for_same_fields(self):
        kwargs = dict(
            score=Decimal("72.3"),
            confidence_lower=None,
            confidence_upper=None,
            sample_size=500,
            external_evaluation_id=None,
            source_snapshot_id="snap-1",
        )
        assert observation_fingerprint("idh", **kwargs) == observation_fingerprint("idh", **kwargs)

    def test_changes_when_score_changes(self):
        common = dict(
            confidence_lower=None, confidence_upper=None, sample_size=500,
            external_evaluation_id=None, source_snapshot_id="snap-1",
        )
        f1 = observation_fingerprint("idh", score=Decimal("72.3"), **common)
        f2 = observation_fingerprint("idh", score=Decimal("72.4"), **common)
        assert f1 != f2

    def test_decimal_scale_is_normalized(self):
        common = dict(
            confidence_lower=None, confidence_upper=None, sample_size=500,
            external_evaluation_id=None, source_snapshot_id="snap-1",
        )
        f1 = observation_fingerprint("idh", score=Decimal("72.3"), **common)
        f2 = observation_fingerprint("idh", score=Decimal("72.30"), **common)
        assert f1 == f2

    def test_changes_when_snapshot_changes(self):
        common = dict(
            score=Decimal("72.3"), confidence_lower=None, confidence_upper=None,
            sample_size=500, external_evaluation_id=None,
        )
        f1 = observation_fingerprint("idh", source_snapshot_id="snap-1", **common)
        f2 = observation_fingerprint("idh", source_snapshot_id="snap-2", **common)
        assert f1 != f2


class TestObservationDiff:
    def test_unchanged_when_only_snapshot_differs(self):
        """Review finding #1: same score in a new snapshot is a re-confirmation,
        not a new observation — daily bloat must be avoided."""
        assert observation_fields_unchanged(
            score=Decimal("72.3"), confidence_lower=None, confidence_upper=None,
            sample_size=500,
            prev_score=Decimal("72.30"), prev_confidence_lower=None, prev_confidence_upper=None,
            prev_sample_size=500,
        )

    def test_changed_when_score_differs(self):
        assert not observation_fields_unchanged(
            score=Decimal("72.3"), confidence_lower=None, confidence_upper=None,
            sample_size=500,
            prev_score=Decimal("72.4"), prev_confidence_lower=None, prev_confidence_upper=None,
            prev_sample_size=500,
        )

    def test_changed_when_sample_size_differs(self):
        assert not observation_fields_unchanged(
            score=Decimal("72.3"), confidence_lower=None, confidence_upper=None,
            sample_size=500,
            prev_score=Decimal("72.3"), prev_confidence_lower=None, prev_confidence_upper=None,
            prev_sample_size=250,
        )


class TestPricingFingerprint:
    def test_excludes_snapshot_and_observed_at(self):
        base = dict(
            model_variant_id="v-1", model_endpoint_id=None,
            input_price_per_million=Decimal("3.0"),
            output_price_per_million=Decimal("15.0"),
            cached_input_price=None,
            currency="USD",
            effective_from="2026-09-01T00:00:00",
            source_id="s-1",
        )
        f1 = pricing_fingerprint(observed_at="2026-09-20T01:00:00", **base)
        f2 = pricing_fingerprint(observed_at="2026-09-21T01:00:00", **base)
        assert f1 == f2

    def test_changes_when_price_changes(self):
        common = dict(
            model_variant_id="v-1", model_endpoint_id=None,
            output_price_per_million=Decimal("15.0"),
            cached_input_price=None, currency="USD",
            effective_from="2026-09-01T00:00:00", source_id="s-1",
            observed_at="2026-09-20T01:00:00",
        )
        f1 = pricing_fingerprint(input_price_per_million=Decimal("3.0"), **common)
        f2 = pricing_fingerprint(input_price_per_million=Decimal("2.5"), **common)
        assert f1 != f2
