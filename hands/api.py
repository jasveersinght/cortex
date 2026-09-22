"""FastAPI service for the Hands.   Run:  uvicorn hands.api:app --port 8002"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from . import __version__, audit
from .approvals import record_approval
from .bridge.content_ingest import ingest_content_output
from .config import Settings, get_settings
from .db import connect, get_flag, get_asset, init_schema, set_flag
from .learning import hashtag_leaderboard, insights_for
from .media import set_media
from .pipeline import preview_preflight, run_metrics_cycle, run_publish_cycle
from .providers import Provider, build_provider
from .utils import loads, to_iso, utcnow

log = logging.getLogger("hands.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if get_settings().enable_worker:
        from .worker import build_scheduler

        scheduler = build_scheduler(blocking=False)
        scheduler.start()
        log.info("background worker started inside the API process")
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="JA Assure - The Hands",
    version=__version__,
    description="Publishing extension for the Brain: approved assets -> 4-gate pre-flight -> schedule -> metrics -> performance lenses -> lessons.",
    lifespan=lifespan,
)


def get_conn() -> Iterator[Any]:
    conn = connect()
    init_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_provider() -> Provider:
    try:
        return build_provider(get_settings())
    except ValueError as exc:
        raise HTTPException(500, str(exc)) from exc


def require_key(x_hands_key: str | None = Header(default=None)) -> None:
    expected = get_settings().api_key
    if expected and not hmac.compare_digest(x_hands_key or "", expected):
        raise HTTPException(401, "missing or invalid X-Hands-Key")


# ---------- request models ----------
class ApprovalIn(BaseModel):
    approved_by: str = Field(min_length=1, description="Name or email of the human reviewer")
    note: str | None = None


class MediaIn(BaseModel):
    url: str
    media_type: str | None = Field(default=None, description="image or video (inferred from the URL if omitted)")
    ai_generated: bool = False


class KillSwitchIn(BaseModel):
    on: bool


class IngestIn(BaseModel):
    payload: dict[str, Any] = Field(description="The JSON returned by POST /api/content/generate")
    brand: str
    region: str = "Singapore"
    video_url: str | None = None
    image_url: str | None = None


# ---------- read endpoints ----------
@app.get("/health", tags=["system"])
def health(conn=Depends(get_conn), provider: Provider = Depends(get_provider)) -> dict[str, Any]:
    counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM publish_jobs GROUP BY status")}
    return {
        "status": "ok",
        "version": __version__,
        "kill_switch": get_flag(conn, "kill_switch", "off"),
        "provider": provider.health(),
        "jobs_by_status": counts,
    }


@app.get("/queue", tags=["queue"])
def queue(status: str | None = None, limit: int = Query(50, le=500), conn=Depends(get_conn)) -> list[dict[str, Any]]:
    sql = "SELECT * FROM publish_jobs"
    args: list[Any] = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    rows = []
    for r in conn.execute(sql, args):
        d = dict(r)
        d.pop("preflight_json", None)
        d["hashtags"] = loads(d.pop("hashtags_json", None), [])
        rows.append(d)
    return rows


@app.get("/jobs/{job_id}", tags=["queue"])
def job_detail(job_id: int, conn=Depends(get_conn)) -> dict[str, Any]:
    job = conn.execute("SELECT * FROM publish_jobs WHERE id=?", (job_id,)).fetchone()
    if job is None:
        raise HTTPException(404, "job not found")
    d = dict(job)
    d["preflight"] = loads(d.pop("preflight_json", None))
    d["hashtags"] = loads(d.pop("hashtags_json", None), [])
    d["metrics"] = [dict(r) for r in conn.execute("SELECT * FROM post_metrics WHERE job_id=? ORDER BY id", (job_id,))]
    score = conn.execute("SELECT * FROM performance_scores WHERE job_id=?", (job_id,)).fetchone()
    d["performance"] = None if score is None else {**dict(score), "explain": loads(score["explain_json"])}
    if d["performance"]:
        d["performance"].pop("explain_json", None)
    return d


@app.get("/summary", tags=["insights"])
def summary(conn=Depends(get_conn)) -> dict[str, Any]:
    by_status = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM publish_jobs GROUP BY status")}
    blocked = {r["block_code"] or "other": r["n"] for r in conn.execute(
        "SELECT block_code, COUNT(*) AS n FROM publish_jobs WHERE status='blocked' GROUP BY block_code")}
    tiers = {r["tier"]: r["n"] for r in conn.execute("SELECT tier, COUNT(*) AS n FROM performance_scores GROUP BY tier")}
    by_platform = [dict(r) for r in conn.execute(
        "SELECT j.platform, COUNT(*) AS posts, ROUND(AVG(s.total_score),1) AS avg_score FROM performance_scores s "
        "JOIN publish_jobs j ON j.id=s.job_id GROUP BY j.platform ORDER BY avg_score DESC")]
    return {"jobs_by_status": by_status, "blocked_by_gate": blocked, "performance_tiers": tiers, "avg_score_by_platform": by_platform}


@app.get("/insights", tags=["insights"])
def insights(brand: str | None = None, platform: str | None = None, conn=Depends(get_conn)) -> dict[str, Any]:
    """Measured guidance for the Content agent. `prompt_block` can be pasted straight into a prompt."""
    return insights_for(conn, brand, platform)


@app.get("/insights/hashtags", tags=["insights"])
def hashtags(brand: str | None = None, platform: str | None = None, conn=Depends(get_conn)) -> list[dict[str, Any]]:
    return hashtag_leaderboard(conn, brand, platform, 20)


@app.get("/audit", tags=["system"])
def audit_trail(limit: int = Query(100, le=1000), conn=Depends(get_conn)) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]


@app.get("/killswitch", tags=["safety"])
def killswitch_status(conn=Depends(get_conn)) -> dict[str, str]:
    return {"kill_switch": get_flag(conn, "kill_switch", "off")}


# ---------- actions ----------
@app.post("/approvals/{asset_id}", tags=["approval"], dependencies=[Depends(require_key)])
def approve(asset_id: str, body: ApprovalIn, conn=Depends(get_conn)) -> dict[str, Any]:
    """Record the human approval receipt (who, when, hash of the exact text)."""
    try:
        return record_approval(conn, asset_id, body.approved_by, body.note)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/assets/{asset_id}/media", tags=["approval"], dependencies=[Depends(require_key)])
def attach_media(asset_id: str, body: MediaIn, conn=Depends(get_conn)) -> dict[str, Any]:
    if get_asset(conn, asset_id) is None:
        raise HTTPException(404, "asset not found")
    try:
        return set_media(conn, asset_id, body.url, body.media_type, body.ai_generated, source="api")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/ingest/content-agent", tags=["bridge"], dependencies=[Depends(require_key)])
def ingest(body: IngestIn, conn=Depends(get_conn)) -> dict[str, Any]:
    created = ingest_content_output(conn, body.payload, brand=body.brand, region=body.region,
                                    video_url=body.video_url, image_url=body.image_url)
    return {"created": created, "next": "run the compliance agent on these assets, then have a human approve them"}


@app.post("/preflight/{asset_id}", tags=["queue"])
def preflight(asset_id: str, platform: str | None = None, conn=Depends(get_conn), provider: Provider = Depends(get_provider)) -> dict[str, Any]:
    """Dry-run the 4 gates for an asset. Creates nothing and posts nothing."""
    try:
        return preview_preflight(conn, asset_id, platform, provider, get_settings())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/publish/run", tags=["queue"], dependencies=[Depends(require_key)])
def publish_run(conn=Depends(get_conn), provider: Provider = Depends(get_provider)) -> dict[str, Any]:
    return run_publish_cycle(conn, provider, get_settings())


@app.post("/metrics/run", tags=["insights"], dependencies=[Depends(require_key)])
def metrics_run(conn=Depends(get_conn), provider: Provider = Depends(get_provider)) -> dict[str, Any]:
    return run_metrics_cycle(conn, provider, get_settings())


@app.post("/jobs/{job_id}/retry", tags=["queue"], dependencies=[Depends(require_key)])
def retry(job_id: int, conn=Depends(get_conn)) -> dict[str, Any]:
    """Re-queue a failed / blocked / needs_review job (after you have verified it was NOT posted)."""
    job = conn.execute("SELECT * FROM publish_jobs WHERE id=?", (job_id,)).fetchone()
    if job is None:
        raise HTTPException(404, "job not found")
    if job["status"] not in {"failed", "blocked", "needs_review", "cancelled"}:
        raise HTTPException(409, f"job is '{job['status']}', only failed/blocked/needs_review/cancelled jobs can be retried")
    conn.execute(
        "UPDATE publish_jobs SET status='queued', attempts=0, block_code=NULL, last_error=NULL, next_attempt_at=NULL, "
        "submitted_at=NULL, updated_at=? WHERE id=?", (to_iso(utcnow()), job_id))
    audit.log(conn, "manual_retry", job_id=job_id, asset_id=job["asset_id"])
    return {"job_id": job_id, "status": "queued"}


@app.post("/jobs/{job_id}/cancel", tags=["queue"], dependencies=[Depends(require_key)])
def cancel(job_id: int, conn=Depends(get_conn)) -> dict[str, Any]:
    cur = conn.execute("UPDATE publish_jobs SET status='cancelled', updated_at=? WHERE id=? AND status IN ('queued','retry','blocked','needs_review')",
                       (to_iso(utcnow()), job_id))
    if cur.rowcount == 0:
        raise HTTPException(409, "job not found or already scheduled/published")
    audit.log(conn, "cancelled", job_id=job_id)
    return {"job_id": job_id, "status": "cancelled"}


@app.post("/killswitch", tags=["safety"], dependencies=[Depends(require_key)])
def killswitch(body: KillSwitchIn, conn=Depends(get_conn)) -> dict[str, str]:
    """ON = nothing new gets scheduled until you turn it off."""
    set_flag(conn, "kill_switch", "on" if body.on else "off")
    audit.log(conn, "kill_switch", detail="on" if body.on else "off")
    return {"kill_switch": "on" if body.on else "off"}
