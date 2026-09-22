"""Background worker.   Run:  python -m hands.worker"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from .config import get_settings
from .db import connect, init_schema
from .pipeline import run_metrics_cycle, run_publish_cycle
from .providers import build_provider

log = logging.getLogger("hands.worker")


def _run(kind: str) -> None:
    settings = get_settings()
    conn = connect()
    try:
        init_schema(conn)
        provider = build_provider(settings)
        if kind == "publish":
            out = run_publish_cycle(conn, provider, settings)
            n = len(out["results"])
            if n or out["intake"]["created"]:
                log.info("publish cycle: %d new jobs, %d processed", len(out["intake"]["created"]), n)
        else:
            out = run_metrics_cycle(conn, provider, settings)
            log.info("metrics cycle: %s snapshots, %s scored", out["metrics"]["snapshots"], len(out["performance"]["scored"]))
    except Exception:  # noqa: BLE001 - a bad cycle must never kill the scheduler
        log.exception("%s cycle failed", kind)
    finally:
        conn.close()


def build_scheduler(blocking: bool = True):
    settings = get_settings()
    scheduler = BlockingScheduler(timezone="UTC") if blocking else BackgroundScheduler(timezone="UTC")
    now = datetime.now(timezone.utc)
    scheduler.add_job(_run, "interval", args=["publish"], seconds=settings.publish_poll_seconds,
                      id="publish", max_instances=1, coalesce=True, next_run_time=now)
    scheduler.add_job(_run, "interval", args=["metrics"], seconds=settings.metrics_poll_seconds,
                      id="metrics", max_instances=1, coalesce=True)
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    log.info("Hands worker starting (provider=%s, dry_run=%s, publish every %ss, metrics every %ss)",
             settings.provider, settings.dry_run, settings.publish_poll_seconds, settings.metrics_poll_seconds)
    try:
        build_scheduler(blocking=True).start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Hands worker stopped")


if __name__ == "__main__":
    main()
