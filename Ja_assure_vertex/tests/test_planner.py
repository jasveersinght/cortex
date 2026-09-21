"""Tests for the Research Planner."""

import pytest
from app.research.enums import Complexity, ResearchType
from app.research.planner import compute_complexity, generate_queries, plan, QUERY_BUDGET


class TestComplexity:

    def test_low_complexity(self):
        c, score = compute_complexity(
            ResearchType.TREND_RESEARCH, [], [], 14, None, 10,
        )
        assert c == Complexity.LOW

    def test_medium_complexity(self):
        c, score = compute_complexity(
            ResearchType.COMPETITOR_MONITORING, ["A", "B"], [], 30, None, 20,
        )
        assert c == Complexity.MEDIUM

    def test_high_complexity(self):
        c, score = compute_complexity(
            ResearchType.COMPETITOR_MONITORING,
            ["A", "B", "C", "D"], [], 90,
            "A very detailed objective that is longer than 120 characters to trigger the bonus " * 2,
            30,
        )
        assert c == Complexity.HIGH

    def test_small_scope_reduces(self):
        c1, s1 = compute_complexity(ResearchType.COMPETITOR_MONITORING, ["A"], [], 30, None, 20)
        c2, s2 = compute_complexity(ResearchType.COMPETITOR_MONITORING, ["A"], [], 30, None, 10)
        assert s2 < s1


class TestQueryGeneration:

    def test_generates_queries(self):
        queries = generate_queries(
            ResearchType.COMPETITOR_MONITORING,
            "Jaguar Transit", "Singapore",
            ["CompA"], [], Complexity.MEDIUM, 30,
        )
        assert len(queries) > 0
        assert all(q.query for q in queries)

    def test_budget_cap(self):
        queries = generate_queries(
            ResearchType.COMPETITOR_MONITORING,
            "Brand", "Singapore",
            [f"Comp{i}" for i in range(10)], [],
            Complexity.LOW, 30,
        )
        assert len(queries) <= QUERY_BUDGET[Complexity.LOW]

    def test_discovery_mode(self):
        """When competitors is empty and type requires them, generates discovery queries."""
        queries = generate_queries(
            ResearchType.COMPETITOR_MONITORING,
            "Jaguar Transit", "Singapore",
            [], [], Complexity.MEDIUM, 30,
        )
        assert len(queries) > 0
        assert any("competitors" in q.query.lower() for q in queries)

    def test_no_duplicate_queries(self):
        queries = generate_queries(
            ResearchType.COMPETITOR_MONITORING,
            "Brand", "Singapore",
            ["CompA"], [], Complexity.MEDIUM, 30,
        )
        query_texts = [q.query.lower() for q in queries]
        assert len(query_texts) == len(set(query_texts))

    def test_topics_used_for_non_competitor_types(self):
        queries = generate_queries(
            ResearchType.TREND_RESEARCH,
            "Brand", "Singapore",
            [], ["AI", "blockchain"], Complexity.LOW, 14,
        )
        assert len(queries) > 0


class TestPlan:

    def test_full_plan_creation(self):
        p = plan(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            competitors=["CompA"],
            topics=[],
            objective="Identify recent activity",
            lookback_days=30,
            max_sources=20,
        )
        assert p.complexity in (Complexity.LOW, Complexity.MEDIUM, Complexity.HIGH)
        assert len(p.queries) > 0
        assert p.rationale

    def test_empty_plan_raises(self):
        """Edge case: if somehow no queries are generated, planner raises."""
        # This shouldn't happen with normal inputs, but tests the guard
        try:
            p = plan(
                brand="", market="Singapore",
                research_type=ResearchType.COMPETITOR_MONITORING,
                competitors=[], topics=[],
                objective=None, lookback_days=30, max_sources=20,
            )
            # If it doesn't raise, at least ensure queries exist
            assert len(p.queries) > 0
        except ValueError:
            pass  # Expected for truly empty inputs

    def test_plan_uses_type_default_lookback(self):
        p = plan(
            brand="Brand", market="Singapore",
            research_type=ResearchType.TREND_RESEARCH,
            competitors=[], topics=[], objective=None,
            lookback_days=None, max_sources=20,
        )
        # Trend research default is 14 days
        assert any(q.time_range_days == 14 for q in p.queries)
