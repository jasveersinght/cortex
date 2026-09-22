"""The Brain's real schema.sql may use UUID text ids instead of integers. Hands must cope with both."""
from __future__ import annotations

from datetime import timedelta

from hands.approvals import record_approval
from hands.config import get_settings
from hands.db import connect, init_schema, insert_dynamic
from hands.pipeline import run_metrics_cycle, run_publish_cycle
from hands.providers import MockProvider
from hands.providers.base import ProviderMetrics

from .conftest import NOW


class Fixed(MockProvider):
    def fetch_metrics(self, post_id, platform):
        return ProviderMetrics(status="sent", impressions=3000, likes=300, comments=60, shares=40, clicks=60)


def test_full_loop_with_uuid_text_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "uuid.db"))
    monkeypatch.setenv("PROVIDER", "mock")
    monkeypatch.setenv("SCORE_MIN_AGE_HOURS", "0")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    conn = connect()
    conn.executescript(
        "CREATE TABLE assets (id TEXT PRIMARY KEY, brand TEXT NOT NULL, platform TEXT, content_type TEXT, region TEXT, "
        "body_text TEXT NOT NULL, status TEXT, tier TEXT, confidence_score REAL, created_at TEXT);"
        "CREATE TABLE lessons_learned (id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, tag TEXT, note TEXT, created_at TEXT);"
    )
    init_schema(conn)
    aid = insert_dynamic(conn, "assets", {"brand": "Jaguar Transit", "platform": "LinkedIn", "region": "Malaysia",
                                          "body_text": "Cargo in transit deserves a plan.", "status": "approved", "tier": "highly_recommended"})
    assert isinstance(aid, str) and len(aid) == 32
    record_approval(conn, aid, "Reviewer")
    s, p = get_settings(), Fixed()
    run_publish_cycle(conn, p, s, NOW)
    assert conn.execute("SELECT status FROM publish_jobs").fetchone()[0] == "scheduled"
    run_metrics_cycle(conn, p, s, NOW + timedelta(days=15))
    lesson = conn.execute("SELECT * FROM lessons_learned").fetchone()
    assert lesson["tag"] == "perf:top_performer" and lesson["asset_id"] == aid and len(lesson["id"]) == 32
    conn.close()
