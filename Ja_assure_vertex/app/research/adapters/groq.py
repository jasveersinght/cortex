"""Groq Analysis Adapter.

Owns the Groq SDK, system prompt, JSON schema enforcement,
and strict output validation (§17.5).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Protocol

from app.research.enums import FindingType, Relevance
from app.research.models import AnalysisPayload, AnalysisResult, Evidence

logger = logging.getLogger("ja_assure")

# ── System Prompt (implementation-grade, per §18.1) ───────────────

GROQ_SYSTEM_PROMPT = """ROLE
You are a research intelligence analyst for JA Assure, a niche InsurTech operating in
Singapore, Malaysia, Hong Kong, Indonesia and Thailand.

INPUT
You will receive a research context and a list of evidence items that were collected by
an external research system. Each evidence item has a stable id.

TASK
Synthesize the supplied evidence into structured findings. Group related evidence into a
single finding rather than producing one finding per article. Classify each finding,
explain why it matters to the stated brand and market, and identify any opportunity
signal that the evidence genuinely supports.

ABSOLUTE CONSTRAINTS
- Use ONLY the supplied evidence. You have no other knowledge of these companies or events.
- Do NOT invent facts, sources, URLs, dates, statistics, companies, or events.
- Do NOT fill gaps with plausible guesses. Missing information stays missing.
- Every finding MUST list the evidence ids that support it. A finding with no supporting
  evidence id is invalid and must not be produced.
- Do NOT reference any URL that does not appear in the supplied evidence.
- Do NOT make business decisions, recommend budgets, or write marketing copy.

CONFLICT RULE
If two evidence items disagree, do NOT pick a winner and do NOT average them. Record the
disagreement in the finding's `conflicts` array, describe what differs, list the conflicting
evidence ids, and lower `ai_confidence` accordingly.

INSUFFICIENCY RULE
If the evidence does not support any meaningful finding, return an empty `findings` array
and set `insufficient_evidence` to true. This is a correct and valuable answer. Producing a
weak finding to avoid an empty result is a failure.

SCORING
- `importance_score` (0-100): how strategically significant this is for the stated brand and
  market. A competitor entering the brand's exact niche is high; a generic industry mention
  is low.
- `ai_confidence` (0-100): how strongly the SUPPLIED EVIDENCE supports the claim you are
  making. Single undated secondary source = low. Multiple independent sources including an
  official one = high. These two scores are independent.

OUTPUT
Return ONLY valid JSON matching the provided schema. No prose, no markdown, no code fences.

REQUIRED JSON SCHEMA:
{
  "findings": [
    {
      "finding_type": "string (one of: product_launch, service_launch, campaign, partnership, pricing_change, market_entry, market_exit, technology_change, customer_signal, industry_trend, regulatory_change, social_signal, other)",
      "title": "string, <= 140 chars",
      "summary": "string, <= 600 chars",
      "why_it_matters": "string, <= 400 chars",
      "opportunity": "string or null, <= 400 chars",
      "entities": ["string"],
      "importance_score": 0,
      "ai_confidence": 0,
      "supporting_evidence_ids": ["evidence_001"],
      "conflicts": [
        {
          "description": "string",
          "evidence_ids": ["evidence_002"]
        }
      ]
    }
  ],
  "insufficient_evidence": false,
  "notes": "string or null"
}"""


# ── Protocol ──────────────────────────────────────────────────────

class GroqAdapterProtocol(Protocol):
    def analyze(self, payload: AnalysisPayload) -> AnalysisResult: ...


# ── Concrete Implementation ──────────────────────────────────────

class GroqAnalysisAdapter:
    """Adapter wrapping the Groq SDK."""

    def __init__(self, api_key: str, model: str = "groq/compound"):
        from groq import Groq
        self._client = Groq(api_key=api_key)
        self._model = model

    def analyze(self, payload: AnalysisPayload) -> AnalysisResult:
        """Send evidence to Groq for synthesis.

        One batched call over all evidence. Never one call per article.
        """
        user_message = json.dumps({
            "context": payload.context,
            "evidence": payload.evidence,
        }, default=str)

        logger.info(
            f"Groq analyze: {len(payload.evidence)} evidence items, "
            f"payload_chars={len(user_message)}"
        )

        try:
            response = self._call_groq(user_message)
            result = self._parse_response(response)
            return result
        except Exception as e:
            logger.error(f"Groq analysis failed: {type(e).__name__}: {e}")
            # Retry once
            try:
                logger.info("Retrying Groq call after failure...")
                time.sleep(2)
                response = self._call_groq(user_message)
                result = self._parse_response(response)
                return result
            except Exception as retry_error:
                logger.error(f"Groq retry also failed: {retry_error}")
                raise

    def _call_groq(self, user_message: str) -> str:
        """Make the actual Groq API call."""
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content

    def _parse_response(self, raw_text: str) -> AnalysisResult:
        """Parse and basic-validate the Groq JSON response."""
        # Strip any markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(text)

        findings = data.get("findings", [])
        insufficient = data.get("insufficient_evidence", False)
        notes = data.get("notes")

        return AnalysisResult(
            findings=findings,
            insufficient_evidence=insufficient,
            notes=notes,
        )


# ── Output Validation (§17.5) ────────────────────────────────────

VALID_FINDING_TYPES = {ft.value for ft in FindingType}


def validate_groq_output(
    result: AnalysisResult,
    evidence_ids: set[str],
    evidence_urls: set[str],
) -> tuple[list[dict], int, list[str]]:
    """Validate Groq output strictly. Drop invalid findings.

    Returns (valid_findings, dropped_count, drop_reasons).

    Validation order (§17.5):
    1. Response parsed as JSON (already done by adapter)
    2. Conforms to expected structure (already done by adapter)
    3. Every supporting_evidence_id exists in the evidence set
    4. Every finding has at least one valid supporting evidence id
    5. finding_type in allowed enum
    6. Scores in [0, 100]
    7. No fabricated URLs in text fields
    """
    valid: list[dict] = []
    dropped = 0
    reasons: list[str] = []

    for f in result.findings:
        # 3. Validate evidence IDs
        supplied_ids = f.get("supporting_evidence_ids", [])
        valid_ids = [eid for eid in supplied_ids if eid in evidence_ids]
        invalid_ids = [eid for eid in supplied_ids if eid not in evidence_ids]

        if invalid_ids:
            logger.warning(
                f"Groq hallucination: finding references unknown evidence ids: {invalid_ids}"
            )
            reasons.append(f"unknown_evidence_ids: {invalid_ids}")

        # 4. Must have at least one valid evidence ID
        if not valid_ids:
            logger.warning(f"Groq: dropping finding with zero valid evidence ids: {f.get('title', '?')}")
            reasons.append(f"zero_valid_evidence: {f.get('title', '?')}")
            dropped += 1
            continue

        f["supporting_evidence_ids"] = valid_ids

        # 5. Validate finding_type
        ftype = f.get("finding_type", "other")
        if ftype not in VALID_FINDING_TYPES:
            logger.warning(f"Groq: unknown finding_type '{ftype}', coercing to 'other'")
            f["finding_type"] = "other"

        # 6. Clamp scores
        for score_key in ("importance_score", "ai_confidence"):
            val = f.get(score_key, 0)
            if not isinstance(val, (int, float)):
                val = 0
            f[score_key] = max(0, min(100, int(val)))

        # 7. Check for fabricated URLs in text fields
        import re
        fabricated = False
        for text_field in ("summary", "why_it_matters", "opportunity"):
            text = f.get(text_field) or ""
            urls_in_text = re.findall(r"https?://[^\s)\"'>]+", text)
            for url in urls_in_text:
                if url not in evidence_urls:
                    logger.warning(f"Groq hallucination: fabricated URL '{url}' in {text_field}")
                    reasons.append(f"fabricated_url: {url}")
                    fabricated = True

        if fabricated:
            dropped += 1
            continue

        # Truncation checks
        title = f.get("title", "")
        if len(title) > 140:
            f["title"] = title[:140]
        summary = f.get("summary", "")
        if len(summary) > 600:
            f["summary"] = summary[:600]

        valid.append(f)

    if dropped > 0:
        logger.warning(f"Groq validation: {dropped} findings dropped, reasons: {reasons}")

    return valid, dropped, reasons


def build_analysis_payload(
    evidence_list: list[Evidence],
    brand: str,
    market: str,
    research_type: str,
    objective: str | None,
    lookback_days: int,
) -> AnalysisPayload:
    """Build the payload sent to Groq from filtered evidence.

    Only RELEVANT (and conditionally UNCERTAIN) evidence is included.
    Evidence is trimmed to the fields Groq needs.
    Token budget: cap at ~40 items × 1500 chars.
    """
    # Filter to RELEVANT + conditionally UNCERTAIN
    relevant = [e for e in evidence_list if e.relevance == Relevance.RELEVANT]
    uncertain = [e for e in evidence_list if e.relevance == Relevance.UNCERTAIN]

    # Include UNCERTAIN only if relevant set is thin (< 5)
    if len(relevant) < 5:
        relevant.extend(uncertain)

    # Sort by relevance_score descending
    relevant.sort(key=lambda e: e.relevance_score, reverse=True)

    # Cap at ~40 items
    MAX_EVIDENCE_ITEMS = 40
    truncated = len(relevant) > MAX_EVIDENCE_ITEMS
    relevant = relevant[:MAX_EVIDENCE_ITEMS]

    evidence_dicts: list[dict] = []
    for e in relevant:
        evidence_dicts.append({
            "id": e.id,
            "source_name": e.source_name,
            "source_quality_tier": e.source_quality,
            "title": e.title,
            "url": e.url,
            "published_at": e.published_at.isoformat() if e.published_at else None,
            "content_excerpt": (e.content or "")[:1500],
            "change_status": e.change_status.value if hasattr(e.change_status, 'value') else str(e.change_status),
        })

    context = {
        "brand": brand,
        "market": market,
        "research_type": research_type,
        "objective": objective or "",
        "lookback_days": lookback_days,
    }

    payload = AnalysisPayload(context=context, evidence=evidence_dicts)

    if truncated:
        logger.info(f"Groq payload truncated to {MAX_EVIDENCE_ITEMS} evidence items")

    return payload
