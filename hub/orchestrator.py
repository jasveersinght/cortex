"""Wires the three agents together for one generation, without changing any of them.

    Content agent (HTTP, untouched)
          |  raw JSON response
          v
    content_store.save_generation()   -> Supabase store 1 (content_generations, content_items)
          |
          v
    hands.bridge.content_ingest       -> Brain's `assets` table, status='pending'  (Hands code, unmodified)
          |
          v
    BrainAdapter.run_compliance()     -> imports the Brain's own compliance function, per asset
          |
          v
    compliance_store.sync()           -> Supabase store 2 (compliance_reviews, review_feedback)
"""
from __future__ import annotations

import sqlite3
from typing import Any

from hands.bridge.content_ingest import ingest_content_output

from . import compliance_store, content_store
from .brain_adapter import AdapterError, BrainAdapter
from .config import HubSettings
from .content_client import ContentAgentError, ContentClient
from .supabase_rest import SupabaseRest


def generate_and_process(
    conn: sqlite3.Connection,
    settings: HubSettings,
    content_client: ContentClient,
    content_supabase: SupabaseRest,
    compliance_supabase: SupabaseRest,
    *,
    request_body: dict[str, Any],
    brand: str,
    region: str = "Singapore",
    video_url: str | None = None,
    image_url: str | None = None,
    run_compliance: bool = True,
) -> dict[str, Any]:
    if settings.content_context_field:
        insights = _latest_insights(conn, brand)
        if insights:
            request_body = {**request_body, settings.content_context_field: insights}

    try:
        response, latency_ms = content_client.generate(request_body)
    except ContentAgentError as exc:
        return {"stage": "content_agent", "ok": False, "error": str(exc)}

    created = ingest_content_output(conn, response, brand=brand, region=region, video_url=video_url, image_url=image_url)
    items = [{"platform": c["platform"], "body_text": _asset_text(conn, c["asset_id"]), "asset_id": c["asset_id"],
             "media_url": video_url or image_url} for c in created]
    store_result = content_store.save_generation(conn, content_supabase, brand=brand, region=region,
                                                  request_body=request_body, response=response, latency_ms=latency_ms, items=items)

    compliance_results: list[dict[str, Any]] = []
    if run_compliance and settings.brain_compliance_func:
        adapter = BrainAdapter(settings)
        for c in created:
            try:
                compliance_results.append({"platform": c["platform"], **adapter.run_compliance(conn, c["asset_id"])})
            except AdapterError as exc:
                compliance_results.append({"platform": c["platform"], "asset_id": c["asset_id"], "error": str(exc)})
        compliance_store.sync(conn, compliance_supabase)

    return {"stage": "done", "ok": True, "generation_id": store_result["generation_id"],
            "stored_in_supabase": store_result["stored_in_supabase"], "assets_created": created,
            "compliance": compliance_results}


def _asset_text(conn: sqlite3.Connection, asset_id: Any) -> str:
    row = conn.execute("SELECT body_text FROM assets WHERE CAST(id AS TEXT)=?", (str(asset_id),)).fetchone()
    return row["body_text"] if row else ""


def _latest_insights(conn: sqlite3.Connection, brand: str) -> str:
    try:
        from hands.learning import insights_for
    except ImportError:
        return ""
    return insights_for(conn, brand, None).get("prompt_block", "")
