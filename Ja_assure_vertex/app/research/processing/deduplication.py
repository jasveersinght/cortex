"""Deduplication of evidence items.

All functions are pure and deterministic.
Applied in order: URL dedup → content dedup → source-level dedup.
Keeps the highest-quality survivor.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.research.models import Evidence

logger = logging.getLogger("ja_assure")


def _survivor_key(e: Evidence) -> tuple:
    """Sort key for survivor preference:
    lowest quality number (best), then longest content, then most recent.
    """
    published_ts = 0
    if e.published_at:
        published_ts = e.published_at.timestamp()
    return (e.source_quality, -len(e.content), -published_ts)


def _jaccard_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity on normalized titles."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def deduplicate(evidence: list[Evidence]) -> tuple[list[Evidence], dict]:
    """Deduplicate evidence items.

    Returns (survivors, stats).
    Stats: {"by_url": int, "by_content": int, "by_source": int, "total_removed": int}
    """
    stats = {"by_url": 0, "by_content": 0, "by_source": 0, "total_removed": 0}

    if not evidence:
        return [], stats

    # Sort by survivor preference so dedup is order-independent
    sorted_evidence = sorted(evidence, key=_survivor_key)

    # 1. Exact URL dedup — identical url_hash
    url_groups: dict[str, list[Evidence]] = defaultdict(list)
    for e in sorted_evidence:
        url_groups[e.url_hash].append(e)

    after_url: list[Evidence] = []
    for url_hash, group in url_groups.items():
        after_url.append(group[0])  # keep best survivor
        removed = len(group) - 1
        stats["by_url"] += removed
        if removed > 0:
            for dup in group[1:]:
                logger.debug(
                    f"Dedup: URL duplicate removed id={dup.id}, "
                    f"survivor={group[0].id}, url_hash={url_hash}"
                )

    # 2. Exact content dedup — identical content_hash across different URLs
    content_groups: dict[str, list[Evidence]] = defaultdict(list)
    for e in after_url:
        content_groups[e.content_hash].append(e)

    after_content: list[Evidence] = []
    for content_hash, group in content_groups.items():
        after_content.append(group[0])
        removed = len(group) - 1
        stats["by_content"] += removed
        if removed > 0:
            for dup in group[1:]:
                logger.debug(
                    f"Dedup: content duplicate removed id={dup.id}, "
                    f"survivor={group[0].id}, content_hash={content_hash}"
                )

    # 3. Source-level dedup — same domain + same published_at date + title similarity ≥ 0.85
    domain_date_groups: dict[str, list[Evidence]] = defaultdict(list)
    for e in after_content:
        from app.research.processing.normalization import extract_domain
        domain = extract_domain(e.url)
        pub_date = e.published_at.date().isoformat() if e.published_at else "unknown"
        key = f"{domain}:{pub_date}"
        domain_date_groups[key].append(e)

    after_source: list[Evidence] = []
    for key, group in domain_date_groups.items():
        if len(group) <= 1:
            after_source.extend(group)
            continue

        # Within each domain+date group, check title similarity
        kept: list[Evidence] = [group[0]]
        for candidate in group[1:]:
            is_dup = False
            for survivor in kept:
                if (
                    candidate.title
                    and survivor.title
                    and _jaccard_similarity(candidate.title, survivor.title) >= 0.85
                ):
                    is_dup = True
                    stats["by_source"] += 1
                    logger.debug(
                        f"Dedup: source duplicate removed id={candidate.id}, "
                        f"survivor={survivor.id}, key={key}"
                    )
                    break
            if not is_dup:
                kept.append(candidate)
        after_source.extend(kept)

    stats["total_removed"] = stats["by_url"] + stats["by_content"] + stats["by_source"]

    return after_source, stats
