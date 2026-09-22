"""Public OpenRouter catalog: model-level context and advertised capabilities."""

from __future__ import annotations

import httpx

MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_openrouter_models() -> list[dict]:
    response = httpx.get(MODELS_URL, timeout=30.0)
    response.raise_for_status()
    rows = response.json().get("data")
    if not isinstance(rows, list):
        raise ValueError("OpenRouter models response has no data list")
    return [row for row in rows if isinstance(row, dict)]
