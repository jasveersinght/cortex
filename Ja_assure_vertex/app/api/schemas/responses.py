"""Response schemas for the Discover API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ConflictResponse(BaseModel):
    description: str
    evidence_ids: list[str]


class EvidenceSummaryResponse(BaseModel):
    """Compact evidence summary embedded in a finding response."""
    evidence_ref: str
    title: str | None = None
    url: str
    source_name: str
    source_quality: int


class FindingResponse(BaseModel):
    """A single research finding."""
    id: UUID | None = None
    finding_type: str
    title: str
    summary: str
    why_it_matters: str
    opportunity: str | None = None
    entities: list[str] = []
    importance_score: int = 0
    relevance_score: int = 0
    confidence_score: int = 0
    ai_confidence: int = 0
    change_status: str = "NEW"
    conflicts: list[ConflictResponse] = []
    supporting_evidence_ids: list[str] = []
    supporting_evidence: list[EvidenceSummaryResponse] = []
    confidence_breakdown: dict | None = None
    created_at: datetime | None = None


class EvidenceResponse(BaseModel):
    """A single piece of research evidence."""
    id: UUID | None = None
    evidence_ref: str
    source_type: str
    source_name: str
    source_quality: int
    title: str | None = None
    url: str
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    market: str
    competitor: str | None = None
    topic: str | None = None
    query: str
    tavily_operation: str
    relevance: str
    relevance_score: float
    change_status: str
    content_preview: str | None = None  # First 500 chars for frontend preview


class ResearchRunResponse(BaseModel):
    """Response for a research run."""
    research_run_id: UUID | None = None
    brand: str = ""
    market: str = ""
    research_type: str = ""
    objective: str | None = None
    status: str = ""
    cache_hit: bool = False
    stale: bool = False
    stale_age_hours: float | None = None
    plan_rationale: str | None = None
    complexity: str | None = None
    lookback_days: int | None = None

    # Counts
    sources_checked: int = 0
    unique_sources: int = 0
    relevant_sources: int = 0
    findings_count: int = 0
    new_findings: int = 0
    changed_findings: int = 0
    unchanged_findings: int = 0
    dropped_findings: int = 0

    # Cost transparency
    tavily_calls: int = 0
    groq_calls: int = 0

    # Quality
    confidence_score: int | None = None
    error_message: str | None = None

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Findings and evidence (populated on detail endpoints)
    findings: list[FindingResponse] = []
    evidence: list[EvidenceResponse] = []

    metadata: dict = {}


class ResearchStatusResponse(BaseModel):
    """Lightweight status for the Discover fruit badge."""
    brand: str
    market: str
    research_type: str
    latest_run_id: UUID | None = None
    status: str | None = None
    completed_at: datetime | None = None
    cache_fresh: bool = False
    cache_expires_at: datetime | None = None
    findings_count: int = 0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    supabase: str = "unknown"
    tavily: str = "unknown"
    groq: str = "unknown"
