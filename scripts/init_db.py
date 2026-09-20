"""Bootstrap or upgrade the schema through Alembic.

Usage:
    python scripts/init_db.py                     # real DB (from .env)
    DB_NAME=model_radar_test python scripts/init_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from backend_core.config import get_settings  # noqa: E402


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    print(f"schema is at Alembic head in {settings.db_name}")


if __name__ == "__main__":
    main()
