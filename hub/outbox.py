"""Local safety net: a Supabase outage must never lose or block a generation."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from hands.utils import dumps, loads, to_iso, utcnow

from .supabase_rest import SupabaseError, SupabaseRest

SCHEMA = Path(__file__).with_name("hub_schema.sql")


def init_hub_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


def enqueue(conn: sqlite3.Connection, target: str, table: str, on_conflict: str, rows: list[dict[str, Any]], error: str) -> None:
    conn.execute(
        "INSERT INTO hub_outbox (target, table_name, on_conflict, payload_json, attempts, last_error, created_at) VALUES (?,?,?,?,?,?,?)",
        (target, table, on_conflict, dumps(rows), 1, error[:300], to_iso(utcnow())),
    )


def flush(conn: sqlite3.Connection, clients: dict[str, SupabaseRest], limit: int = 100) -> dict[str, int]:
    """Retry queued writes in the order they were created. Stops a target at its first failure to keep order."""
    out = {"sent": 0, "pending": 0}
    blocked: set[str] = set()
    for row in conn.execute("SELECT * FROM hub_outbox ORDER BY id LIMIT ?", (limit,)).fetchall():
        client = clients.get(row["target"])
        if row["target"] in blocked or client is None or not client.enabled:
            out["pending"] += 1
            continue
        try:
            client.upsert(row["table_name"], loads(row["payload_json"], []), row["on_conflict"])
        except SupabaseError as exc:
            conn.execute("UPDATE hub_outbox SET attempts=attempts+1, last_error=? WHERE id=?", (str(exc)[:300], row["id"]))
            blocked.add(row["target"])
            out["pending"] += 1
            continue
        conn.execute("DELETE FROM hub_outbox WHERE id=?", (row["id"],))
        out["sent"] += 1
    return out
