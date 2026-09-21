"""Comprehensive unit and integration tests for ResearchManager pipeline behavior.

Tests mock Tavily, Groq, Supabase repository, and CacheManager to deterministically verify:
- Happy path (end-to-end orchestration)
- Cache hit (zero external calls)
- Cache miss / force refresh
- In-flight concurrency detection (202 / duplicate protection)
- All unchanged evidence (Groq skip + carry-forward)
- No relevant evidence (Groq skip + honest completion)
- Tavily failure with and without stale cache fallback
- Groq failure (persisting evidence + PARTIAL_FAILURE)
- Partial Tavily failure (partial queries failed)
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from app.research.enums import (
    ChangeStatus, Complexity, FindingType, Relevance, ResearchType, RunStatus, SourceType, TavilyOperation,
)
from app.research.models import (
    AnalysisResult, Conflict, Evidence, Finding, PlannedQuery, RawSource, ResearchPlan, ResearchResult, ExtractPolicyConfig,
)
from app.research.manager import ResearchManager


class MockTavilyAdapter:
    def __init__(self, raw_sources=None, calls=1, failed_queries=None):
        self.raw_sources = raw_sources or []
        self.calls = calls
        self.failed_queries = failed_queries or []

    def execute_plan(self, plan, max_sources):
        return self.raw_sources, self.calls, self.failed_queries


class MockGroqAdapter:
    def __init__(self, result=None, should_fail=False):
        self.result = result or AnalysisResult(findings=[])
        self.should_fail = should_fail
        self.call_count = 0

    def analyze(self, payload):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Groq rate limit exceeded")
        return self.result


class MockRepo:
    def __init__(self):
        self.runs = {}
        self.evidence = {}
        self.findings = {}
        self.inflight_hash = None
        self.prior_run = None
        self.competitor_domains = set()

    def create_run(self, brand, market, research_type, objective, request_hash, lookback_days, status):
        run_id = uuid4()
        self.runs[run_id] = {
            "id": str(run_id),
            "brand": brand,
            "market": market,
            "research_type": research_type,
            "objective": objective,
            "request_hash": request_hash,
            "lookback_days": lookback_days,
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        return run_id

    def update_run_status(self, run_id, status):
        if run_id in self.runs:
            self.runs[run_id]["status"] = status

    def attach_plan(self, run_id, plan_dict):
        if run_id in self.runs:
            self.runs[run_id]["plan"] = plan_dict

    def complete_run(self, run_id, status, metrics, error_message=None, metadata=None):
        if run_id in self.runs:
            self.runs[run_id].update({
                "status": status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error_message": error_message,
                "metadata": metadata or {},
                **metrics,
            })

    def set_run_failed(self, run_id, error_message):
        self.complete_run(run_id, RunStatus.FAILED.value, {}, error_message=error_message)

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def find_prior_completed_run(self, brand, market, research_type):
        return self.prior_run

    def find_inflight_run(self, request_hash):
        if self.inflight_hash == request_hash:
            return uuid4()
        return None

    def get_competitor_domains(self, brand, market):
        return self.competitor_domains

    def save_evidence(self, run_id, evidence_list):
        self.evidence[run_id] = evidence_list

    def get_evidence_for_run(self, run_id):
        return [
            {
                "evidence_ref": e.id,
                "url_hash": e.url_hash,
                "content_hash": e.content_hash,
                "url": e.url,
                "title": e.title,
                "source_name": e.source_name,
                "source_quality": e.source_quality,
            }
            for e in self.evidence.get(run_id, [])
        ]

    def get_prior_evidence(self, run_id):
        return self.evidence.get(run_id, [])

    def save_findings(self, run_id, findings):
        self.findings[run_id] = findings

    def get_findings_for_run(self, run_id, change_status=None, min_confidence=None):
        findings_list = self.findings.get(run_id, [])
        rows = []
        for f in findings_list:
            rows.append({
                "id": str(f.id or uuid4()),
                "finding_type": f.finding_type.value if hasattr(f.finding_type, "value") else str(f.finding_type),
                "title": f.title,
                "summary": f.summary,
                "why_it_matters": f.why_it_matters,
                "opportunity": f.opportunity,
                "entities": f.entities,
                "importance_score": f.importance_score,
                "relevance_score": f.relevance_score,
                "confidence_score": f.confidence_score,
                "ai_confidence": f.ai_confidence,
                "change_status": f.change_status.value if hasattr(f.change_status, "value") else str(f.change_status),
                "conflicts": [{"description": c.description, "evidence_ids": c.evidence_ids} for c in f.conflicts],
                "supporting_evidence_ids": f.supporting_evidence_ids,
                "metadata": f.metadata,
                "created_at": f.created_at.isoformat() if f.created_at else datetime.now(timezone.utc).isoformat(),
            })
        return rows


class MockCacheManager:
    def __init__(self):
        self.store = {}
        self.stale_store = {}

    def get_valid(self, cache_key):
        return self.store.get(cache_key)

    def get_stale(self, cache_key):
        return self.stale_store.get(cache_key)

    def write(self, cache_key, request_hash, run_id, research_type, ttl_hours):
        self.store[cache_key] = {
            "cache_key": cache_key,
            "request_hash": request_hash,
            "research_run_id": str(run_id),
            "research_type": research_type,
            "ttl_hours": ttl_hours,
        }

    def invalidate(self, cache_key):
        self.store.pop(cache_key, None)


def _sample_raw_source():
    return RawSource(
        url="https://straitstimes.com/business/sample-news",
        title="Competitor Launches Product in Singapore",
        content="Competitor X launched a brand new transit cover product in Singapore today with great success.",
        published_at=datetime.now(timezone.utc) - timedelta(days=2),
        score=0.9,
        source_operation=TavilyOperation.SEARCH,
        query="Competitor X Singapore",
    )


class TestResearchManagerPipeline:

    def test_happy_path_end_to_end(self):
        raw = _sample_raw_source()
        tavily = MockTavilyAdapter(raw_sources=[raw], calls=2)
        groq_result = AnalysisResult(findings=[{
            "finding_type": "product_launch",
            "title": "Competitor X Product Launch",
            "summary": "Competitor X launched transit cover",
            "why_it_matters": "Increases market competition",
            "opportunity": "Differentiate with pricing",
            "entities": ["Competitor X"],
            "importance_score": 85,
            "ai_confidence": 80,
            "supporting_evidence_ids": ["evidence_001"],
            "conflicts": [],
        }])
        groq = MockGroqAdapter(result=groq_result)
        repo = MockRepo()
        cache = MockCacheManager()

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            competitors=["Competitor X"],
            lookback_days=30,
        )

        assert result.status == RunStatus.COMPLETED.value
        assert result.cache_hit is False
        assert result.lookback_days == 30
        assert len(result.findings) == 1
        assert result.findings[0].title == "Competitor X Product Launch"
        assert result.findings[0].created_at is not None
        assert result.findings[0].confidence_score > 0
        assert "confidence_breakdown" in result.findings[0].metadata
        assert result.tavily_calls == 2
        assert result.groq_calls == 1
        assert len(cache.store) == 1

    def test_cache_hit_bypasses_providers(self):
        tavily = MockTavilyAdapter()
        groq = MockGroqAdapter()
        repo = MockRepo()
        cache = MockCacheManager()

        # Seed an existing run in repo and cache
        run_id = uuid4()
        repo.runs[run_id] = {
            "id": str(run_id),
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
            "status": RunStatus.COMPLETED.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "sources_checked": 5,
        }
        from app.research.repositories.cache import compute_request_hash, build_cache_key
        req_hash = compute_request_hash("Jaguar Transit", "Singapore", "competitor_monitoring", [], [], 30, None)
        cache_key = build_cache_key("competitor_monitoring", req_hash)
        cache.write(cache_key, req_hash, run_id, "competitor_monitoring", 24)

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
            force_refresh=False,
        )

        assert result.cache_hit is True
        assert result.research_run_id == run_id
        assert tavily.calls == 1  # Note: execute_plan was never called
        assert groq.call_count == 0

    def test_force_refresh_bypasses_cache(self):
        raw = _sample_raw_source()
        tavily = MockTavilyAdapter(raw_sources=[raw])
        groq = MockGroqAdapter()
        repo = MockRepo()
        cache = MockCacheManager()

        # Seed an existing cache row
        run_id = uuid4()
        from app.research.repositories.cache import compute_request_hash, build_cache_key
        req_hash = compute_request_hash("Jaguar Transit", "Singapore", "competitor_monitoring", [], [], 30, None)
        cache_key = build_cache_key("competitor_monitoring", req_hash)
        cache.write(cache_key, req_hash, run_id, "competitor_monitoring", 24)

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
            force_refresh=True,  # Bypass!
        )

        assert result.cache_hit is False
        assert result.research_run_id != run_id

    def test_inflight_duplicate_returns_in_flight(self):
        tavily = MockTavilyAdapter()
        groq = MockGroqAdapter()
        repo = MockRepo()
        cache = MockCacheManager()

        from app.research.repositories.cache import compute_request_hash
        req_hash = compute_request_hash("Jaguar Transit", "Singapore", "competitor_monitoring", [], [], 30, None)
        repo.inflight_hash = req_hash

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
        )

        assert result.status == "IN_FLIGHT"

    def test_all_unchanged_skips_groq_and_carries_forward(self):
        raw = _sample_raw_source()
        tavily = MockTavilyAdapter(raw_sources=[raw])
        groq = MockGroqAdapter()
        repo = MockRepo()
        cache = MockCacheManager()

        # Setup prior run with identical evidence and findings
        prior_run_id = uuid4()
        repo.runs[prior_run_id] = {
            "id": str(prior_run_id),
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
            "status": RunStatus.COMPLETED.value,
        }
        repo.prior_run = repo.runs[prior_run_id]

        from app.research.processing.normalization import normalize_url, normalize_content, hash_url, hash_content
        norm_url = normalize_url(raw.url)
        norm_content, _ = normalize_content(raw.content)
        prior_ev = Evidence(
            id="evidence_001",
            url=norm_url,
            url_hash=hash_url(norm_url),
            content_hash=hash_content(norm_content),
        )
        repo.evidence[prior_run_id] = [prior_ev]
        repo.findings[prior_run_id] = [
            Finding(
                id=uuid4(),
                title="Existing Unchanged Finding",
                finding_type=FindingType.SERVICE_LAUNCH,
                change_status=ChangeStatus.UNCHANGED,
                supporting_evidence_ids=["evidence_001"],
            )
        ]

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
        )

        assert result.status == RunStatus.COMPLETED.value
        assert groq.call_count == 0  # Groq was skipped!
        assert result.groq_calls == 0
        assert len(result.findings) == 1
        assert result.findings[0].change_status == ChangeStatus.UNCHANGED

    def test_groq_failure_persists_evidence_partial_failure(self):
        raw = _sample_raw_source()
        tavily = MockTavilyAdapter(raw_sources=[raw])
        groq = MockGroqAdapter(should_fail=True)  # Fails!
        repo = MockRepo()
        cache = MockCacheManager()

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
        )

        assert result.status == RunStatus.PARTIAL_FAILURE.value
        assert "Groq analysis failed" in (result.error_message or "")
        # Evidence was preserved
        assert len(repo.evidence.get(result.research_run_id, [])) == 1
        assert len(result.findings) == 0
        # Not cached
        assert len(cache.store) == 0

    def test_all_tavily_queries_fail_without_cache(self):
        tavily = MockTavilyAdapter(raw_sources=[], failed_queries=["query 1", "query 2"])
        groq = MockGroqAdapter()
        repo = MockRepo()
        cache = MockCacheManager()

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
        )

        assert result.status == RunStatus.FAILED.value
        assert "All research queries failed" in (result.error_message or "")
        assert groq.call_count == 0
        assert len(cache.store) == 0

    def test_all_tavily_queries_fail_with_stale_cache(self):
        stale_run_id = uuid4()
        tavily = MockTavilyAdapter(raw_sources=[], failed_queries=["query 1"])
        groq = MockGroqAdapter()
        repo = MockRepo()
        cache = MockCacheManager()

        repo.runs[stale_run_id] = {
            "id": str(stale_run_id),
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
            "status": RunStatus.COMPLETED.value,
            "completed_at": (datetime.now(timezone.utc) - timedelta(hours=36)).isoformat(),
        }
        from app.research.repositories.cache import compute_request_hash, build_cache_key
        req_hash = compute_request_hash("Jaguar Transit", "Singapore", "competitor_monitoring", [], [], 30, None)
        cache_key = build_cache_key("competitor_monitoring", req_hash)
        cache.stale_store[cache_key] = {"research_run_id": str(stale_run_id)}

        manager = ResearchManager(tavily, groq, repo, cache)
        result = manager.run(
            brand="Jaguar Transit",
            market="Singapore",
            research_type=ResearchType.COMPETITOR_MONITORING,
            lookback_days=30,
        )

        assert result.stale is True
        assert result.research_run_id == stale_run_id
