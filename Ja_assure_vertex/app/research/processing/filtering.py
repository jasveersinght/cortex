"""Relevance filtering and source quality classification.

All functions are pure and deterministic — no AI.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.research.enums import Relevance, SourceType
from app.research.models import Evidence
from app.research.processing.normalization import extract_domain

logger = logging.getLogger("ja_assure")


# ── Source Quality Classification ──────────────────────────────────

# Tier 1: Official company sources — populated dynamically from competitors table
# Tier 2: Government / regulator domains
REGULATOR_DOMAINS = {
    # Singapore
    "mas.gov.sg", "mom.gov.sg", "singstat.gov.sg",
    # Malaysia
    "bnm.gov.my", "sc.com.my",
    # Hong Kong
    "sfc.hk", "hkma.gov.hk", "ia.org.hk",
    # Indonesia
    "ojk.go.id", "bi.go.id",
    # Thailand
    "oic.or.th", "bot.or.th", "sec.or.th",
}

# Tier 3: Reputable news
NEWS_DOMAINS = {
    "reuters.com", "bloomberg.com", "cnbc.com", "bbc.com", "bbc.co.uk",
    "ft.com", "wsj.com", "nytimes.com", "theguardian.com",
    "straitstimes.com", "channelnewsasia.com", "todayonline.com",
    "thestar.com.my", "nst.com.my", "scmp.com", "nikkei.com",
    "bangkokpost.com", "nationthailand.com",
    "jakartaglobe.id", "thejakartapost.com",
    "businesstimes.com.sg", "edgeprop.sg",
}

# Tier 4: Industry publications
INDUSTRY_DOMAINS = {
    "insuranceasiafinews.com", "asiainsurancereview.com",
    "insurancebusinessmag.com", "insurancejournal.com",
    "fintechnews.sg", "fintechmagazine.com",
    "techinasia.com", "e27.co", "dealstreetasia.com",
}

# Tier 5: Social sources
SOCIAL_DOMAINS = {
    "twitter.com", "x.com", "linkedin.com", "facebook.com",
    "reddit.com", "instagram.com", "tiktok.com",
    "youtube.com",
}


def classify_source_quality(
    domain: str,
    competitor_domains: set[str] | None = None,
) -> tuple[int, SourceType]:
    """Classify a domain into quality tiers 1–6.

    Returns (tier, source_type).
    """
    domain = domain.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # Tier 1: Official company source
    if competitor_domains and domain in competitor_domains:
        return 1, SourceType.COMPANY_SITE

    # Tier 2: Government / regulator
    if domain in REGULATOR_DOMAINS or ".gov" in domain:
        return 2, SourceType.REGULATOR

    # Tier 3: Reputable news
    if domain in NEWS_DOMAINS:
        return 3, SourceType.NEWS

    # Tier 4: Industry publication
    if domain in INDUSTRY_DOMAINS:
        return 4, SourceType.INDUSTRY

    # Tier 5: Social
    if domain in SOCIAL_DOMAINS:
        return 5, SourceType.SOCIAL

    # Tier 6: Secondary / unknown
    return 6, SourceType.OTHER


# ── Relevance Scoring ─────────────────────────────────────────────

def _token_set(text: str) -> set[str]:
    """Normalize text to a set of lowercase alphanumeric tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score_relevance(
    evidence: Evidence,
    brand: str,
    market: str,
    competitors: list[str],
    topics: list[str],
    objective: str | None,
    lookback_days: int,
) -> float:
    """Compute a relevance score in [0, 1] for a single evidence item.

    Formula (§14):
      0.30 * entity_match
    + 0.20 * market_match
    + 0.20 * objective_overlap
    + 0.15 * source_quality_norm
    + 0.15 * recency_norm
    """
    # Searchable text
    title_lower = (evidence.title or "").lower()
    content_head = (evidence.content or "")[:1000].lower()
    searchable = title_lower + " " + content_head

    # 1. Entity match (0.30) — brand/competitor/topic appears
    entity_terms = [brand.lower()] + [c.lower() for c in competitors] + [t.lower() for t in topics]
    entity_hits = sum(1 for term in entity_terms if term in searchable)
    entity_match = min(1.0, entity_hits / max(1, len(entity_terms)))

    # 2. Market match (0.20)
    market_aliases = {market.lower()}
    if market == "Hong Kong":
        market_aliases.update({"hk", "hong kong"})
    elif market == "Singapore":
        market_aliases.update({"sg", "singapore"})
    elif market == "Malaysia":
        market_aliases.update({"my", "malaysia"})
    elif market == "Indonesia":
        market_aliases.update({"id", "indonesia"})
    elif market == "Thailand":
        market_aliases.update({"th", "thailand"})
    market_match = 1.0 if any(alias in searchable for alias in market_aliases) else 0.0

    # 3. Objective/topic overlap (0.20) — Jaccard on tokens
    if objective or topics:
        objective_text = (objective or "") + " " + " ".join(topics)
        obj_tokens = _token_set(objective_text)
        content_tokens = _token_set(searchable)
        if obj_tokens and content_tokens:
            overlap = len(obj_tokens & content_tokens) / len(obj_tokens | content_tokens)
            objective_overlap = min(1.0, overlap * 3)  # scale up small overlaps
        else:
            objective_overlap = 0.0
    else:
        objective_overlap = 0.0

    # 4. Source quality normalized (0.15) — (7 - tier) / 6
    source_quality_norm = (7 - evidence.source_quality) / 6.0

    # 5. Recency normalized (0.15)
    if evidence.published_at:
        now = datetime.now(timezone.utc)
        days_old = (now - evidence.published_at).total_seconds() / 86400
        recency_norm = max(0.0, 1.0 - (days_old / lookback_days))
    else:
        recency_norm = 0.5  # penalty for missing date

    score = (
        0.30 * entity_match
        + 0.20 * market_match
        + 0.20 * objective_overlap
        + 0.15 * source_quality_norm
        + 0.15 * recency_norm
    )

    return round(score, 3)


def label_relevance(score: float) -> Relevance:
    """Map a relevance score to a tri-state label."""
    if score >= 0.60:
        return Relevance.RELEVANT
    elif score >= 0.35:
        return Relevance.UNCERTAIN
    else:
        return Relevance.IRRELEVANT


def filter_by_date(
    evidence_list: list[Evidence],
    lookback_days: int,
) -> list[Evidence]:
    """Filter out evidence older than the lookback window.

    Evidence without published_at is kept (marked in metadata).
    """
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - (lookback_days * 86400)
    filtered: list[Evidence] = []

    for e in evidence_list:
        if e.published_at and e.published_at.timestamp() < cutoff:
            logger.debug(f"Date filter: dropped id={e.id}, published_at={e.published_at}")
            continue
        if not e.published_at:
            e.metadata["published_date_missing"] = True
        filtered.append(e)

    return filtered


def apply_relevance_scoring(
    evidence_list: list[Evidence],
    brand: str,
    market: str,
    competitors: list[str],
    topics: list[str],
    objective: str | None,
    lookback_days: int,
) -> list[Evidence]:
    """Score and label relevance for all evidence items.

    Nothing is discarded — everything is persisted with its label.
    """
    for e in evidence_list:
        e.relevance_score = score_relevance(
            e, brand, market, competitors, topics, objective, lookback_days
        )
        e.relevance = label_relevance(e.relevance_score)

    return evidence_list
