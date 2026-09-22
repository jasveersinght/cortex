"""Per-platform limits and *exact* length counting.

Buffer counts UTF-16 code units (emoji = 2), LinkedIn counts every URL as 24,
Instagram counts every line break as 2, and X uses a weighted count where URLs
are 23 and CJK characters / emoji weigh 2. Counting like the platform does is
what stops a post that "looks short enough" from being rejected at send time.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .config import Settings

URL_RE = re.compile(r"https?://\S+")

# X weighs these code point ranges as 1, everything else as 2.
_X_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))


@dataclass(frozen=True)
class PlatformRule:
    name: str
    limit: int
    media: str               # optional | required | video_required
    max_hashtags: int
    hashtag_placement: str   # inline | first_comment
    counting: str            # utf16 | linkedin | instagram | x
    first_comment_limit: int = 0


def rule_for(platform: str, settings: Settings) -> PlatformRule | None:
    rules = {
        "linkedin": PlatformRule("linkedin", 3000, "optional", 5, "inline", "linkedin", 1250),
        "instagram": PlatformRule("instagram", 2196, "required", 10, "first_comment", "instagram", 2200),
        "x": PlatformRule("x", settings.x_char_limit, "optional", 2, "inline", "x"),
        "tiktok": PlatformRule("tiktok", 2200, "video_required", 5, "inline", "utf16"),
    }
    return rules.get(platform)


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _x_weight(ch: str) -> int:
    cp = ord(ch)
    return 1 if any(lo <= cp <= hi for lo, hi in _X_LIGHT_RANGES) else 2


def _x_len(text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    total, pos = 0, 0
    for m in URL_RE.finditer(text):
        total += sum(_x_weight(c) for c in text[pos : m.start()]) + 23
        pos = m.end()
    return total + sum(_x_weight(c) for c in text[pos:])


def count_length(text: str, rule: PlatformRule) -> int:
    if rule.counting == "x":
        return _x_len(text)
    if rule.counting == "linkedin":
        return utf16_len(URL_RE.sub("x" * 24, text))
    if rule.counting == "instagram":
        return utf16_len(text) + text.count("\n")  # each line break counts 2
    return utf16_len(text)


def compose_final_text(body: str, hashtags: list[str], rule: PlatformRule) -> tuple[str, str | None, list[str]]:
    """Attach hashtags WITHOUT ever touching the approved body.

    Returns (final_text, first_comment, hashtags_actually_used). Hashtags that do
    not fit are dropped, never the body.
    """
    tags = list(hashtags)[: rule.max_hashtags]
    if not tags:
        return body, None, []

    if rule.hashtag_placement == "first_comment":
        used: list[str] = []
        for tag in tags:
            candidate = " ".join(used + [tag])
            if count_length(candidate, rule) <= rule.first_comment_limit:
                used.append(tag)
        return body, (" ".join(used) or None), used

    used = []
    for tag in tags:
        candidate = body + "\n\n" + " ".join(used + [tag])
        if count_length(candidate, rule) <= rule.limit:
            used.append(tag)
        else:
            break
    if not used:
        return body, None, []
    return body + "\n\n" + " ".join(used), None, used
