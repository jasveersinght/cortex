"""Pull engagement back into the database (snapshots, never overwritten)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from . import audit
from .config import Settings
from .providers.base import Provider, ProviderError
from .utils import dumps, parse_iso, to_iso, utcnow

LOOKBACK_DAYS = 30


def collect_metrics(conn: sqlite3.Connection, provider: Provider, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    out: dict[str, Any] = {"snapshots": 0, "pending": 0, "errors": 0, "published": 0, "failed": 0}
    jobs = conn.execute(
        "SELECT * FROM publish_jobs WHERE status IN ('scheduled','published') AND external_post_id IS NOT NULL "
        "AND scheduled_for <= ? AND scheduled_for >= ?",
        (to_iso(now), to_iso(now - timedelta(days=LOOKBACK_DAYS))),
    ).fetchall()
    for job in jobs:
        last = conn.execute("SELECT fetched_at FROM post_metrics WHERE job_id=? ORDER BY id DESC LIMIT 1", (job["id"],)).fetchone()
        if last and now - parse_iso(last["fetched_at"]) < timedelta(minutes=settings.metrics_min_interval_minutes):
            continue
        try:
            fm = provider.fetch_metrics(job["external_post_id"], job["platform"])
        except ProviderError as exc:
            out["errors"] += 1
            audit.log(conn, "metrics_error", job_id=job["id"], asset_id=job["asset_id"], detail=str(exc))
            continue
        if fm is None:
            out["pending"] += 1
            continue
        if fm.status == "error":
            conn.execute("UPDATE publish_jobs SET status='failed', last_error=?, updated_at=? WHERE id=?",
                         ("provider reported that the post failed to publish", to_iso(now), job["id"]))
            audit.log(conn, "provider_reported_failure", job_id=job["id"], asset_id=job["asset_id"])
            out["failed"] += 1
            continue
        if job["status"] == "scheduled" and (fm.has_data or fm.status == "sent"):
            conn.execute("UPDATE publish_jobs SET status='published', published_at=?, updated_at=? WHERE id=?",
                         (job["scheduled_for"], to_iso(now), job["id"]))
            audit.log(conn, "published", job_id=job["id"], asset_id=job["asset_id"])
            out["published"] += 1
        if not fm.has_data:  # a missing metric is "not reported yet", not zero
            out["pending"] += 1
            continue
        conn.execute(
            "INSERT INTO post_metrics (job_id, fetched_at, impressions, reach, views, likes, comments, shares, saves, clicks, engagement_rate, raw_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (job["id"], to_iso(now), fm.impressions, fm.reach, fm.views, fm.likes, fm.comments, fm.shares, fm.saves, fm.clicks, fm.engagement_rate, dumps(fm.raw)),
        )
        out["snapshots"] += 1
    return out
