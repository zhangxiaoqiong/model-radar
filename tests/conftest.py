"""Test bootstrap: pin env before backend_core imports.

Every DB test file also sets these, but conftest runs first at collection
time, before any test module import triggers settings caching.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DB_NAME", "model_radar_test")
os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token")


def pytest_sessionstart(session):
    """Refuse to run destructive DB fixtures against a non-test database."""
    from backend_core.config import get_settings

    get_settings.cache_clear()
    name = get_settings().db_name.strip().lower()
    if not name.endswith("_test"):
        raise pytest.UsageError(
            f"refusing to run database tests against DB_NAME={name!r}; "
            "the name must end with '_test'"
        )
