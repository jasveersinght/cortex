"""Store 2: compliance reviews, human decisions and lessons, mirrored to Supabase for the checking agent.

The Brain writes SQLite and is not modified. This module READS that SQLite and upserts into Supabase.
It is idempotent (fingerprints in hub_mirror) and safe to run as often as you like.
"""
from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

from hands.approvals import get_approval
from hands.db import table_exists
from hands.utils import dumps, sha256_text, to_iso, utcnow

from .supabase_rest import SupabaseError, SupabaseRest

BATCH = 50


def _fp(*parts: Any) -> str:
    return hashlib.sha256(dumps(parts).encode()).hexdigest()[:24]


def _mirrored(conn: sqlite3.Connection, kind: str, local_id: str, fingerprint: str) -> bool:
    row = conn.execute("SELECT fingerprint FROM hub_mirror WHERE kind=? AND local_id=?", (kind, local_id)).fetchone()
    return bool(row and row["fingerprint"] == fingerprint)


def _mark(conn: sqlite3.Connection, kind: str, local_id: str, fingerprint: str) -> None:
    conn.execute(
        "INSERT INTO hub_mirror (kind, local_id, fingerprint, synced_at) VALUES (?,?,?,?) "
        "ON CONFLICT(kind, local_id) DO UPDATE SET fingerprint=excluded.fingerprint, synced_at=excluded.synced_at",
        (kind, local_id, fingerprint, to_iso(utcnow())),
    )


def _flush(client: SupabaseRest, table: str, on_conflict: str, pending: list[tuple[dict[str, Any], str, str, str]],
           conn: sqlite3.Connection, counts: dict[str, int], key: str) -> None:
    for i in range(0, len(pending), BATCH):
        chunk = pending[i : i + BATCH]
        try:
            client.upsert(table, [c[0] for c in chunk], on_conflict)
        except SupabaseError as exc:
            counts["errors"] += len(chunk)
            counts["last_error"] = str(exc)[:200]  # type: ignore[assignment]
            continue
        for _, kind, local_id, fp in chunk:
            _mark(conn, kind, local_id, fp)
        counts[key] += len(chunk)


def sync(conn: sqlite3.Connection, client: SupabaseRest) -> dict[str, Any]:
    if not client.enabled:
        return {"skipped": "compliance Supabase is not configured"}
    counts: dict[str, Any] = {"reviews": 0, "decisions": 0, "lessons": 0, "errors": 0}

    lens: dict[str, dict[str, Any]] = {}
    if table_exists(conn, "lens_scores"):
        for r in conn.execute("SELECT * FROM lens_scores"):
            d = dict(r)
            name = d.get("lens_name") or d.get("lens") or d.get("name")
            lens.setdefault(str(d["asset_id"]), {})[str(name)] = {"score": d.get("score"), "reason": d.get("reason")}

    reviews, decisions = [], []
    for a in conn.execute("SELECT * FROM assets WHERE tier IS NOT NULL").fetchall():
        aid = str(a["id"])
        approval = get_approval(conn, aid)
        status = str(a["status"] or "")
        fp = _fp(a["tier"], a["confidence_score"], status, sha256_text(a["body_text"]), lens.get(aid), approval["approved_by"] if approval else None)
        if not _mirrored(conn, "review", aid, fp):
            reviews.append(({
                "brain_asset_id": aid, "brand": a["brand"], "platform": a["platform"], "region": a["region"],
                "content_type": a["content_type"], "body_text": a["body_text"], "body_hash": sha256_text(a["body_text"]),
                "status": status, "tier": a["tier"], "confidence_score": a["confidence_score"],
                "lens_scores": lens.get(aid, {}), "approved_by": approval["approved_by"] if approval else None,
                "approved_at": approval["approved_at"] if approval else None, "synced_at": to_iso(utcnow()),
            }, "review", aid, fp))
        if status in {"approved", "rejected"}:
            dfp = _fp(status, approval["approved_by"] if approval else None)
            local = f"{aid}:{status}"
            if not _mirrored(conn, "decision", local, dfp):
                decisions.append(({
                    "source_key": f"decision:{local}", "brain_asset_id": aid, "brand": a["brand"], "platform": a["platform"],
                    "region": a["region"], "feedback_type": "decision", "decision": status,
                    "reviewer": approval["approved_by"] if approval else None, "reason_tag": None, "note": None,
                    "body_excerpt": (a["body_text"] or "")[:280], "created_at": (approval["approved_at"] if approval else to_iso(utcnow())),
                }, "decision", local, dfp))

    lessons = []
    if table_exists(conn, "lessons_learned"):
        rows = conn.execute(
            "SELECT l.*, a.brand AS a_brand, a.platform AS a_platform, a.region AS a_region, a.body_text AS a_body "
            "FROM lessons_learned l LEFT JOIN assets a ON CAST(a.id AS TEXT)=CAST(l.asset_id AS TEXT)").fetchall()
        for l in rows:
            lid = str(l["id"])
            fp = _fp(l["tag"], l["note"])
            if _mirrored(conn, "lesson", lid, fp):
                continue
            tag = l["tag"] or ""
            lessons.append(({
                "source_key": f"lesson:{lid}", "brain_asset_id": str(l["asset_id"]), "brand": l["a_brand"], "platform": l["a_platform"],
                "region": l["a_region"], "feedback_type": "performance" if tag.startswith("perf:") else "human_lesson",
                "decision": None, "reviewer": None, "reason_tag": tag, "note": l["note"],
                "body_excerpt": (l["a_body"] or "")[:280], "created_at": l["created_at"] or to_iso(utcnow()),
            }, "lesson", lid, fp))

    _flush(client, "compliance_reviews", "brain_asset_id", reviews, conn, counts, "reviews")
    _flush(client, "review_feedback", "source_key", decisions, conn, counts, "decisions")
    _flush(client, "review_feedback", "source_key", lessons, conn, counts, "lessons")
    return counts
