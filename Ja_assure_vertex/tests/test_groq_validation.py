"""Tests for Groq output validation (hallucination prevention)."""

import pytest
from app.research.adapters.groq import validate_groq_output
from app.research.models import AnalysisResult


class TestGroqOutputValidation:

    def _make_result(self, findings: list[dict]) -> AnalysisResult:
        return AnalysisResult(findings=findings)

    def test_valid_finding_passes(self):
        findings = [{
            "finding_type": "product_launch",
            "title": "Test finding",
            "summary": "A valid summary",
            "why_it_matters": "Relevant to brand",
            "opportunity": None,
            "entities": ["CompA"],
            "importance_score": 80,
            "ai_confidence": 70,
            "supporting_evidence_ids": ["evidence_001"],
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, dropped, reasons = validate_groq_output(
            result,
            evidence_ids={"evidence_001"},
            evidence_urls={"https://example.com"},
        )
        assert len(valid) == 1
        assert dropped == 0

    def test_unknown_evidence_id_dropped(self):
        """Finding referencing a nonexistent evidence id is dropped."""
        findings = [{
            "finding_type": "product_launch",
            "title": "Bad finding",
            "summary": "References fake evidence",
            "why_it_matters": "Test",
            "supporting_evidence_ids": ["evidence_999"],  # doesn't exist
            "importance_score": 50,
            "ai_confidence": 50,
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, dropped, reasons = validate_groq_output(
            result,
            evidence_ids={"evidence_001"},
            evidence_urls=set(),
        )
        assert len(valid) == 0
        assert dropped == 1

    def test_fabricated_url_dropped(self):
        """Finding with a URL not in evidence set is dropped."""
        findings = [{
            "finding_type": "product_launch",
            "title": "Bad finding",
            "summary": "See https://fabricated.com/fake for details",
            "why_it_matters": "Test",
            "supporting_evidence_ids": ["evidence_001"],
            "importance_score": 50,
            "ai_confidence": 50,
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, dropped, reasons = validate_groq_output(
            result,
            evidence_ids={"evidence_001"},
            evidence_urls={"https://example.com"},
        )
        assert len(valid) == 0
        assert dropped == 1

    def test_unknown_finding_type_coerced(self):
        """Unknown finding type is coerced to 'other', not dropped."""
        findings = [{
            "finding_type": "alien_invasion",
            "title": "Test",
            "summary": "Summary",
            "why_it_matters": "Why",
            "supporting_evidence_ids": ["evidence_001"],
            "importance_score": 50,
            "ai_confidence": 50,
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, dropped, _ = validate_groq_output(
            result,
            evidence_ids={"evidence_001"},
            evidence_urls=set(),
        )
        assert len(valid) == 1
        assert valid[0]["finding_type"] == "other"

    def test_score_clamping(self):
        """Out-of-range scores are clamped to [0, 100]."""
        findings = [{
            "finding_type": "product_launch",
            "title": "Test",
            "summary": "Summary",
            "why_it_matters": "Why",
            "supporting_evidence_ids": ["evidence_001"],
            "importance_score": 150,
            "ai_confidence": -10,
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, _, _ = validate_groq_output(
            result,
            evidence_ids={"evidence_001"},
            evidence_urls=set(),
        )
        assert valid[0]["importance_score"] == 100
        assert valid[0]["ai_confidence"] == 0

    def test_partially_valid_ids(self):
        """Finding with mix of valid and invalid ids: invalid are removed, finding kept if ≥1 valid."""
        findings = [{
            "finding_type": "product_launch",
            "title": "Test",
            "summary": "Summary",
            "why_it_matters": "Why",
            "supporting_evidence_ids": ["evidence_001", "evidence_999"],
            "importance_score": 70,
            "ai_confidence": 60,
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, dropped, _ = validate_groq_output(
            result,
            evidence_ids={"evidence_001"},
            evidence_urls=set(),
        )
        assert len(valid) == 1
        assert valid[0]["supporting_evidence_ids"] == ["evidence_001"]

    def test_empty_findings_passes(self):
        result = AnalysisResult(findings=[], insufficient_evidence=True)
        valid, dropped, _ = validate_groq_output(result, set(), set())
        assert len(valid) == 0
        assert dropped == 0

    def test_title_truncation(self):
        """Titles longer than 140 chars are truncated."""
        findings = [{
            "finding_type": "other",
            "title": "x" * 200,
            "summary": "Summary",
            "why_it_matters": "Why",
            "supporting_evidence_ids": ["evidence_001"],
            "importance_score": 50,
            "ai_confidence": 50,
            "conflicts": [],
        }]
        result = self._make_result(findings)
        valid, _, _ = validate_groq_output(result, {"evidence_001"}, set())
        assert len(valid[0]["title"]) == 140
