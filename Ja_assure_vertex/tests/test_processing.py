"""Tests for deduplication, filtering, change detection, and confidence scoring."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.research.enums import ChangeStatus, FindingType, Relevance, SourceType
from app.research.models import Conflict, Evidence, Finding
from app.research.processing.deduplication import deduplicate
from app.research.processing.filtering import (
    classify_source_quality, score_relevance, label_relevance, filter_by_date,
)
from app.research.processing.change_detection import (
    detect_evidence_changes, compute_finding_identity_key,
    derive_finding_change_status, all_evidence_unchanged,
)
from app.research.processing.confidence import score_confidence, compute_finding_relevance_score


# ── Helpers ───────────────────────────────────────────────────────

_DEFAULT_PUB_DATE = object()


def _make_evidence(
    id: str = "e_001",
    url: str | None = None,
    url_hash: str = "hash_a",
    content_hash: str = "chash_a",
    source_quality: int = 3,
    title: str | None = None,
    content: str = "Test content about competitors in Singapore",
    published_at: datetime | None | object = _DEFAULT_PUB_DATE,
    relevance: Relevance = Relevance.RELEVANT,
    relevance_score: float = 0.7,
    change_status: ChangeStatus = ChangeStatus.NEW,
) -> Evidence:
    actual_pub = datetime.now(timezone.utc) if published_at is _DEFAULT_PUB_DATE else published_at
    actual_url = url if url is not None else f"https://example.com/{id}"
    actual_title = title if title is not None else f"Test Article {id}"
    return Evidence(
        id=id,
        url=actual_url,
        url_hash=url_hash,
        content_hash=content_hash,
        source_type=SourceType.NEWS,
        source_name="example.com",
        source_quality=source_quality,
        title=actual_title,
        content=content,
        published_at=actual_pub,
        retrieved_at=datetime.now(timezone.utc),
        market="Singapore",
        relevance=relevance,
        relevance_score=relevance_score,
        change_status=change_status,
    )


# ── Deduplication ─────────────────────────────────────────────────

class TestDeduplication:

    def test_url_dedup(self):
        e1 = _make_evidence(id="e1", url_hash="same", content_hash="c1", source_quality=3)
        e2 = _make_evidence(id="e2", url_hash="same", content_hash="c2", source_quality=5)
        result, stats = deduplicate([e1, e2])
        assert len(result) == 1
        assert stats["by_url"] == 1
        assert result[0].source_quality == 3  # Better quality survives

    def test_content_dedup(self):
        e1 = _make_evidence(id="e1", url_hash="u1", content_hash="same", source_quality=2)
        e2 = _make_evidence(id="e2", url_hash="u2", content_hash="same", source_quality=4)
        result, stats = deduplicate([e1, e2])
        assert len(result) == 1
        assert stats["by_content"] == 1

    def test_no_dedup_different(self):
        e1 = _make_evidence(id="e1", url_hash="u1", content_hash="c1")
        e2 = _make_evidence(id="e2", url_hash="u2", content_hash="c2")
        result, stats = deduplicate([e1, e2])
        assert len(result) == 2
        assert stats["total_removed"] == 0

    def test_empty_input(self):
        result, stats = deduplicate([])
        assert result == []

    def test_order_independent(self):
        e1 = _make_evidence(id="e1", url_hash="same", content_hash="c1", source_quality=5)
        e2 = _make_evidence(id="e2", url_hash="same", content_hash="c2", source_quality=2)
        r1, _ = deduplicate([e1, e2])
        r2, _ = deduplicate([e2, e1])
        assert r1[0].source_quality == r2[0].source_quality  # Same survivor regardless of order


# ── Source Quality ────────────────────────────────────────────────

class TestSourceQuality:

    def test_regulator(self):
        tier, stype = classify_source_quality("mas.gov.sg")
        assert tier == 2
        assert stype == SourceType.REGULATOR

    def test_news(self):
        tier, stype = classify_source_quality("reuters.com")
        assert tier == 3
        assert stype == SourceType.NEWS

    def test_industry(self):
        tier, stype = classify_source_quality("techinasia.com")
        assert tier == 4
        assert stype == SourceType.INDUSTRY

    def test_social(self):
        tier, stype = classify_source_quality("linkedin.com")
        assert tier == 5
        assert stype == SourceType.SOCIAL

    def test_unknown_domain_tier_6(self):
        tier, stype = classify_source_quality("randomsite.xyz")
        assert tier == 6
        assert stype == SourceType.OTHER

    def test_competitor_domain_tier_1(self):
        tier, stype = classify_source_quality("competitor.com", {"competitor.com"})
        assert tier == 1
        assert stype == SourceType.COMPANY_SITE

    def test_gov_tld_tier_2(self):
        tier, stype = classify_source_quality("some-agency.gov.my")
        assert tier == 2


# ── Relevance Scoring ────────────────────────────────────────────

class TestRelevanceScoring:

    def test_high_relevance(self):
        e = _make_evidence(
            title="Jaguar Transit competitor launch Singapore",
            content="Jaguar Transit competitor launched a new product in Singapore market",
        )
        score = score_relevance(
            e, "Jaguar Transit", "Singapore",
            ["CompA"], [], "competitor activity", 30,
        )
        assert score >= 0.60

    def test_irrelevant(self):
        e = _make_evidence(
            title="Unrelated news about weather in Tokyo",
            content="Weather forecast for Tokyo shows rain expected this weekend",
            source_quality=6,
        )
        score = score_relevance(
            e, "Jaguar Transit", "Singapore",
            ["CompA"], [], "competitor activity", 30,
        )
        assert score < 0.35

    def test_label_boundaries(self):
        assert label_relevance(0.60) == Relevance.RELEVANT
        assert label_relevance(0.59) == Relevance.UNCERTAIN
        assert label_relevance(0.35) == Relevance.UNCERTAIN
        assert label_relevance(0.34) == Relevance.IRRELEVANT


# ── Date Filtering ────────────────────────────────────────────────

class TestDateFiltering:

    def test_within_window(self):
        e = _make_evidence(published_at=datetime.now(timezone.utc) - timedelta(days=5))
        result = filter_by_date([e], 30)
        assert len(result) == 1

    def test_outside_window(self):
        e = _make_evidence(published_at=datetime.now(timezone.utc) - timedelta(days=60))
        result = filter_by_date([e], 30)
        assert len(result) == 0

    def test_missing_date_retained(self):
        e = _make_evidence(published_at=None)
        result = filter_by_date([e], 30)
        assert len(result) == 1
        assert result[0].metadata.get("published_date_missing") is True


# ── Change Detection ─────────────────────────────────────────────

class TestChangeDetection:

    def test_all_new_no_prior(self):
        e = _make_evidence(url_hash="u1")
        result, summary = detect_evidence_changes([e], None)
        assert result[0].change_status == ChangeStatus.NEW
        assert summary["new"] == 1

    def test_unchanged(self):
        e_current = _make_evidence(url_hash="u1", content_hash="c1")
        e_prior = _make_evidence(url_hash="u1", content_hash="c1")
        result, summary = detect_evidence_changes([e_current], [e_prior])
        assert result[0].change_status == ChangeStatus.UNCHANGED

    def test_changed(self):
        e_current = _make_evidence(url_hash="u1", content_hash="c_new")
        e_prior = _make_evidence(url_hash="u1", content_hash="c_old")
        result, summary = detect_evidence_changes([e_current], [e_prior])
        assert result[0].change_status == ChangeStatus.CHANGED

    def test_removed_count(self):
        e_prior = _make_evidence(url_hash="u_gone")
        _, summary = detect_evidence_changes([], [e_prior])
        assert summary["removed"] == 1

    def test_identity_key_stable(self):
        k1 = compute_finding_identity_key("product_launch", "Title X", "CompA")
        k2 = compute_finding_identity_key("product_launch", "Title X", "CompA")
        assert k1 == k2

    def test_identity_key_case_insensitive(self):
        k1 = compute_finding_identity_key("product_launch", "Title X", "CompA")
        k2 = compute_finding_identity_key("product_launch", "title x", "compa")
        assert k1 == k2

    def test_all_unchanged(self):
        e = _make_evidence(change_status=ChangeStatus.UNCHANGED)
        assert all_evidence_unchanged([e])

    def test_not_all_unchanged(self):
        e1 = _make_evidence(id="e1", change_status=ChangeStatus.UNCHANGED)
        e2 = _make_evidence(id="e2", change_status=ChangeStatus.NEW)
        assert not all_evidence_unchanged([e1, e2])


# ── Finding Change Status Derivation ─────────────────────────────

class TestFindingChangeStatus:

    def test_new_if_any_new(self):
        e1 = _make_evidence(change_status=ChangeStatus.UNCHANGED)
        e2 = _make_evidence(change_status=ChangeStatus.NEW)
        assert derive_finding_change_status([e1, e2]) == ChangeStatus.NEW

    def test_changed_if_any_changed(self):
        e1 = _make_evidence(change_status=ChangeStatus.UNCHANGED)
        e2 = _make_evidence(change_status=ChangeStatus.CHANGED)
        assert derive_finding_change_status([e1, e2]) == ChangeStatus.CHANGED

    def test_unchanged_if_all_unchanged(self):
        e = _make_evidence(change_status=ChangeStatus.UNCHANGED)
        assert derive_finding_change_status([e]) == ChangeStatus.UNCHANGED


# ── Confidence Scoring ───────────────────────────────────────────

class TestConfidenceScoring:

    def test_basic_scoring(self):
        e = _make_evidence(source_quality=3)
        f = Finding(
            ai_confidence=75,
            supporting_evidence_ids=["e_001"],
        )
        score, breakdown = score_confidence(f, [e], 30)
        assert 0 <= score <= 100
        assert "source_quality" in breakdown
        assert "final_score" in breakdown

    def test_conflict_penalty(self):
        e = _make_evidence(source_quality=3)
        f = Finding(
            ai_confidence=75,
            supporting_evidence_ids=["e_001"],
            conflicts=[Conflict(description="test", evidence_ids=["e_001"])],
        )
        score_with, _ = score_confidence(f, [e], 30)
        f2 = Finding(ai_confidence=75, supporting_evidence_ids=["e_001"])
        score_without, _ = score_confidence(f2, [e], 30)
        assert score_with < score_without

    def test_low_quality_penalty(self):
        e = _make_evidence(source_quality=6)
        f = Finding(ai_confidence=75, supporting_evidence_ids=["e_001"])
        score, breakdown = score_confidence(f, [e], 30)
        assert "all_sources_low_quality (-10)" in breakdown["penalties"]

    def test_undated_penalty(self):
        e = _make_evidence(published_at=None, source_quality=3)
        f = Finding(ai_confidence=75, supporting_evidence_ids=["e_001"])
        score, breakdown = score_confidence(f, [e], 30)
        assert "all_sources_undated (-10)" in breakdown["penalties"]

    def test_empty_evidence(self):
        f = Finding(ai_confidence=75, supporting_evidence_ids=[])
        score, _ = score_confidence(f, [], 30)
        assert score == 0

    def test_relevance_score(self):
        e = _make_evidence(relevance_score=0.8)
        assert compute_finding_relevance_score([e]) == 80
