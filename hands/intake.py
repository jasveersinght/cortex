"""Intake: turn approved assets into publish jobs (one job per asset + platform)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from . import audit
from .config import Settings
from .db import tx
from .platform_rules import rule_for
from .preflight import gate_approval, gate_integrity
from .timing import choose_slot
from .utils import parse_platforms, to_iso, utcnow

REQUEUE_CODES = ("approval", "integrity")


def _insert_job(conn: sqlite3.Connection, asset: sqlite3.Row, platform: str, settings: Settings, now: datetime) -> int:
    slot, reason = choose_slot(conn, platform, asset["region"], settings, now)
    cur = conn.execute(
        "INSERT INTO publish_jobs (asset_id, platform, brand, region, status, scheduled_for, slot_reason, max_attempts, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (str(asset["id"]), platform, asset["brand"], asset["region"], "queued", to_iso(slot), reason, settings.max_attempts, to_iso(now), to_iso(now)),
    )
    return int(cur.lastrowid)


def sync_approved(conn: sqlite3.Connection, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    """Create jobs for approved assets that have none, and revive jobs blocked only because of a stale approval."""
    now = now or utcnow()
    out: dict[str, Any] = {"created": [], "requeued": [], "unsupported": []}
    assets = conn.execute("SELECT * FROM assets WHERE lower(status)='approved'").fetchall()
    for asset in assets:
        valid, invalid = parse_platforms(asset["platform"])
        with tx(conn):
            for platform in valid:
                if rule_for(platform, settings) is None:
                    continue
                existing = conn.execute(
                    "SELECT * FROM publish_jobs WHERE asset_id=? AND platform=?", (str(asset["id"]), platform)
                ).fetchone()
                if existing is None:
                    job_id = _insert_job(conn, asset, platform, settings, now)
                    audit.log(conn, "job_created", job_id=job_id, asset_id=asset["id"], detail={"platform": platform})
                    out["created"].append(job_id)
                elif existing["status"] == "blocked" and existing["block_code"] in REQUEUE_CODES:
                    if gate_approval(conn, asset, settings).passed and gate_integrity(conn, asset).passed:
                        conn.execute(
                            "UPDATE publish_jobs SET status='queued', block_code=NULL, last_error=NULL, next_attempt_at=NULL, updated_at=? WHERE id=?",
                            (to_iso(now), existing["id"]),
                        )
                        audit.log(conn, "job_requeued_after_reapproval", job_id=existing["id"], asset_id=asset["id"])
                        out["requeued"].append(existing["id"])
            for bad in invalid:
                name = bad.lower()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO publish_jobs (asset_id, platform, brand, region, status, block_code, last_error, max_attempts, created_at, updated_at) "
                    "VALUES (?,?,?,?,'blocked','platform_fit',?,?,?,?)",
                    (str(asset["id"]), name, asset["brand"], asset["region"], f"unsupported platform '{bad}'", settings.max_attempts, to_iso(now), to_iso(now)),
                )
                if cur.rowcount:
                    audit.log(conn, "unsupported_platform", job_id=cur.lastrowid, asset_id=asset["id"], detail={"platform": bad})
                    out["unsupported"].append(bad)
    return out
