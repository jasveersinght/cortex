"""Last-mile claims screen for text that Hands (not a human) adds: hashtags.

The approved body is frozen and was already checked by the Brain's compliance
agent. Anything Hands *adds* must not reintroduce a prohibited claim, so it is
screened here, in English, Malay, Bahasa Indonesia, Thai and Chinese.
"""
from __future__ import annotations

import re

_PATTERNS = [
    # English
    r"guarantee[ds]?", r"100\s?(%|percent|pct)", r"hundred[\s-]?percent", r"risk[\s-]?free", r"no[\s-]?exclusions?", r"always[\s-]?covered",
    r"never[\s-]?denied", r"instant(ly)?[\s-]?(payout|approval|claims?)", r"cheapest", r"unbeatable",
    r"best[\s-]?(insurance|coverage|rates?|cover)", r"number[\s-]?one", r"zero[\s-]?risk",
    r"fully[\s-]?covered", r"covers?[\s-]?everything", r"no[\s-]?questions[\s-]?asked", r"#1\b",
    r"sure[\s-]?payout", r"worry[\s-]?free",
    # Bahasa Melayu / Bahasa Indonesia
    r"dijamin", r"jaminan", r"pasti[\s-]?dibayar", r"tanpa[\s-]?syarat", r"bebas[\s-]?risiko",
    r"terbaik[\s-]?di", r"termurah", r"semua[\s-]?dilindungi",
    # Thai
    r"รับประกัน", r"การันตี", r"ไม่มีข้อยกเว้น", r"ถูกที่สุด",
    # Chinese
    r"保证", r"百分百", r"绝对", r"零风险", r"无条件", r"最便宜", r"最好的保险", r"一定赔", r"保證", r"絕對",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


def violations(text: str | None) -> list[str]:
    """Return the prohibited fragments found in `text` (empty list = clean)."""
    found: list[str] = []
    for pattern in _COMPILED:
        for m in pattern.finditer(text or ""):
            found.append(m.group(0))
    return found


def is_clean(text: str | None) -> bool:
    return not violations(text)
