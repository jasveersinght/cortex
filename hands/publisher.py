"""The publishing engine: claim -> pre-flight -> enrich -> schedule -> record.

Safety properties:
* A job is claimed with one atomic UPDATE, so two workers can never take the same job.
* `submitted_at` is written BEFORE the provider call. If the process dies mid-call we
  know the provider may have accepted it, so we never blindly re-post (needs_review).
* Nothing that fails a gate ever reaches the provider.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

from . import audit
from .config import Settings
from .db import get_asset
from .enrichment import enrich
from .media import get_media, to_public_url
from .platform_rules import compose_final_text, rule_for
from .preflight import run_preflight
from .providers.base import (
    PermanentProviderError,
    PostPayload,
    Provider,
    TransientProviderError,
)
from .timing import choose_slot
from .utils import dumps, loads, parse_iso, sha256_text, to_iso, utcnow


def _get(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM publish_jobs WHERE id=?", (job_id,)).fetchone()


def _update(conn: sqlite3.Connection, job_id: int, **fields: Any) -> None:
    fields["updated_at"] = to_iso(utcnow())
    names = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE publish_jobs SET {names} WHERE id=?", (*fields.values(), job_id))


def claim(conn: sqlite3.Connection, job_id: int, now: datetime) -> bool:
    cur = conn.execute(
        "UPDATE publish_jobs SET status='publishing', updated_at=? WHERE id=? AND status IN ('queued','retry')",
        (to_iso(now), job_id),
    )
    return cur.rowcount == 1


def recover_stale(conn: sqlite3.Connection, settings: Settings, now: datetime) -> int:
    """A job stuck in 'publishing' means a worker died. Requeue only if the provider was never called."""
    cutoff = to_iso(now - timedelta(minutes=settings.stale_publishing_minutes))
    fixed = 0
    for row in conn.execute("SELECT id, asset_id, submitted_at FROM publish_jobs WHERE status='publishing' AND updated_at < ?", (cutoff,)).fetchall():
        if row["submitted_at"] is None:
            _update(conn, row["id"], status="queued", last_error="recovered after worker crash (provider was never called)")
            audit.log(conn, "job_recovered", job_id=row["id"], asset_id=row["asset_id"])
        else:
            _update(conn, row["id"], status="needs_review",
                    last_error="worker died after contacting the provider; check the provider dashboard, then use retry if it was not posted")
            audit.log(conn, "job_needs_review", job_id=row["id"], asset_id=row["asset_id"], detail="stale after submit")
        fixed += 1
    return fixed


def process_job(conn: sqlite3.Connection, job_id: int, provider: Provider, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    job = _get(conn, job_id)
    asset = get_asset(conn, job["asset_id"])
    if asset is None:
        _update(conn, job_id, status="blocked", block_code="approval", last_error="asset no longer exists")
        audit.log(conn, "blocked", job_id=job_id, detail="asset missing")
        return {"job_id": job_id, "status": "blocked", "detail": "asset missing"}

    platform = job["platform"]
    rule = rule_for(platform, settings)
    if rule is None:
        _update(conn, job_id, status="blocked", block_code="platform_fit", last_error=f"unsupported platform '{platform}'")
        return {"job_id": job_id, "status": "blocked", "detail": "unsupported platform"}

    # media (rewrite the content agent's local URL to a public one)
    media_row = get_media(conn, job["asset_id"])
    media_view = None
    if media_row is not None:
        media_view = {"media_url": to_public_url(media_row["media_url"], settings), "media_type": media_row["media_type"],
                      "ai_generated": bool(media_row["ai_generated"])}

    # enrichment: hashtags only, cached on the job so retries are identical
    if job["hashtags_json"] is None:
        en = enrich(conn, asset, platform, rule, settings)
        _update(conn, job_id, hashtags_json=dumps(en.hashtags))
        if en.dropped:
            audit.log(conn, "hashtags_dropped_by_claims_screen", job_id=job_id, asset_id=asset["id"], detail=en.dropped)
        job = _get(conn, job_id)
    hashtags = loads(job["hashtags_json"], []) or []
    body = asset["body_text"] or ""
    final_text, first_comment, used = compose_final_text(body, hashtags, rule)

    report = run_preflight(conn, asset=asset, job_id=job_id, platform=platform, rule=rule, media=media_view,
                           provider=provider, settings=settings, now=now)
    _update(conn, job_id, preflight_json=dumps(report.to_dict()))

    if report.action == "block":
        _update(conn, job_id, status="blocked", block_code=report.block_code, last_error=report.summary())
        audit.log(conn, "blocked", job_id=job_id, asset_id=asset["id"], detail=report.summary())
        if report.block_code == "integrity" and settings.revert_tampered_to_pending:
            conn.execute("UPDATE assets SET status='pending' WHERE CAST(id AS TEXT)=?", (str(asset["id"]),))
            audit.log(conn, "asset_returned_to_review", asset_id=asset["id"], detail="edited after approval")
        return {"job_id": job_id, "status": "blocked", "detail": report.summary()}

    if report.action == "defer":
        _update(conn, job_id, status="queued", next_attempt_at=to_iso(report.retry_after or now + timedelta(minutes=15)), last_error=report.summary())
        audit.log(conn, "deferred", job_id=job_id, asset_id=asset["id"], detail=report.summary())
        return {"job_id": job_id, "status": "deferred", "detail": report.summary()}

    # schedule time must be in the future
    scheduled_for = parse_iso(job["scheduled_for"]) if job["scheduled_for"] else now
    slot_reason = job["slot_reason"]
    if scheduled_for <= now + timedelta(seconds=5):
        scheduled_for, slot_reason = choose_slot(conn, platform, job["region"], settings, now)

    body_hash = sha256_text(body)
    attempts = job["attempts"] + 1
    _update(conn, job_id, submitted_at=to_iso(now), attempts=attempts, final_text=final_text, first_comment=first_comment,
            hashtags_json=dumps(used), scheduled_for=to_iso(scheduled_for), slot_reason=slot_reason, provider=provider.name,
            body_hash=body_hash, last_error=None, next_attempt_at=None)

    payload = PostPayload(
        text=final_text, platform=platform, brand=asset["brand"], scheduled_for=scheduled_for,
        media_url=media_view["media_url"] if media_view else None,
        media_type=media_view["media_type"] if media_view else None,
        first_comment=first_comment,
        ai_generated=bool(settings.ai_disclosure and media_view and media_view["ai_generated"]),
        idempotency_key=f"hands-{job_id}-{body_hash[:8]}",
    )

    try:
        result = provider.schedule_post(payload)
    except TransientProviderError as exc:
        if exc.ambiguous:
            msg = f"uncertain outcome ({exc}). Check the provider dashboard, then POST /jobs/{job_id}/retry if it was not posted"
            _update(conn, job_id, status="needs_review", last_error=msg)
            audit.log(conn, "needs_review", job_id=job_id, asset_id=asset["id"], detail=str(exc))
            return {"job_id": job_id, "status": "needs_review", "detail": msg}
        if attempts >= job["max_attempts"]:
            _update(conn, job_id, status="failed", last_error=f"gave up after {attempts} attempts: {exc}", submitted_at=None)
            audit.log(conn, "failed", job_id=job_id, asset_id=asset["id"], detail=str(exc))
            return {"job_id": job_id, "status": "failed", "detail": str(exc)}
        backoff = max(settings.backoff_base_seconds * 2 ** (attempts - 1), exc.retry_after or 0)
        _update(conn, job_id, status="retry", next_attempt_at=to_iso(now + timedelta(seconds=backoff)), last_error=str(exc), submitted_at=None)
        audit.log(conn, "retry_scheduled", job_id=job_id, asset_id=asset["id"], detail={"attempt": attempts, "in_seconds": backoff})
        return {"job_id": job_id, "status": "retry", "detail": str(exc)}
    except PermanentProviderError as exc:
        _update(conn, job_id, status="failed", last_error=str(exc))
        audit.log(conn, "failed", job_id=job_id, asset_id=asset["id"], detail=str(exc))
        return {"job_id": job_id, "status": "failed", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - unknown state: do not risk a duplicate post
        msg = f"unexpected error after contacting provider ({type(exc).__name__}: {exc}); verify before retrying"
        _update(conn, job_id, status="needs_review", last_error=msg)
        audit.log(conn, "needs_review", job_id=job_id, asset_id=asset["id"], detail=msg)
        return {"job_id": job_id, "status": "needs_review", "detail": msg}

    _update(conn, job_id, status="scheduled", external_post_id=result.post_id, external_url=result.url, last_error=None)
    audit.log(conn, "scheduled", job_id=job_id, asset_id=asset["id"], detail={"post_id": result.post_id, "for": to_iso(scheduled_for), "provider": provider.name})
    return {"job_id": job_id, "status": "scheduled", "detail": result.post_id}


def publish_due(conn: sqlite3.Connection, provider: Provider, settings: Settings, limit: int = 20, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or utcnow()
    recover_stale(conn, settings, now)
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM publish_jobs WHERE status IN ('queued','retry') AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
            "ORDER BY COALESCE(scheduled_for, created_at) LIMIT ?",
            (to_iso(now), limit),
        )
    ]
    results: list[dict[str, Any]] = []
    for job_id in ids:
        if claim(conn, job_id, now):
            results.append(process_job(conn, job_id, provider, settings, now))
    return results
