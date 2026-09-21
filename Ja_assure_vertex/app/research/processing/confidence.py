"""Confidence scoring — transparent, explainable, no ML.

Importance = strategic significance (AI-assigned).
Confidence = strength of supporting evidence (primarily deterministic).
They are always separate.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, timezone

from app.research.models import Evidence, Finding

logger = logging.getLogger("ja_assure")


def score_confidence(
    finding: Finding,
    supporting_evidence: list[Evidence],
    lookback_days: int,
) -> tuple[int, dict]:
    """Compute the blended confidence score for a finding.

    Formula (§20):
      0.30 * source_quality_component     (deterministic)
    + 0.25 * corroboration_component      (deterministic)
    + 0.15 * independence_component       (deterministic)
    + 0.15 * recency_component            (deterministic)
    + 0.15 * ai_confidence_component      (AI-assisted)

    Penalties:
      -15 if conflicts exist
      -10 if all sources are tier 5 or 6
      -10 if all sources lack published_at

    Returns (score, breakdown_dict).
    """
    if not supporting_evidence:
        breakdown = {
            "source_quality": 0, "corroboration": 0,
            "independence": 0, "recency": 0,
            "ai_confidence": 0, "penalties": [],
            "raw_score": 0, "final_score": 0,
        }
        return 0, breakdown

    # ── Component 1: Source quality (best tier among supporting evidence)
    best_tier = min(e.source_quality for e in supporting_evidence)
    source_quality_component = (7 - best_tier) / 6.0

    # ── Component 2: Corroboration (diminishing returns on independent sources)
    n_sources = len(supporting_evidence)
    corroboration_component = min(1.0, math.log2(1 + n_sources) / math.log2(5))

    # ── Component 3: Independence (distinct domains / total)
    from app.research.processing.normalization import extract_domain
    domains = set()
    for e in supporting_evidence:
        domain = extract_domain(e.url)
        if domain:
            domains.add(domain)
    independence_component = len(domains) / max(1, n_sources)

    # ── Component 4: Recency (best among supporting evidence)
    now = datetime.now(timezone.utc)
    dated_evidence = [e for e in supporting_evidence if e.published_at]
    if dated_evidence:
        newest = max(e.published_at for e in dated_evidence)
        days_since = (now - newest).total_seconds() / 86400
        recency_component = max(0.0, 1.0 - (days_since / lookback_days))
    else:
        recency_component = 0.5  # penalty for all-undated

    # ── Component 5: AI confidence (self-report)
    ai_confidence_component = finding.ai_confidence / 100.0

    # ── Blend
    raw_score = (
        0.30 * source_quality_component
        + 0.25 * corroboration_component
        + 0.15 * independence_component
        + 0.15 * recency_component
        + 0.15 * ai_confidence_component
    )

    score = round(100 * raw_score)

    # ── Penalties
    penalties: list[str] = []

    if finding.conflicts:
        score -= 15
        penalties.append("conflicts_present (-15)")

    all_low_quality = all(e.source_quality >= 5 for e in supporting_evidence)
    if all_low_quality:
        score -= 10
        penalties.append("all_sources_low_quality (-10)")

    all_undated = all(e.published_at is None for e in supporting_evidence)
    if all_undated:
        score -= 10
        penalties.append("all_sources_undated (-10)")

    # Floor / ceiling
    score = max(0, min(100, score))

    breakdown = {
        "source_quality": round(source_quality_component, 3),
        "corroboration": round(corroboration_component, 3),
        "independence": round(independence_component, 3),
        "recency": round(recency_component, 3),
        "ai_confidence": round(ai_confidence_component, 3),
        "penalties": penalties,
        "raw_score": round(raw_score, 3),
        "final_score": score,
    }

    return score, breakdown


def compute_finding_relevance_score(
    supporting_evidence: list[Evidence],
) -> int:
    """Compute a finding-level relevance score from its supporting evidence.

    Simple average of evidence relevance scores, scaled to 0–100.
    """
    if not supporting_evidence:
        return 0
    avg = sum(e.relevance_score for e in supporting_evidence) / len(supporting_evidence)
    return round(avg * 100)
