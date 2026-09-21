"""FastAPI endpoint integration tests and security secret-leak tests.

Covers:
- GET /health
- POST /discover/run (validation errors -> 422)
- POST /discover/run (cache hit -> 200, new run -> 201, in-flight -> 202)
- GET /discover/{run_id} (found -> 200, missing -> 404)
- GET /discover/{run_id}/findings
- GET /discover/{run_id}/evidence
- GET /discover/status
- Security: verify no API secrets leak into any response body or headers
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.research.models import ResearchResult, Finding, Evidence
from app.research.enums import FindingType, ChangeStatus, Relevance, SourceType


client = TestClient(app)


class TestHealthEndpoint:

    def test_health_check_structure(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "supabase" in data
        assert "tavily" in data
        assert "groq" in data


class TestDiscoverRunEndpoint:

    def test_validation_error_missing_brand(self):
        payload = {
            "market": "Singapore",
            "research_type": "competitor_monitoring",
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 422
        assert "error" in response.json()

    def test_validation_error_invalid_market(self):
        payload = {
            "brand": "Jaguar Transit",
            "market": "Tokyo",  # Not in JA Assure markets
            "research_type": "competitor_monitoring",
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 422

    def test_validation_error_invalid_research_type(self):
        payload = {
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "invalid_type",
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 422

    @patch("app.api.routes.discover._get_manager")
    def test_run_success_new_run_returns_201(self, mock_get_manager):
        run_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.run.return_value = ResearchResult(
            research_run_id=run_id,
            brand="Jaguar Transit",
            market="Singapore",
            research_type="competitor_monitoring",
            objective="Identify recent competitor activity",
            lookback_days=30,
            status="COMPLETED",
            cache_hit=False,
            findings=[
                Finding(
                    id=uuid4(),
                    title="Test Finding",
                    finding_type=FindingType.SERVICE_LAUNCH,
                    change_status=ChangeStatus.NEW,
                    supporting_evidence_ids=["evidence_001"],
                    created_at=datetime.now(timezone.utc),
                )
            ],
        )
        mock_get_manager.return_value = mock_manager

        payload = {
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
            "objective": "Identify recent competitor activity",
            "lookback_days": 30,
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["cache_hit"] is False
        assert data["status"] == "COMPLETED"
        assert data["lookback_days"] == 30
        assert data["objective"] == "Identify recent competitor activity"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["created_at"] is not None

    @patch("app.api.routes.discover._get_manager")
    def test_run_cache_hit_returns_200(self, mock_get_manager):
        run_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.run.return_value = ResearchResult(
            research_run_id=run_id,
            brand="Jaguar Transit",
            market="Singapore",
            research_type="competitor_monitoring",
            status="COMPLETED",
            cache_hit=True,
        )
        mock_get_manager.return_value = mock_manager

        payload = {
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is True

    @patch("app.api.routes.discover._get_manager")
    def test_run_inflight_returns_202(self, mock_get_manager):
        run_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.run.return_value = ResearchResult(
            research_run_id=run_id,
            status="IN_FLIGHT",
        )
        mock_get_manager.return_value = mock_manager

        payload = {
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "IN_FLIGHT"


class TestDetailEndpoints:

    @patch("app.api.routes.discover._get_repo")
    def test_get_run_not_found(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_run.return_value = None
        mock_get_repo.return_value = mock_repo

        missing_id = uuid4()
        response = client.get(f"/discover/{missing_id}")
        assert response.status_code == 404
        assert "RESEARCH_RUN_NOT_FOUND" in response.json()["error"]["code"]

    @patch("app.api.routes.discover._get_repo")
    def test_get_run_found(self, mock_get_repo):
        run_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_run.return_value = {
            "id": str(run_id),
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
            "status": "COMPLETED",
            "lookback_days": 30,
            "sources_checked": 10,
        }
        mock_repo.get_findings_for_run.return_value = [
            {
                "id": str(uuid4()),
                "finding_type": "service_launch",
                "title": "Service Launch",
                "summary": "Summary",
                "why_it_matters": "Why",
                "supporting_evidence_ids": [],
                "created_at": "2026-09-16T10:00:00Z",
            }
        ]
        mock_get_repo.return_value = mock_repo

        response = client.get(f"/discover/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["brand"] == "Jaguar Transit"
        assert data["sources_checked"] == 10
        assert data["lookback_days"] == 30
        assert len(data["findings"]) == 1
        assert data["findings"][0]["created_at"] is not None

    @patch("app.api.routes.discover._get_repo")
    def test_get_findings_endpoint(self, mock_get_repo):
        run_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_run.return_value = {"id": str(run_id)}
        mock_repo.get_findings_for_run.return_value = [
            {
                "id": str(uuid4()),
                "finding_type": "partnership",
                "title": "Bank Partnership",
                "summary": "Partnered with Bank",
                "why_it_matters": "Increases reach",
                "supporting_evidence_ids": ["evidence_001"],
                "importance_score": 80,
                "confidence_score": 75,
                "change_status": "NEW",
                "created_at": "2026-09-16T10:00:00Z",
            }
        ]
        mock_repo.get_evidence_for_run.return_value = [
            {
                "evidence_ref": "evidence_001",
                "title": "News Title",
                "url": "https://example.com/news",
                "source_name": "example.com",
                "source_quality": 3,
            }
        ]
        mock_get_repo.return_value = mock_repo

        response = client.get(f"/discover/{run_id}/findings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Bank Partnership"
        assert data[0]["created_at"] is not None
        assert len(data[0]["supporting_evidence"]) == 1
        assert data[0]["supporting_evidence"][0]["evidence_ref"] == "evidence_001"

    @patch("app.api.routes.discover._get_repo")
    def test_get_evidence_endpoint(self, mock_get_repo):
        run_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_run.return_value = {"id": str(run_id)}
        mock_repo.get_evidence_for_run.return_value = [
            {
                "id": str(uuid4()),
                "evidence_ref": "evidence_001",
                "source_type": "news",
                "source_name": "straitstimes.com",
                "source_quality": 3,
                "title": "Article Title",
                "url": "https://straitstimes.com/article",
                "market": "Singapore",
                "query": "query",
                "tavily_operation": "search",
                "relevance": "RELEVANT",
                "relevance_score": 0.85,
                "change_status": "NEW",
                "content": "Full article content snippet...",
            }
        ]
        mock_get_repo.return_value = mock_repo

        response = client.get(f"/discover/{run_id}/evidence")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["evidence_ref"] == "evidence_001"
        assert data[0]["relevance"] == "RELEVANT"

    @patch("app.api.routes.discover._get_repo")
    def test_get_status_endpoint(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_latest_runs_status.return_value = [
            {
                "id": str(uuid4()),
                "brand": "Jaguar Transit",
                "market": "Singapore",
                "research_type": "competitor_monitoring",
                "status": "COMPLETED",
                "new_findings": 2,
                "changed_findings": 1,
                "unchanged_findings": 0,
            }
        ]
        mock_get_repo.return_value = mock_repo

        response = client.get("/discover/status")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["brand"] == "Jaguar Transit"
        assert data[0]["findings_count"] == 3


class TestSecuritySecretsExposure:

    def test_no_secrets_in_responses(self):
        """Assert that no response body or headers leak configured secret values."""
        secrets_to_check = [
            settings.TAVILY_API_KEY,
            settings.GROQ_API_KEY,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        ]

        # Test health endpoint
        r = client.get("/health")
        for s in secrets_to_check:
            if s:
                assert s not in r.text
                assert not any(s in v for v in r.headers.values())

        # Test validation error response
        r = client.post("/discover/run", json={})
        for s in secrets_to_check:
            if s:
                assert s not in r.text
                assert not any(s in v for v in r.headers.values())


class TestFixRegressions:
    """Regression tests for R1 (created_at timestamp) and R3 (lookback_days mapping)."""

    @patch("app.api.routes.discover._get_manager")
    def test_regression_r3_lookback_days_in_post_run(self, mock_get_manager):
        """Verify POST /discover/run returns lookback_days matching the request."""
        run_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.run.return_value = ResearchResult(
            research_run_id=run_id,
            brand="Jaguar Transit",
            market="Singapore",
            research_type="competitor_monitoring",
            objective="Identify recent competitor activity",
            lookback_days=45,
            status="COMPLETED",
        )
        mock_get_manager.return_value = mock_manager

        payload = {
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
            "objective": "Identify recent competitor activity",
            "lookback_days": 45,
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["lookback_days"] == 45
        assert data["objective"] == "Identify recent competitor activity"

    @patch("app.api.routes.discover._get_manager")
    def test_regression_r1_finding_created_at_in_post_run(self, mock_get_manager):
        """Verify POST /discover/run returns non-null created_at on findings."""
        now = datetime.now(timezone.utc)
        run_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.run.return_value = ResearchResult(
            research_run_id=run_id,
            brand="Jaguar Transit",
            market="Singapore",
            research_type="competitor_monitoring",
            status="COMPLETED",
            findings=[
                Finding(
                    id=uuid4(),
                    title="Verified Finding",
                    finding_type=FindingType.PARTNERSHIP,
                    change_status=ChangeStatus.NEW,
                    created_at=now,
                )
            ],
        )
        mock_get_manager.return_value = mock_manager

        payload = {
            "brand": "Jaguar Transit",
            "market": "Singapore",
            "research_type": "competitor_monitoring",
        }
        response = client.post("/discover/run", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert len(data["findings"]) == 1
        assert data["findings"][0]["created_at"] is not None
        # Must be valid ISO string parsable by datetime
        parsed = datetime.fromisoformat(data["findings"][0]["created_at"])
        assert parsed is not None

    @patch("app.api.routes.discover._get_repo")
    def test_regression_r1_finding_created_at_in_get_findings(self, mock_get_repo):
        """Verify GET /discover/{id}/findings returns non-null created_at."""
        run_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_run.return_value = {"id": str(run_id)}
        mock_repo.get_findings_for_run.return_value = [
            {
                "id": str(uuid4()),
                "finding_type": "partnership",
                "title": "Bank Partnership",
                "summary": "Partnered with Bank",
                "why_it_matters": "Increases reach",
                "supporting_evidence_ids": [],
                "importance_score": 80,
                "confidence_score": 75,
                "change_status": "NEW",
                "created_at": "2026-09-16T10:15:30.123456+00:00",
            }
        ]
        mock_repo.get_evidence_for_run.return_value = []
        mock_get_repo.return_value = mock_repo

        response = client.get(f"/discover/{run_id}/findings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["created_at"] == "2026-09-16T10:15:30.123456Z" or "2026-09-16T10:15:30.123456" in data[0]["created_at"]

