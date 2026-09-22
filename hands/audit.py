"""Append-only audit trail: every decision Hands makes is recorded."""
from __future__ import annotations

import sqlite3
from typing import Any

from .utils import dumps, to_iso, utcnow


def log(
    conn: sqlite3.Connection,
    event: str,
    *,
    actor: str = "hands",
    job_id: int | None = None,
    asset_id: Any = None,
    detail: Any = None,
) -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, actor, event, job_id, asset_id, detail) VALUES (?,?,?,?,?,?)",
        (to_iso(utcnow()), actor, event, job_id, None if asset_id is None else str(asset_id), dumps(detail) if detail is not None else None),
    )
