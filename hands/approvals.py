"""The human-approval receipt.

Brain sets `assets.status = 'approved'`, but a status column is only a claim.
Hands additionally requires an approval *record*: who approved, when, and a hash
of the exact text they approved. Anything edited afterwards no longer matches.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from . import audit
from .db import get_asset
from .utils import sha256_text, to_iso, utcnow


def record_approval(
    conn: sqlite3.Connection,
    asset_id: Any,
    approved_by: str,
    note: str | None = None,
    source: str = "reviewer",
    set_status: bool = False,
) -> dict[str, Any]:
    """Call this from the Brain's review step the moment a human clicks Approve."""
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by is required: approvals must be attributable to a person")
    asset = get_asset(conn, asset_id)
    if asset is None:
        raise LookupError(f"asset {asset_id} not found")
    rec = {
        "asset_id": str(asset_id),
        "approved_by": approved_by.strip(),
        "approved_at": to_iso(utcnow()),
        "body_hash": sha256_text(asset["body_text"]),
        "note": note,
        "source": source,
    }
    conn.execute(
        "INSERT INTO approval_records (asset_id, approved_by, approved_at, body_hash, note, source) "
        "VALUES (:asset_id, :approved_by, :approved_at, :body_hash, :note, :source) "
        "ON CONFLICT(asset_id) DO UPDATE SET approved_by=excluded.approved_by, approved_at=excluded.approved_at, "
        "body_hash=excluded.body_hash, note=excluded.note, source=excluded.source",
        rec,
    )
    if set_status:
        conn.execute("UPDATE assets SET status='approved' WHERE CAST(id AS TEXT)=?", (str(asset_id),))
    audit.log(conn, "approval_recorded", actor=approved_by, asset_id=asset_id, detail={"hash": rec["body_hash"][:12], "source": source})
    return rec


def get_approval(conn: sqlite3.Connection, asset_id: Any) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM approval_records WHERE asset_id=?", (str(asset_id),)).fetchone()


def adopt_existing_approved(conn: sqlite3.Connection, approved_by: str) -> list[str]:
    """One-time migration: create records for assets already marked approved by the Brain UI.

    Only run this if a human really approved them. It snapshots the CURRENT text.
    """
    adopted: list[str] = []
    rows = conn.execute("SELECT id FROM assets WHERE lower(status)='approved'").fetchall()
    for row in rows:
        if get_approval(conn, row["id"]) is None:
            record_approval(conn, row["id"], approved_by, note="adopted from existing approved status", source="adopted")
            adopted.append(str(row["id"]))
    return adopted
