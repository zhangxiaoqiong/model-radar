"""Create the test database (model_radar_test) using credentials from .env.

Usage: python scripts/create_test_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymysql  # noqa: E402

from backend_core.config import get_settings  # noqa: E402


def main() -> None:
    s = get_settings()
    database_name = s.db_name.strip()
    if not database_name.lower().endswith("_test"):
        raise SystemExit(
            f"refusing to create non-test database {database_name!r}; "
            "DB_NAME must end with '_test'"
        )
    if "`" in database_name:
        raise SystemExit("invalid DB_NAME")
    conn = pymysql.connect(host=s.db_host, port=s.db_port, user=s.db_user,
                           password=s.db_password, connect_timeout=10)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()
    print("test db ready")


if __name__ == "__main__":
    main()
