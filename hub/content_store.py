"""Store 1: everything the content agent generates, saved to Supabase."""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from typing import Any

from hands.utils import sha256_text, to_iso, utcnow

from . import outbox
from .supabase_rest import SupabaseError, SupabaseRest


def save_generation(
    conn: sqlite3.Connection,
    client: SupabaseRest,
    *,
    brand: str,
    region: str,
    request_body: dict[str, Any],
    response: dict[str, Any],
    latency_ms: int,
    items: list[dict[str, Any]],
    parent_generation_id: str | None = None,
    source_url: str = "",
) -> dict[str, Any]:
    """Persist one generation + one row per platform text. Never raises: on failure it queues locally."""
    generation_id = str(uuid.uuid4())
    now = to_iso(utcnow())
    gen_row = {
        "id": generation_id,
        "brand": brand,
        "region": region,
        "request_json": request_body,
        "response_json": response,
        "latency_ms": latency_ms,
        "parent_generation_id": parent_generation_id,
        "source_url": source_url,
        "created_at": now,
    }
    item_rows = [
        {
            "generation_id": generation_id,
            "platform": it["platform"],
            "body_text": it["body_text"],
            "body_hash": sha256_text(it["body_text"]),
            "brand": brand,
            "region": region,
            "brain_asset_id": it.get("asset_id"),
            "media_url": it.get("media_url"),
            "created_at": now,
        }
        for it in items
    ]
    for it in items:
        if it.get("asset_id"):
            conn.execute("INSERT OR IGNORE INTO hub_links (generation_id, asset_id, platform, created_at) VALUES (?,?,?,?)",
                         (generation_id, str(it["asset_id"]), it["platform"], now))

    stored, error = False, None
    try:
        client.upsert("content_generations", [gen_row], "id")
        client.upsert("content_items", item_rows, "generation_id,platform")
        stored = True
    except SupabaseError as exc:
        error = str(exc)
        outbox.enqueue(conn, "content", "content_generations", "id", [gen_row], error)
        outbox.enqueue(conn, "content", "content_items", "generation_id,platform", item_rows, error)
    return {"generation_id": generation_id, "stored_in_supabase": stored, "queued_for_retry": not stored, "error": error}
