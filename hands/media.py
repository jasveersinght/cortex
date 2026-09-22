"""Media handling. Providers need a PUBLIC url; localhost links will not work."""
from __future__ import annotations

import ipaddress
import sqlite3
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .utils import to_iso, utcnow

_VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")


def infer_media_type(url: str) -> str | None:
    path = urlparse(url).path.lower()
    if path.endswith(_VIDEO_EXT):
        return "video"
    if path.endswith(_IMAGE_EXT):
        return "image"
    return None


def is_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "0.0.0.0"} or host.endswith((".local", ".internal", ".lan")):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)


def to_public_url(url: str, settings: Settings) -> str:
    """Rewrite the content agent's local URL to the tunnel / CDN base URL when configured."""
    base = settings.public_media_base_url
    if not base:
        return url
    local = settings.content_agent_base_url
    if url.startswith(local):
        return base + url[len(local):]
    if url.startswith("/"):
        return base + url
    return url


def set_media(
    conn: sqlite3.Connection,
    asset_id: Any,
    url: str,
    media_type: str | None = None,
    ai_generated: bool = False,
    source: str | None = None,
) -> dict[str, Any]:
    mtype = media_type or infer_media_type(url)
    if mtype not in {"image", "video"}:
        raise ValueError("media_type must be 'image' or 'video' (could not infer it from the URL)")
    conn.execute(
        "INSERT INTO asset_media (asset_id, media_url, media_type, ai_generated, source, created_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(asset_id) DO UPDATE SET media_url=excluded.media_url, media_type=excluded.media_type, "
        "ai_generated=excluded.ai_generated, source=excluded.source",
        (str(asset_id), url, mtype, int(ai_generated), source, to_iso(utcnow())),
    )
    return {"asset_id": str(asset_id), "media_url": url, "media_type": mtype, "ai_generated": ai_generated}


def get_media(conn: sqlite3.Connection, asset_id: Any) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM asset_media WHERE asset_id=?", (str(asset_id),)).fetchone()
