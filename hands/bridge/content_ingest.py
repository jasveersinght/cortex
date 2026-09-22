"""Bridge: Content agent JSON  ->  rows in the Brain's `assets` table (status 'pending').

The content agent (cortex-content-agent) returns structured JSON but does not write to
the database. This adapter is what feeds the Brain, so compliance -> human approval ->
Hands can all run on real content. It is deliberately tolerant about the shape of each
platform block, because that shape is a prompt output and can vary.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..db import insert_dynamic
from ..media import set_media
from ..utils import normalize_platform

DISPLAY = {"linkedin": "LinkedIn", "instagram": "Instagram", "x": "X", "tiktok": "TikTok"}
TEXT_KEYS = ("post", "caption", "text", "body", "content", "message", "tweet", "copy", "description")
COMPOSE_KEYS = ("hook", "body", "cta")
SKIP_KEYS = {"hashtags", "platform", "format", "image_prompt", "visual", "alt_text", "notes", "language", "tone"}
VIDEO_PLATFORMS = {"instagram", "tiktok"}
IMAGE_PLATFORMS = {"instagram", "linkedin", "x"}


def extract_text(block: Any) -> str:
    if block is None:
        return ""
    if isinstance(block, str):
        return block.strip()
    if isinstance(block, list):
        return "\n\n".join(t for t in (extract_text(b) for b in block) if t)
    if isinstance(block, dict):
        composed = [extract_text(block.get(k)) for k in COMPOSE_KEYS]
        if sum(1 for t in composed if t) >= 2:          # hook + body (+ cta) read as one post
            return "\n\n".join(t for t in composed if t)
        for key in TEXT_KEYS:
            text = extract_text(block.get(key))
            if text:
                return text
        if any(composed):
            return "\n\n".join(t for t in composed if t)
        return "\n\n".join(t for k, v in block.items() if k not in SKIP_KEYS for t in [extract_text(v)] if t)
    return str(block).strip()


def ingest_content_output(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    brand: str,
    region: str,
    video_url: str | None = None,
    image_url: str | None = None,
    content_type: str = "caption",
) -> list[dict[str, Any]]:
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    created: list[dict[str, Any]] = []
    for key, block in data.items():
        platform = normalize_platform(key)
        if platform is None:
            continue
        text = extract_text(block)
        if not text:
            continue
        asset_id = insert_dynamic(conn, "assets", {
            "brand": brand,
            "platform": DISPLAY[platform],
            "content_type": content_type,
            "region": region,
            "body_text": text,
            "status": "pending",
        })
        media = None
        if video_url and platform in VIDEO_PLATFORMS:
            media = set_media(conn, asset_id, video_url, "video", ai_generated=True, source="content-agent")
        elif image_url and platform in IMAGE_PLATFORMS:
            media = set_media(conn, asset_id, image_url, "image", ai_generated=True, source="content-agent")
        created.append({"asset_id": str(asset_id), "platform": DISPLAY[platform], "chars": len(text), "media": media["media_type"] if media else None})
    return created
