"""Discover API Routes.

Thin route handlers — all business logic lives in ResearchManager.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.schemas.requests import ResearchRequest
from app.api.schemas.responses import (
    ResearchRunResponse, FindingResponse, EvidenceResponse,
    EvidenceSummaryResponse, ConflictResponse,
    ResearchStatusResponse, HealthResponse,
)
from app.research.enums import ResearchType, RunStatus
from app.research.exceptions import ResearchRunNotFound
from app.research.models import ResearchResult

logger = logging.getLogger("ja_assure")

router = APIRouter(prefix="/discover", tags=["discover"])


def _get_manager():
    """Lazy-init the ResearchManager singleton."""
    from app.config import settings
    from app.research.manager import ResearchManager
    from app.research.adapters.tavily import TavilyResearchAdapter
    from app.research.adapters.groq import GroqAnalysisAdapter
    from app.research.repositories.supabase import ResearchRepository
    from app.research.repositories.cache import CacheManager

    # These are created once and reused
    if not hasattr(_get_manager, "_instance"):
        tavily = TavilyResearchAdapter(api_key=settings.TAVILY_API_KEY)
        groq = GroqAnalysisAdapter(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL)
        repo = ResearchRepository(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        cache = CacheManager(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        _get_manager._instance = ResearchManager(tavily, groq, repo, cache)
    return _get_manager._instance


def _get_repo():
    """Lazy-init the ResearchRepository singleton."""
    from app.config import settings
    from app.research.repositories.supabase import ResearchRepository
    if not hasattr(_get_repo, "_instance"):
        _get_repo._instance = ResearchRepository(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _get_repo._instance


def _result_to_response(result: ResearchResult) -> ResearchRunResponse:
    """Convert internal ResearchResult to API response."""
    findings = []
    for f in result.findings:
        conflicts = [
            ConflictResponse(description=c.description, evidence_ids=c.evidence_ids)
            for c in f.conflicts
        ]
        findings.append(FindingResponse(
            id=f.id,
            finding_type=f.finding_type.value if hasattr(f.finding_type, 'value') else str(f.finding_type),
            title=f.title,
            summary=f.summary,
            why_it_matters=f.why_it_matters,
            opportunity=f.opportunity,
            entities=f.entities,
            importance_score=f.importance_score,
            relevance_score=f.relevance_score,
            confidence_score=f.confidence_score,
            ai_confidence=f.ai_confidence,
            change_status=f.change_status.value if hasattr(f.change_status, 'value') else str(f.change_status),
            conflicts=conflicts,
            supporting_evidence_ids=f.supporting_evidence_ids,
            confidence_breakdown=f.metadata.get("confidence_breakdown"),
            created_at=f.created_at,
        ))

    plan = result.plan or {}

    return ResearchRunResponse(
        research_run_id=result.research_run_id,
        brand=result.brand,
        market=result.market,
        research_type=result.research_type,
        objective=result.objective,
        status=result.status,
        cache_hit=result.cache_hit,
        stale=result.stale,
        stale_age_hours=result.stale_age_hours,
        plan_rationale=plan.get("rationale") if isinstance(plan, dict) else None,
        complexity=plan.get("complexity") if isinstance(plan, dict) else None,
        lookback_days=result.lookback_days,
        sources_checked=result.sources_checked,
        unique_sources=result.unique_sources,
        relevant_sources=result.relevant_sources,
        findings_count=len(findings),
        new_findings=result.new_findings,
        changed_findings=result.changed_findings,
        unchanged_findings=result.unchanged_findings,
        dropped_findings=result.dropped_findings,
        tavily_calls=result.tavily_calls,
        groq_calls=result.groq_calls,
        confidence_score=result.confidence_score,
        error_message=result.error_message,
        started_at=result.started_at,
        completed_at=result.completed_at,
        findings=findings,
        metadata=result.metadata,
    )


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/run", response_model=ResearchRunResponse, status_code=201)
async def run_research(request: ResearchRequest, response: Response):
    """Start a research run (or return cached result).

    - 200: cache hit
    - 201: new run completed
    - 202: identical run in-flight
    - 422: validation error
    - 502: external provider failure
    """
    manager = _get_manager()

    result = manager.run(
        brand=request.brand,
        market=request.market,
        research_type=request.research_type,
        objective=request.objective,
        competitors=request.competitors,
        topics=request.topics,
        lookback_days=request.lookback_days,
        force_refresh=request.force_refresh,
        max_sources=request.max_sources,
    )

    if result.cache_hit:
        response.status_code = 200
    elif result.status == "IN_FLIGHT":
        response.status_code = 202
    elif result.status == RunStatus.FAILED.value and result.error_message and ("Tavily" in result.error_message or "queries failed" in result.error_message):
        response.status_code = 502
    else:
        response.status_code = 201

    return _result_to_response(result)


@router.get("/status", response_model=list[ResearchStatusResponse])
async def get_status():
    """Get lightweight status for each (brand, market, research_type) combination."""
    repo = _get_repo()
    rows = repo.get_latest_runs_status()

    statuses = []
    for row in rows:
        findings_count = (
            (row.get("new_findings") or 0)
            + (row.get("changed_findings") or 0)
            + (row.get("unchanged_findings") or 0)
        )
        statuses.append(ResearchStatusResponse(
            brand=row.get("brand", ""),
            market=row.get("market", ""),
            research_type=row.get("research_type", ""),
            latest_run_id=UUID(row["id"]) if row.get("id") else None,
            status=row.get("status"),
            completed_at=row.get("completed_at"),
            findings_count=findings_count,
        ))

    return statuses


@router.get("/{research_run_id}", response_model=ResearchRunResponse)
async def get_research_run(research_run_id: UUID):
    """Get a research run with its findings and metrics."""
    repo = _get_repo()
    run_data = repo.get_run(research_run_id)
    if not run_data:
        raise ResearchRunNotFound(str(research_run_id))

    # Load findings
    findings_data = repo.get_findings_for_run(research_run_id)

    findings = []
    for row in findings_data:
        conflicts = [
            ConflictResponse(description=c.get("description", ""), evidence_ids=c.get("evidence_ids", []))
            for c in (row.get("conflicts") or [])
        ]
        findings.append(FindingResponse(
            id=UUID(row["id"]) if row.get("id") else None,
            finding_type=row.get("finding_type", "other"),
            title=row.get("title", ""),
            summary=row.get("summary", ""),
            why_it_matters=row.get("why_it_matters", ""),
            opportunity=row.get("opportunity"),
            entities=row.get("entities", []),
            importance_score=row.get("importance_score", 0),
            relevance_score=row.get("relevance_score", 0),
            confidence_score=row.get("confidence_score", 0),
            ai_confidence=row.get("ai_confidence", 0),
            change_status=row.get("change_status", "NEW"),
            conflicts=conflicts,
            supporting_evidence_ids=row.get("supporting_evidence_ids", []),
            confidence_breakdown=row.get("metadata", {}).get("confidence_breakdown"),
            created_at=row.get("created_at"),
        ))

    plan = run_data.get("plan") or {}

    return ResearchRunResponse(
        research_run_id=research_run_id,
        brand=run_data.get("brand", ""),
        market=run_data.get("market", ""),
        research_type=run_data.get("research_type", ""),
        objective=run_data.get("objective"),
        status=run_data.get("status", ""),
        plan_rationale=plan.get("rationale") if isinstance(plan, dict) else None,
        complexity=plan.get("complexity") if isinstance(plan, dict) else None,
        lookback_days=run_data.get("lookback_days"),
        sources_checked=run_data.get("sources_checked", 0),
        unique_sources=run_data.get("unique_sources", 0),
        relevant_sources=run_data.get("relevant_sources", 0),
        findings_count=len(findings),
        new_findings=run_data.get("new_findings", 0),
        changed_findings=run_data.get("changed_findings", 0),
        unchanged_findings=run_data.get("unchanged_findings", 0),
        dropped_findings=run_data.get("dropped_findings", 0),
        tavily_calls=run_data.get("tavily_calls", 0),
        groq_calls=run_data.get("groq_calls", 0),
        confidence_score=run_data.get("confidence_score"),
        error_message=run_data.get("error_message"),
        started_at=run_data.get("started_at"),
        completed_at=run_data.get("completed_at"),
        findings=findings,
        metadata=run_data.get("metadata", {}),
    )


@router.get("/{research_run_id}/findings", response_model=list[FindingResponse])
async def get_findings(
    research_run_id: UUID,
    change_status: str | None = Query(None, description="Filter by change status: NEW, CHANGED, UNCHANGED"),
    min_confidence: int | None = Query(None, ge=0, le=100, description="Minimum confidence score"),
):
    """Get findings for a research run."""
    repo = _get_repo()
    run_data = repo.get_run(research_run_id)
    if not run_data:
        raise ResearchRunNotFound(str(research_run_id))

    rows = repo.get_findings_for_run(research_run_id, change_status, min_confidence)
    findings = []
    for row in rows:
        # Build compact evidence summaries
        evidence_summaries = []
        evidence_rows = repo.get_evidence_for_run(research_run_id)
        evidence_map = {e["evidence_ref"]: e for e in evidence_rows}
        for eid in row.get("supporting_evidence_ids", []):
            if eid in evidence_map:
                ev = evidence_map[eid]
                evidence_summaries.append(EvidenceSummaryResponse(
                    evidence_ref=eid,
                    title=ev.get("title"),
                    url=ev.get("url", ""),
                    source_name=ev.get("source_name", ""),
                    source_quality=ev.get("source_quality", 6),
                ))

        conflicts = [
            ConflictResponse(description=c.get("description", ""), evidence_ids=c.get("evidence_ids", []))
            for c in (row.get("conflicts") or [])
        ]

        findings.append(FindingResponse(
            id=UUID(row["id"]) if row.get("id") else None,
            finding_type=row.get("finding_type", "other"),
            title=row.get("title", ""),
            summary=row.get("summary", ""),
            why_it_matters=row.get("why_it_matters", ""),
            opportunity=row.get("opportunity"),
            entities=row.get("entities", []),
            importance_score=row.get("importance_score", 0),
            relevance_score=row.get("relevance_score", 0),
            confidence_score=row.get("confidence_score", 0),
            ai_confidence=row.get("ai_confidence", 0),
            change_status=row.get("change_status", "NEW"),
            conflicts=conflicts,
            supporting_evidence_ids=row.get("supporting_evidence_ids", []),
            supporting_evidence=evidence_summaries,
            confidence_breakdown=row.get("metadata", {}).get("confidence_breakdown"),
            created_at=row.get("created_at"),
        ))

    return findings


@router.get("/{research_run_id}/evidence", response_model=list[EvidenceResponse])
async def get_evidence(
    research_run_id: UUID,
    relevance: str | None = Query(None, description="Filter by relevance: RELEVANT, UNCERTAIN, IRRELEVANT"),
):
    """Get all evidence for a research run (including IRRELEVANT for auditability)."""
    repo = _get_repo()
    run_data = repo.get_run(research_run_id)
    if not run_data:
        raise ResearchRunNotFound(str(research_run_id))

    rows = repo.get_evidence_for_run(research_run_id)

    evidence = []
    for row in rows:
        if relevance and row.get("relevance") != relevance:
            continue
        evidence.append(EvidenceResponse(
            id=UUID(row["id"]) if row.get("id") else None,
            evidence_ref=row.get("evidence_ref", ""),
            source_type=row.get("source_type", "other"),
            source_name=row.get("source_name", ""),
            source_quality=row.get("source_quality", 6),
            title=row.get("title"),
            url=row.get("url", ""),
            published_at=row.get("published_at"),
            retrieved_at=row.get("retrieved_at"),
            market=row.get("market", ""),
            competitor=row.get("competitor"),
            topic=row.get("topic"),
            query=row.get("query", ""),
            tavily_operation=row.get("tavily_operation", ""),
            relevance=row.get("relevance", "UNCERTAIN"),
            relevance_score=float(row.get("relevance_score", 0)),
            change_status=row.get("change_status", "NEW"),
            content_preview=(row.get("content") or "")[:500],
        ))

    return evidence
