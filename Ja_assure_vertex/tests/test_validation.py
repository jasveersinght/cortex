"""Tests for request validation and hashing."""

import pytest
from app.api.schemas.requests import ResearchRequest
from app.research.enums import ResearchType
from app.research.repositories.cache import compute_request_hash, build_cache_key


# ── Request Validation ────────────────────────────────────────────

class TestResearchRequestValidation:

    def test_valid_request(self):
        req = ResearchRequest(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
        )
        assert req.brand == "Jaguar Transit"
        assert req.market == "Singapore"

    def test_brand_strip(self):
        req = ResearchRequest(
            brand="  Jaguar Transit  ",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
        )
        assert req.brand == "Jaguar Transit"

    def test_invalid_market(self):
        with pytest.raises(ValueError):
            ResearchRequest(
                brand="Test", market="NotAMarket",
                research_type=ResearchType.COMPETITOR_MONITORING,
            )

    def test_invalid_research_type(self):
        with pytest.raises(ValueError):
            ResearchRequest(
                brand="Test", market="Singapore",
                research_type="nonexistent_type",
            )

    def test_competitors_dedup_case_insensitive(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            competitors=["CompA", "compa", "COMPA", "CompB"],
        )
        assert len(req.competitors) == 2

    def test_competitors_cap_at_10(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            competitors=[f"Comp{i}" for i in range(15)],
        )
        assert len(req.competitors) == 10

    def test_competitors_strip_empties(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            competitors=["", "  ", "CompA", "  CompB  "],
        )
        assert req.competitors == ["CompA", "CompB"]

    def test_topics_normalization(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.TREND_RESEARCH,
            topics=["AI", "ai", "  AI  ", "blockchain"],
        )
        assert len(req.topics) == 2

    def test_objective_empty_string_becomes_none(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.TREND_RESEARCH,
            objective="   ",
        )
        assert req.objective is None

    def test_max_sources_clamped(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.TREND_RESEARCH,
            max_sources=100,
        )
        assert req.max_sources == 50

    def test_max_sources_floor(self):
        req = ResearchRequest(
            brand="Test", market="Singapore",
            research_type=ResearchType.TREND_RESEARCH,
            max_sources=1,
        )
        assert req.max_sources == 5

    def test_lookback_days_range(self):
        with pytest.raises(ValueError):
            ResearchRequest(
                brand="Test", market="Singapore",
                research_type=ResearchType.TREND_RESEARCH,
                lookback_days=0,
            )

    def test_all_valid_markets(self):
        for market in ["Singapore", "Malaysia", "Hong Kong", "Indonesia", "Thailand"]:
            req = ResearchRequest(
                brand="Test", market=market,
                research_type=ResearchType.TREND_RESEARCH,
            )
            assert req.market == market


# ── Request Hashing ───────────────────────────────────────────────

class TestRequestHashing:

    def test_hash_stability(self):
        h1 = compute_request_hash("Brand", "Singapore", "competitor_monitoring", ["A"], [], 30, None)
        h2 = compute_request_hash("Brand", "Singapore", "competitor_monitoring", ["A"], [], 30, None)
        assert h1 == h2

    def test_hash_case_insensitivity(self):
        h1 = compute_request_hash("Brand", "Singapore", "competitor_monitoring", ["CompA"], [], 30, None)
        h2 = compute_request_hash("brand", "singapore", "competitor_monitoring", ["compa"], [], 30, None)
        assert h1 == h2

    def test_hash_order_independence(self):
        h1 = compute_request_hash("B", "S", "t", ["A", "B"], [], 30, None)
        h2 = compute_request_hash("B", "S", "t", ["B", "A"], [], 30, None)
        assert h1 == h2

    def test_hash_sensitive_to_type(self):
        h1 = compute_request_hash("B", "S", "competitor_monitoring", [], [], 30, None)
        h2 = compute_request_hash("B", "S", "trend_research", [], [], 30, None)
        assert h1 != h2

    def test_hash_sensitive_to_lookback(self):
        h1 = compute_request_hash("B", "S", "t", [], [], 30, None)
        h2 = compute_request_hash("B", "S", "t", [], [], 60, None)
        assert h1 != h2

    def test_hash_whitespace_insensitivity(self):
        h1 = compute_request_hash("  Brand  ", "Singapore", "t", [], [], 30, "  hello  world  ")
        h2 = compute_request_hash("Brand", "Singapore", "t", [], [], 30, "hello world")
        assert h1 == h2


# ── Cache Key ─────────────────────────────────────────────────────

class TestCacheKey:

    def test_cache_key_format(self):
        key = build_cache_key("competitor_monitoring", "abc123def456")
        assert key == "research:competitor_monitoring:abc123def456"

    def test_cache_key_truncates_hash(self):
        long_hash = "a" * 64
        key = build_cache_key("trend_research", long_hash)
        assert key == f"research:trend_research:{'a' * 16}"
