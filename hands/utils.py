"""Small shared helpers: time, hashing, platform names, JSON."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from typing import Any

PLATFORM_ALIASES = {
    "linkedin": "linkedin",
    "linked in": "linkedin",
    "instagram": "instagram",
    "insta": "instagram",
    "ig": "instagram",
    "x": "x",
    "twitter": "x",
    "x (twitter)": "x",
    "x/twitter": "x",
    "tiktok": "tiktok",
    "tik tok": "tiktok",
}
SUPPORTED_PLATFORMS = ("linkedin", "instagram", "x", "tiktok")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Fixed-width UTC timestamp, so plain string comparison sorts correctly."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_platform(value: Any) -> str | None:
    if value is None:
        return None
    return PLATFORM_ALIASES.get(str(value).strip().lower())


def parse_platforms(value: Any) -> tuple[list[str], list[str]]:
    """'LinkedIn, Instagram' -> (['linkedin','instagram'], []). Unknown names are returned separately."""
    valid: list[str] = []
    invalid: list[str] = []
    for part in str(value or "").replace("/", ",").replace(";", ",").replace("|", ",").split(","):
        part = part.strip()
        if not part:
            continue
        norm = normalize_platform(part)
        if norm is None:
            invalid.append(part)
        elif norm not in valid:
            valid.append(norm)
    return valid, invalid


def normalize_text(text: str | None) -> str:
    return unicodedata.normalize("NFC", (text or "").replace("\r\n", "\n")).strip()


def sha256_text(text: str | None) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def loads(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default
