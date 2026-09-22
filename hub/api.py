"""FastAPI Hub service.   Run:  uvicorn hub.api:app --port 8003

This is the ONLY new process. The content agent, research agent and Brain keep running
exactly as they already do; this just calls into them.
"""
from __future__ import annotations

import hmac
import logging
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from hands.db import connect as hands_connect
from hands.db import init_schema as hands_init_schema

from . import compliance_store, outbox
from .brain_adapter import AdapterError, BrainAdapter
from .config import HubSettings, get_hub_settings
from .content_client import ContentClient
from .orchestrator import generate_and_process
from .supabase_rest import SupabaseRest

log = logging.getLogger("hub.api")
app = FastAPI(title="JA Assure Hub", version="1.0.0",
             description="Connects Research + Content + Brain + Hands, and mirrors content/compliance to Supabase.")


def get_conn() -> Iterator[Any]:
    conn = hands_connect()
    hands_init_schema(conn)
    outbox.init_hub_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_settings() -> HubSettings:
    return get_hub_settings()


def get_clients(settings: HubSettings = Depends(get_settings)):
    return {
        "content": ContentClient(settings.content_agent_url),
        "content_sb": SupabaseRest(settings.supabase_content_url, settings.supabase_content_key),
        "compliance_sb": SupabaseRest(settings.supabase_compliance_url, settings.supabase_compliance_key),
    }


def require_key(x_hub_key: str | None = Header(default=None), settings: HubSettings = Depends(get_settings)) -> None:
    if settings.hub_api_key and not hmac.compare_digest(x_hub_key or "", settings.hub_api_key):
        raise HTTPException(401, "missing or invalid X-Hub-Key")


class GenerateIn(BaseModel):
    request: dict[str, Any] = Field(description="Passed to the content agent's /api/content/generate exactly as given")
    brand: str
    region: str = "Singapore"
    video_url: str | None = None
    image_url: str | None = None
    run_compliance: bool = True


class DecisionIn(BaseModel):
    decision: str = Field(description="approved | rejected | edited")
    reviewer: str
    tag: str | None = None
    note: str | None = None
    edited_text: str | None = None


@app.get("/health")
def health(settings: HubSettings = Depends(get_settings), clients=Depends(get_clients)) -> dict[str, Any]:
    return {
        "status": "ok",
        "content_agent_reachable": clients["content"].reachable(),
        "content_supabase_configured": clients["content_sb"].enabled,
        "compliance_supabase_configured": clients["compliance_sb"].enabled,
        "brain_compliance_func": settings.brain_compliance_func or "(not configured)",
    }


@app.post("/generate", dependencies=[Depends(require_key)])
def generate(body: GenerateIn, conn=Depends(get_conn), settings: HubSettings = Depends(get_settings), clients=Depends(get_clients)) -> dict[str, Any]:
    """generate -> store to Supabase -> create pending Brain assets -> run compliance -> mirror to Supabase."""
    return generate_and_process(conn, settings, clients["content"], clients["content_sb"], clients["compliance_sb"],
                                request_body=body.request, brand=body.brand, region=body.region,
                                video_url=body.video_url, image_url=body.image_url, run_compliance=body.run_compliance)


@app.post("/assets/{asset_id}/compliance", dependencies=[Depends(require_key)])
def run_compliance(asset_id: str, conn=Depends(get_conn), settings: HubSettings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return BrainAdapter(settings).run_compliance(conn, asset_id)
    except AdapterError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/assets/{asset_id}/decision", dependencies=[Depends(require_key)])
def record_decision(asset_id: str, body: DecisionIn, conn=Depends(get_conn), settings: HubSettings = Depends(get_settings)) -> dict[str, Any]:
    try:
        return BrainAdapter(settings).record_decision(conn, asset_id, body.decision, body.reviewer, body.tag, body.note, body.edited_text)
    except AdapterError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/sync/compliance", dependencies=[Depends(require_key)])
def sync_compliance(conn=Depends(get_conn), clients=Depends(get_clients)) -> dict[str, Any]:
    """Mirror every review/decision/lesson currently in SQLite to Supabase store 2."""
    return compliance_store.sync(conn, clients["compliance_sb"])


@app.post("/sync/outbox", dependencies=[Depends(require_key)])
def sync_outbox(conn=Depends(get_conn), clients=Depends(get_clients)) -> dict[str, Any]:
    """Retry any writes that failed earlier because Supabase was unreachable."""
    return outbox.flush(conn, {"content": clients["content_sb"], "compliance": clients["compliance_sb"]})
