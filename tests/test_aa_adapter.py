"""Artificial Analysis adapter tests — all HTTP via httpx.MockTransport."""

from __future__ import annotations

import httpx
import pytest

from ingestion.adapters.artificial_analysis import (
    AAClient,
    AAPermissionError,
    AARateLimitedError,
    Tier,
)


def _client(handler, **kw) -> AAClient:
    return AAClient(
        api_key="test-key",
        base_url="https://artificialanalysis.ai/api/v2",
        http=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://artificialanalysis.ai/api/v2/"),
        **kw,
    )


def test_get_json_parses_body_and_rate_limit_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, json={"ok": True}, headers={
            "X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "87",
            "X-RateLimit-Reset": "1726700000",
        })

    c = _client(handler)
    data, rl = c.get_json("v1/models")
    assert data == {"ok": True}
    assert rl.limit == 100
    assert rl.remaining == 87
    assert rl.reset == 1726700000


def test_429_raises_rate_limited_error():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    c = _client(handler, max_retries=0)
    with pytest.raises(AARateLimitedError):
        c.get_json("v1/models")


def test_server_error_is_retried_then_raised():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    c = _client(handler, max_retries=1)
    data, _ = c.get_json("v1/models")
    assert data == {"ok": True}
    assert calls["n"] == 2


def test_api_key_is_required_for_all_tiers():
    c = AAClient(api_key="", base_url="https://artificialanalysis.ai/api/v2")
    with pytest.raises(AAPermissionError):
        c.get_json("language/models/free")


def test_tier_comes_from_response_and_evaluations_are_flattened():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "tier": "free",
            "pagination": {"page": 1, "has_more": False},
            "data": [{
                "id": "model-1",
                "name": "Model One",
                "slug": "model-one",
                "model_creator": {"slug": "vendor"},
                "evaluations": {"gpqa-diamond": 0.72, "nested": {"x": 1}},
            }],
        })

    c = _client(handler)
    rows = c.fetch_evaluations()
    assert c.tier == Tier.FREE
    assert rows == [{
        "id": "model-1:gpqa-diamond",
        "model_id": "model-1",
        "model_name": "model-one",
        "provider_slug": "vendor",
        "index_name": "gpqa-diamond",
        "value": 0.72,
    }]
