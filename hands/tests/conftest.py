from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hands.approvals import record_approval
from hands.bridge.brain_stub import ensure_brain_tables
from hands.config import get_settings
from hands.db import connect, init_schema, insert_dynamic
from hands.providers import MockProvider

# Monday 2026-09-21 10:00 in Singapore
NOW = datetime(2026, 9, 21, 2, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    for key in ("DRY_RUN", "GEMINI_API_KEY", "HANDS_API_KEY", "ENABLE_WORKER", "PUBLIC_MEDIA_BASE_URL", "MOCK_FAIL_RATE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PROVIDER", "mock")
    monkeypatch.setenv("SCORE_MIN_AGE_HOURS", "0")
    c = connect()
    ensure_brain_tables(c)
    init_schema(c)
    yield c
    c.close()


@pytest.fixture
def settings(conn):
    return get_settings()


@pytest.fixture
def provider():
    return MockProvider()


def add_asset(conn, *, brand="Jade", platform="LinkedIn", body="Protect your stock while it moves between vaults and showrooms.",
              region="Singapore", status="approved", tier="highly_recommended", approve=True, approver="Aisha (reviewer)"):
    asset_id = insert_dynamic(conn, "assets", {
        "brand": brand, "platform": platform, "content_type": "caption", "region": region,
        "body_text": body, "status": status, "tier": tier, "confidence_score": 90,
    })
    if approve:
        record_approval(conn, asset_id, approver)
    return asset_id
