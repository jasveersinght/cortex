"""Orchestration: the two recurring cycles and a side-effect-free pre-flight preview."""
from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime
from typing import Any

from .config import Settings
from .db import get_asset
from .intake import sync_approved
from .media import get_media, to_public_url
from .metrics import collect_metrics
from .performance import score_pending
from .platform_rules import compose_final_text, rule_for
from .preflight import run_preflight
from .providers.base import Provider
from .publisher import publish_due
from .utils import parse_platforms, utcnow


def run_publish_cycle(conn: sqlite3.Connection, provider: Provider, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    """Approved assets -> jobs -> pre-flight -> scheduled."""
    now = now or utcnow()
    intake = sync_approved(conn, settings, now)
    results = publish_due(conn, provider, settings, now=now)
    return {"intake": intake, "results": results}


def run_metrics_cycle(conn: sqlite3.Connection, provider: Provider, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    """Collect engagement -> score with the 4 lenses -> write lessons."""
    now = now or utcnow()
    collected = collect_metrics(conn, provider, settings, now)
    scored = score_pending(conn, settings, now)
    return {"metrics": collected, "performance": scored}


def preview_preflight(conn: sqlite3.Connection, asset_id: Any, platform: str | None, provider: Provider, settings: Settings) -> dict[str, Any]:
    """Run the 4 gates without creating a job or calling any provider."""
    asset = get_asset(conn, asset_id)
    if asset is None:
        raise LookupError(f"asset {asset_id} not found")
    valid, _ = parse_platforms(platform or asset["platform"])
    out: dict[str, Any] = {"asset_id": str(asset_id), "platforms": {}}
    quiet = replace(settings, enrichment_mode="off")
    for p in valid:
        rule = rule_for(p, quiet)
        if rule is None:
            continue
        media_row = get_media(conn, asset_id)
        media_view = None if media_row is None else {
            "media_url": to_public_url(media_row["media_url"], quiet), "media_type": media_row["media_type"]}
        report = run_preflight(conn, asset=asset, job_id=None, platform=p, rule=rule, media=media_view,
                               provider=provider, settings=quiet)
        out["platforms"][p] = report.to_dict()
    return out
