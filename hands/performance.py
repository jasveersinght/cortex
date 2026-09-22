"""The 4 performance lenses (mirrors the Brain's 4 compliance lenses).

    Engagement 40%  weighted interactions per impression
    Reach      25%  how many people saw it
    Conversion 25%  click-through rate
    Timing     10%  was it posted inside a recommended window for that market

Each lens is 0-100 where 50 means "on benchmark" and 100 means "double the benchmark".
A lens the platform did not report is skipped and the remaining weights are
re-normalised, so missing data is never punished as zero. Once a platform has at least
8 scored posts, benchmarks switch from generic starting values to YOUR OWN median.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from statistics import median
from typing import Any

from . import audit
from .config import Settings
from .learning import best_hours, write_lessons
from .timing import MIN_SAMPLES_FOR_LEARNING, timing_fit
from .utils import dumps, parse_iso, to_iso, utcnow

# platform -> (weighted engagement rate %, impressions, click-through rate %)   (starting values)
BENCHMARKS = {
    "linkedin": (3.0, 800.0, 1.0),
    "instagram": (3.0, 1200.0, 1.0),
    "x": (1.5, 600.0, 0.8),
    "tiktok": (6.0, 3000.0, 1.0),
}
WEIGHTS = {"engagement": 0.40, "reach": 0.25, "conversion": 0.25, "timing": 0.10}
TIERS = ((80.0, "top_performer"), (55.0, "solid"), (30.0, "weak"), (0.0, "underperforming"))


def tier_for(score: float) -> str:
    for floor, name in TIERS:
        if score >= floor:
            return name
    return "underperforming"


def _ratio_score(value: float, benchmark: float) -> float:
    return max(0.0, min(100.0, 50.0 * value / benchmark)) if benchmark > 0 else 0.0


def _rates(snap: sqlite3.Row) -> dict[str, float | None]:
    impressions = snap["impressions"] or snap["views"] or snap["reach"]
    interactions = None
    if any(snap[k] is not None for k in ("likes", "comments", "shares", "saves")):
        interactions = (snap["likes"] or 0) + 2 * (snap["comments"] or 0) + 3 * (snap["shares"] or 0) + 2 * (snap["saves"] or 0)
    eng = interactions / impressions * 100 if impressions and interactions is not None else snap["engagement_rate"]
    ctr = snap["clicks"] / impressions * 100 if impressions and snap["clicks"] is not None else None
    return {"impressions": float(impressions) if impressions else None, "engagement_rate": eng, "ctr": ctr}


def _own_benchmarks(conn: sqlite3.Connection, platform: str, exclude_job: int) -> tuple[tuple[float, float, float], int] | None:
    rows = conn.execute(
        "SELECT m.* FROM post_metrics m JOIN (SELECT job_id, MAX(id) AS mid FROM post_metrics GROUP BY job_id) l ON m.id=l.mid "
        "JOIN publish_jobs j ON j.id=m.job_id WHERE j.platform=? AND j.id != ?",
        (platform, exclude_job),
    ).fetchall()
    if len(rows) < MIN_SAMPLES_FOR_LEARNING:
        return None
    rates = [_rates(r) for r in rows]

    def med(key: str, fallback: float) -> float:
        vals = [r[key] for r in rates if r[key]]
        return float(median(vals)) if vals else fallback

    base = BENCHMARKS[platform]
    return (med("engagement_rate", base[0]), med("impressions", base[1]), med("ctr", base[2])), len(rows)


def score_job(conn: sqlite3.Connection, job: sqlite3.Row, snap: sqlite3.Row, now: datetime) -> dict[str, Any]:
    platform = job["platform"]
    base = BENCHMARKS.get(platform, BENCHMARKS["linkedin"])
    own = _own_benchmarks(conn, platform, job["id"])
    bench, n_hist = (own if own else (base, 0))
    rates = _rates(snap)

    lenses: dict[str, float | None] = {
        "engagement": _ratio_score(rates["engagement_rate"], bench[0]) if rates["engagement_rate"] is not None else None,
        "reach": _ratio_score(rates["impressions"], bench[1]) if rates["impressions"] is not None else None,
        "conversion": _ratio_score(rates["ctr"], bench[2]) if rates["ctr"] is not None else None,
        "timing": float(timing_fit(platform, job["region"], parse_iso(job["scheduled_for"]), best_hours(conn, platform, job["region"]))) if job["scheduled_for"] else None,
    }
    live = {k: v for k, v in lenses.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in live)
    total = sum(WEIGHTS[k] * v for k, v in live.items()) / total_weight if total_weight else 0.0

    explain = {
        "benchmarks": {"engagement_rate": bench[0], "impressions": bench[1], "ctr": bench[2], "source": f"own history (n={n_hist})" if own else "starting values"},
        "values": rates,
        "skipped_lenses": [k for k, v in lenses.items() if v is None],
    }
    tier = tier_for(total)
    conn.execute(
        "INSERT INTO performance_scores (job_id, engagement_score, reach_score, conversion_score, timing_score, total_score, tier, explain_json, metrics_id, computed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET engagement_score=excluded.engagement_score, "
        "reach_score=excluded.reach_score, conversion_score=excluded.conversion_score, timing_score=excluded.timing_score, "
        "total_score=excluded.total_score, tier=excluded.tier, explain_json=excluded.explain_json, metrics_id=excluded.metrics_id, computed_at=excluded.computed_at",
        (job["id"], lenses["engagement"], lenses["reach"], lenses["conversion"], lenses["timing"], round(total, 1), tier, dumps(explain), snap["id"], to_iso(now)),
    )
    return {"job_id": job["id"], "total": round(total, 1), "tier": tier, "lenses": lenses}


def score_pending(conn: sqlite3.Connection, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    """Score every published post whose newest snapshot is unscored, and turn extremes into lessons."""
    now = now or utcnow()
    scored: list[dict[str, Any]] = []
    rows = conn.execute(
        "SELECT j.*, m.id AS snap_id FROM publish_jobs j "
        "JOIN (SELECT job_id, MAX(id) AS mid FROM post_metrics GROUP BY job_id) l ON l.job_id=j.id "
        "JOIN post_metrics m ON m.id=l.mid LEFT JOIN performance_scores s ON s.job_id=j.id "
        "WHERE j.status='published' AND (s.job_id IS NULL OR s.metrics_id IS NULL OR s.metrics_id < m.id) "
        "AND j.scheduled_for <= ?",
        (to_iso(now - timedelta(hours=settings.score_min_age_hours)),),
    ).fetchall()
    for job in rows:
        snap = conn.execute("SELECT * FROM post_metrics WHERE id=?", (job["snap_id"],)).fetchone()
        result = score_job(conn, job, snap, now)
        audit.log(conn, "scored", job_id=job["id"], asset_id=job["asset_id"], detail={"total": result["total"], "tier": result["tier"]})
        scored.append(result)
    lessons = write_lessons(conn, [s["job_id"] for s in scored])
    return {"scored": scored, "lessons_written": lessons}
