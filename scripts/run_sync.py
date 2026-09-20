"""Manual / cron sync runner: pull Artificial Analysis data and run the pipeline.

Usage:
    python scripts/run_sync.py                 # daily_sync, schedule trigger
    python scripts/run_sync.py --dry-run       # fetch only, print row summary
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_core.config import get_settings  # noqa: E402
from backend_core.db import create_db_engine, make_session_factory  # noqa: E402
from ingestion.adapters.artificial_analysis import (  # noqa: E402
    AAClient,
    AAPermissionError,
    AARateLimitedError,
)
from ingestion.pipeline import run_sync_pipeline  # noqa: E402


def fetch_aa_rows(client: AAClient) -> list[dict]:
    rows = client.fetch_evaluations()
    if isinstance(rows, dict):
        rows = rows.get("data", [])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AA sync pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and summarize rows without DB writes")
    parser.add_argument("--source", default="artificial_analysis")
    args = parser.parse_args()

    settings = get_settings.cache_clear() or get_settings()
    client = AAClient(api_key=settings.aa_api_key, base_url=settings.aa_base_url)

    if args.dry_run:
        try:
            rows = fetch_aa_rows(client)
        except (AARateLimitedError, AAPermissionError) as exc:
            print(str(exc))
            return 1
        print(f"fetched {len(rows)} rows from {args.source}")
        for row in rows[:10]:
            print(" ", {k: row.get(k) for k in ("model_name", "index_name", "value")})
        return 0

    engine = create_db_engine(get_settings().database_url)
    session = make_session_factory(engine)()
    try:
        from sqlalchemy import select
        from backend_core.domain import Source

        source = session.scalar(
            select(Source).where(Source.slug == args.source)
        )
        if source is None:
            print(f"source '{args.source}' not found — run scripts/seed.py first")
            return 1

        run = run_sync_pipeline(
            session,
            source_id=source.id,
            fetch_fn=lambda: fetch_aa_rows(client),
        )
        session.commit()
        print(f"pipeline run {run.id}: {run.status}")
        for stage in run.stages if hasattr(run, "stages") else []:
            print(f"  {stage.stage_name}: {stage.status} {stage.detail or ''}")
        return 0 if run.status in ("success", "partial") else 1
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
