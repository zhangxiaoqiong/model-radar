"""Daily sync scheduler (APScheduler, blocking).

Usage: python scripts/scheduler.py          # runs daily sync at 06:00 UTC
       python scripts/scheduler.py --interval-minutes 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: E402

from backend_core.config import get_settings  # noqa: E402
from backend_core.db import create_db_engine, make_session_factory  # noqa: E402
from ingestion.adapters.artificial_analysis import AAClient  # noqa: E402
from ingestion.pipeline import (  # noqa: E402
    PipelineBusyError,
    recover_stale_runs,
    run_sync_pipeline,
)
from run_sync import fetch_aa_rows  # noqa: E402  (same directory)


def sync_once() -> None:
    settings = get_settings()
    client = AAClient(api_key=settings.aa_api_key, base_url=settings.aa_base_url)
    engine = create_db_engine(settings.database_url)
    session = make_session_factory(engine)()
    try:
        from sqlalchemy import select
        from backend_core.domain import PipelineRun, Source

        source = session.scalar(
            select(Source).where(Source.slug == "artificial_analysis")
        )
        if source is None:
            print("source missing — run scripts/seed.py first")
            return
        recovered = recover_stale_runs(session)
        if recovered:
            print(f"marked {recovered} expired pipeline run(s) as failed")
        pending = session.scalar(
            select(PipelineRun)
            .where(PipelineRun.status == "pending", PipelineRun.trigger == "manual")
            .order_by(PipelineRun.created_at.asc())
            .limit(1)
        )
        run = run_sync_pipeline(
            session,
            source_id=source.id,
            fetch_fn=lambda: fetch_aa_rows(client),
            pipeline_type=pending.pipeline_type if pending else "daily_sync",
            trigger=pending.trigger if pending else "schedule",
            existing_run=pending,
        )
        session.commit()
        print(f"sync run {run.id}: {run.status}")
    except PipelineBusyError as exc:
        session.rollback()
        print(f"sync skipped: {exc}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-minutes", type=int, default=None,
                        help="run every N minutes instead of daily")
    parser.add_argument("--hour", type=int, default=6, help="daily UTC hour")
    args = parser.parse_args()

    scheduler = BlockingScheduler(timezone="UTC")
    if args.interval_minutes:
        scheduler.add_job(sync_once, "interval", minutes=args.interval_minutes,
                          id="aa-sync")
    else:
        scheduler.add_job(sync_once, "cron", hour=args.hour, minute=0, id="aa-sync")
    print("scheduler started (Ctrl+C to stop)")
    scheduler.start()


if __name__ == "__main__":
    main()
