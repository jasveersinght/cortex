"""Domain models for the Research / Discover Agent.

These are internal dataclass models used throughout the pipeline.
API request/response schemas live in app/api/schemas/.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.research.enums import (
    ChangeStatus,
    Complexity,
    FindingType,
    Relevance,
    SourceType,
    TavilyOperation,
)


# ── Research Type Registry ────────────────────────────────────────────

@dataclass(frozen=True)
class ResearchTypeConfig:
    """Configuration for a research type in the registry."""
    name: str
    query_templates: list[str]
    ttl_hours: int
    default_complexity: Complexity
    default_lookback_days: int
    requires_competitors: bool
    finding_type_hints: list[str]


# ── Planning Models ───────────────────────────────────────────────────

@dataclass
class PlannedQuery:
    """A single query the planner has decided to execute."""
    query: str
    operation: TavilyOperation
    purpose: str
    target_entity: str | None
    max_results: int
    time_range_days: int
    domains_include: list[str] = field(default_factory=list)
    domains_exclude: list[str] = field(default_factory=list)


@dataclass
class ExtractPolicyConfig:
    """Controls when extract operations are triggered."""
    enabled: bool = True
    max_urls: int = 5
    min_search_score: float = 0.6
    min_content_chars: int = 400


@dataclass
class ResearchPlan:
    """The complete plan for a research run."""
    complexity: Complexity
    queries: list[PlannedQuery]
    extract_policy: ExtractPolicyConfig
    crawl_targets: list[str] = field(default_factory=list)
    rationale: str = ""
    estimated_tavily_calls: int = 0


# ── Raw Source (Tavily output boundary) ───────────────────────────────

@dataclass
class RawSource:
    """Normalized output from the Tavily adapter.
    Vendor response shapes never leak past this boundary."""
    url: str
    title: str | None
    content: str | None
    published_at: datetime | None
    score: float | None
    source_operation: TavilyOperation
    query: str
    raw: dict = field(default_factory=dict)


# ── Evidence ──────────────────────────────────────────────────────────

@dataclass
class Evidence:
    """A single piece of processed, traceable evidence."""
    id: str                                 # "evidence_001"-style, stable within a run
    research_run_id: UUID | None = None
    source_type: SourceType = SourceType.OTHER
    source_name: str = ""
    source_quality: int = 6                 # 1..6, 1 = best
    title: str | None = None
    url: str = ""                           # normalized
    display_url: str = ""                   # original for display
    content: str = ""
    content_hash: str = ""
    url_hash: str = ""
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    market: str = ""
    competitor: str | None = None
    topic: str | None = None
    query: str = ""
    tavily_operation: str = ""
    relevance: Relevance = Relevance.UNCERTAIN
    relevance_score: float = 0.0
    change_status: ChangeStatus = ChangeStatus.NEW
    metadata: dict = field(default_factory=dict)


# ── Conflict ──────────────────────────────────────────────────────────

@dataclass
class Conflict:
    """A disagreement between evidence items within a finding."""
    description: str
    evidence_ids: list[str]


# ── Finding ───────────────────────────────────────────────────────────

@dataclass
class Finding:
    """A structured research finding synthesized by Groq."""
    id: UUID | None = None
    research_run_id: UUID | None = None
    identity_key: str = ""
    finding_type: FindingType = FindingType.OTHER
    title: str = ""
    summary: str = ""
    why_it_matters: str = ""
    opportunity: str | None = None
    entities: list[str] = field(default_factory=list)
    importance_score: int = 0
    relevance_score: int = 0
    confidence_score: int = 0
    ai_confidence: int = 0
    change_status: ChangeStatus = ChangeStatus.NEW
    conflicts: list[Conflict] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


# ── Analysis Payload / Result (Groq boundary) ────────────────────────

@dataclass
class AnalysisPayload:
    """The payload sent to Groq for analysis."""
    context: dict
    evidence: list[dict]


@dataclass
class AnalysisResult:
    """The validated result from Groq analysis."""
    findings: list[dict]
    insufficient_evidence: bool = False
    notes: str | None = None


# ── Research Result (final output) ────────────────────────────────────

@dataclass
class ResearchResult:
    """The complete result of a research run, returned by ResearchManager."""
    research_run_id: UUID | None = None
    brand: str = ""
    market: str = ""
    research_type: str = ""
    objective: str | None = None
    lookback_days: int | None = None
    status: str = ""
    cache_hit: bool = False
    stale: bool = False
    stale_age_hours: float | None = None
    plan: dict | None = None
    findings: list[Finding] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    sources_checked: int = 0
    unique_sources: int = 0
    relevant_sources: int = 0
    new_findings: int = 0
    changed_findings: int = 0
    unchanged_findings: int = 0
    tavily_calls: int = 0
    groq_calls: int = 0
    dropped_findings: int = 0
    confidence_score: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def in_flight(run_id: UUID) -> "ResearchResult":
        """Return a minimal result for an in-flight duplicate."""
        return ResearchResult(
            research_run_id=run_id,
            status="IN_FLIGHT",
        )
