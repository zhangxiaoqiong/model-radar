"""Artificial Analysis Data API v2 client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx


class Tier(Enum):
    FREE = "free"
    PRO = "pro"
    COMMERCIAL = "commercial"


@dataclass
class RateLimitInfo:
    limit: int | None = None
    remaining: int | None = None
    reset: int | None = None


class AARateLimitedError(RuntimeError):
    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(f"rate limited (retry after {retry_after}s)")


class AAPermissionError(RuntimeError):
    pass


class AAClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://artificialanalysis.ai/api/v2",
        http: httpx.Client | None = None,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self._http = http
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self.tier: Tier | None = None

    def _client(self) -> httpx.Client:
        if self._http is not None:
            return self._http
        return httpx.Client(base_url=self.base_url, timeout=30.0)

    def get_json(self, path: str, params: dict | None = None) -> tuple[dict, RateLimitInfo]:
        if not self.api_key:
            raise AAPermissionError("AA_API_KEY is required for every Data API tier")

        owned = self._http is None
        client = self._client()
        try:
            last_exc: Exception | None = None
            for attempt in range(self._max_retries + 1):
                try:
                    response = client.get(
                        path.lstrip("/"),
                        params=params,
                        headers={"x-api-key": self.api_key},
                    )
                except httpx.HTTPError as exc:
                    last_exc = exc
                    if attempt == self._max_retries:
                        raise
                    time.sleep(self._backoff * (2 ** attempt))
                    continue

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise AARateLimitedError(float(retry_after) if retry_after else None)
                if response.status_code in (401, 403):
                    try:
                        detail = response.json().get("error", response.text)
                    except ValueError:
                        detail = response.text
                    raise AAPermissionError(f"Artificial Analysis access denied: {detail}")
                if response.status_code >= 500:
                    last_exc = RuntimeError(f"upstream {response.status_code}")
                    if attempt == self._max_retries:
                        raise last_exc
                    time.sleep(self._backoff * (2 ** attempt))
                    continue
                response.raise_for_status()

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Artificial Analysis response must be a JSON object")
                tier = data.get("tier")
                if tier in {item.value for item in Tier}:
                    self.tier = Tier(tier)
                return data, RateLimitInfo(
                    limit=_int_header(response, "X-RateLimit-Limit"),
                    remaining=_int_header(response, "X-RateLimit-Remaining"),
                    reset=_int_header(response, "X-RateLimit-Reset"),
                )
            raise last_exc or RuntimeError("unreachable")
        finally:
            if owned:
                client.close()

    def fetch_models(self) -> list[dict[str, Any]]:
        """Fetch every page of the documented free-shape language model list."""
        page = 1
        models: list[dict[str, Any]] = []
        while True:
            body, _ = self.get_json("language/models/free", params={"page": page})
            rows = body.get("data", [])
            if not isinstance(rows, list):
                raise ValueError("Artificial Analysis 'data' must be a list")
            models.extend(row for row in rows if isinstance(row, dict))
            pagination = body.get("pagination") or {}
            if not pagination.get("has_more"):
                break
            page += 1
        return models

    def fetch_evaluations(self) -> list[dict[str, Any]]:
        """Flatten model-level nested evaluation objects into warehouse rows."""
        rows: list[dict[str, Any]] = []
        for model in self.fetch_models():
            evaluations = model.get("evaluations") or {}
            if not isinstance(evaluations, dict):
                continue
            model_id = str(model.get("id") or model.get("slug") or model.get("name"))
            creator = model.get("model_creator") or {}
            for metric_slug, value in evaluations.items():
                if value is None or isinstance(value, (dict, list)):
                    continue
                rows.append(
                    {
                        "id": f"{model_id}:{metric_slug}",
                        "model_id": model.get("id"),
                        "model_name": model.get("slug") or model.get("name"),
                        "provider_slug": creator.get("slug"),
                        "index_name": metric_slug,
                        "value": value,
                    }
                )
        return rows


def _int_header(response: httpx.Response, name: str) -> int | None:
    value = response.headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
