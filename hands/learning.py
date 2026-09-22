"""Closing the loop: what performed -> lessons for the Brain and guidance for the Content agent."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from statistics import mean
from typing import Any

from . import audit
from .db import insert_dynamic, table_exists
from .timing import MIN_SAMPLES_FOR_LEARNING, region_tz, tz_label
from .utils import loads, parse_iso

PERF_TAG_PREFIX = "perf:"


def _scored_rows(conn: sqlite3.Connection, brand: str | None = None, platform: str | None = None, region: str | None = None, job_id: int | None = None) -> list[sqlite3.Row]:
    sql = (
        "SELECT j.*, s.total_score, s.tier, a.body_text, a.content_type, "
        "(SELECT media_type FROM asset_media m WHERE m.asset_id=j.asset_id) AS media_type "
        "FROM performance_scores s JOIN publish_jobs j ON j.id=s.job_id "
        "LEFT JOIN assets a ON CAST(a.id AS TEXT)=j.asset_id WHERE 1=1"
    )
    args: list[Any] = []
    if brand:
        sql += " AND lower(j.brand)=lower(?)"
        args.append(brand)
    if platform:
        sql += " AND j.platform=?"
        args.append(platform)
    if region:
        sql += " AND lower(j.region)=lower(?)"
        args.append(region)
    if job_id is not None:
        sql += " AND j.id=?"
        args.append(job_id)
    return conn.execute(sql, args).fetchall()


def best_hours(conn: sqlite3.Connection, platform: str, region: str | None, top: int = 3) -> list[int]:
    """Local hours with the best average score. Empty until enough posts are scored."""
    rows = _scored_rows(conn, platform=platform, region=region)
    rows = [r for r in rows if r["scheduled_for"]]
    if len(rows) < MIN_SAMPLES_FOR_LEARNING:
        return []
    tz = region_tz(region)
    by_hour: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        by_hour[parse_iso(r["scheduled_for"]).astimezone(tz).hour].append(r["total_score"])
    ranked = sorted(by_hour.items(), key=lambda kv: mean(kv[1]), reverse=True)
    return sorted(h for h, _ in ranked[:top])


def hashtag_leaderboard(conn: sqlite3.Connection, brand: str | None, platform: str | None, limit: int = 8) -> list[dict[str, Any]]:
    """Hashtags that appeared on posts scoring 'solid' or better, ranked by average score."""
    scores: dict[str, list[float]] = defaultdict(list)
    for r in _scored_rows(conn, brand, platform):
        if r["total_score"] < 55:
            continue
        for tag in loads(r["hashtags_json"], []) or []:
            scores[tag.lower()].append(r["total_score"])
    board = [{"tag": t, "uses": len(v), "avg_score": round(mean(v), 1)} for t, v in scores.items()]
    board.sort(key=lambda x: (x["avg_score"], x["uses"]), reverse=True)
    return board[:limit]


def proven_hashtags(conn: sqlite3.Connection, brand: str | None, platform: str | None, limit: int = 8) -> list[str]:
    return [b["tag"] for b in hashtag_leaderboard(conn, brand, platform, limit)]


def _describe(row: sqlite3.Row) -> str:
    when = parse_iso(row["scheduled_for"]).astimezone(region_tz(row["region"])) if row["scheduled_for"] else None
    tags = len(loads(row["hashtags_json"], []) or [])
    bits = [f"{row['platform']} post for {row['brand']}", f"score {row['total_score']:.0f}/100 ({row['tier']})"]
    if when:
        bits.append(f"posted {when:%a %H:%M} {tz_label(row['region'])}")
    if row["body_text"]:
        bits.append(f"{len(row['body_text'])} chars")
    bits.append(f"{tags} hashtags")
    bits.append(row["media_type"] or "text only")
    return ", ".join(bits)


def write_lessons(conn: sqlite3.Connection, job_ids: list[int]) -> int:
    """Append performance lessons to the Brain's lessons_learned table (tag prefix 'perf:')."""
    if not job_ids or not table_exists(conn, "lessons_learned"):
        return 0
    written = 0
    for job_id in job_ids:
        rows = _scored_rows(conn, job_id=job_id)
        if not rows or rows[0]["tier"] not in {"top_performer", "underperforming"}:
            continue
        row = rows[0]
        tag = f"{PERF_TAG_PREFIX}{row['tier']}"
        exists = conn.execute(
            "SELECT 1 FROM lessons_learned WHERE CAST(asset_id AS TEXT)=? AND tag=?", (row["asset_id"], tag)
        ).fetchone()
        if exists:
            continue
        verdict = "Repeat what worked here" if row["tier"] == "top_performer" else "Avoid repeating this pattern"
        insert_dynamic(conn, "lessons_learned", {"asset_id": row["asset_id"], "tag": tag, "note": f"{verdict}: {_describe(row)}."})
        audit.log(conn, "lesson_written", job_id=job_id, asset_id=row["asset_id"], detail={"tag": tag})
        written += 1
    return written


def insights_for(conn: sqlite3.Connection, brand: str | None, platform: str | None) -> dict[str, Any]:
    """Measured guidance for the Content agent. Deterministic: no LLM, no invention."""
    rows = _scored_rows(conn, brand, platform)
    out: dict[str, Any] = {"brand": brand, "platform": platform, "scored_posts": len(rows), "ready": len(rows) >= 3}
    if not rows:
        out["prompt_block"] = ""
        return out

    out["avg_score"] = round(mean(r["total_score"] for r in rows), 1)
    tiers: dict[str, int] = defaultdict(int)
    for r in rows:
        tiers[r["tier"]] += 1
    out["tiers"] = dict(tiers)

    lines: list[str] = []
    top = [r for r in rows if r["tier"] in {"top_performer", "solid"} and r["body_text"]]
    weak = [r for r in rows if r["tier"] in {"weak", "underperforming"} and r["body_text"]]
    if top and weak:
        t_len, w_len = mean(len(r["body_text"]) for r in top), mean(len(r["body_text"]) for r in weak)
        out["avg_len_top"], out["avg_len_weak"] = round(t_len), round(w_len)
        if t_len < w_len * 0.85:
            lines.append(f"Shorter posts performed better (about {t_len:.0f} chars vs {w_len:.0f}).")
        elif t_len > w_len * 1.15:
            lines.append(f"Longer, more substantive posts performed better (about {t_len:.0f} chars vs {w_len:.0f}).")

    with_media = [r["total_score"] for r in rows if r["media_type"]]
    without = [r["total_score"] for r in rows if not r["media_type"]]
    if with_media and without:
        out["media_avg"], out["text_only_avg"] = round(mean(with_media), 1), round(mean(without), 1)
        if mean(with_media) > mean(without) + 5:
            lines.append("Posts with media outscored text-only posts; include a visual where the platform allows.")
        elif mean(without) > mean(with_media) + 5:
            lines.append("Text-only posts outscored posts with media on this channel.")

    hours = best_hours(conn, platform, None) if platform else []
    if hours:
        out["best_hours_local"] = hours
        lines.append("Best-performing local posting hours: " + ", ".join(f"{h:02d}:00" for h in hours) + ".")

    tags = proven_hashtags(conn, brand, platform, 6)
    if tags:
        out["proven_hashtags"] = tags
        lines.append("Hashtags on high-scoring posts: " + " ".join(tags) + ".")

    if lines and out["ready"]:
        scope = " / ".join(x for x in (brand, platform) if x) or "all channels"
        out["prompt_block"] = (
            f"PERFORMANCE INSIGHTS ({scope}, measured from {len(rows)} published posts):\n"
            + "\n".join(f"- {l}" for l in lines)
            + "\nUse these as soft guidance only. Never trade a compliance rule or brand voice for reach."
        )
    else:
        out["prompt_block"] = ""
    return out
