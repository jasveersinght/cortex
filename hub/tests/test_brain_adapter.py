from __future__ import annotations

import sys
import types

import pytest

from hands.db import insert_dynamic, table_exists

from ..brain_adapter import AdapterError, BrainAdapter
from ..config import HubSettings


def _settings(**over):
    base = dict(content_agent_url="", research_agent_url="", hands_api_url="", brain_path="",
               brain_compliance_func="fake_brain:run_compliance", brain_decision_func="",
               supabase_content_url="", supabase_content_key="", supabase_compliance_url="", supabase_compliance_key="",
               content_context_field="", hub_api_key="", sync_interval_seconds=120)
    base.update(over)
    return HubSettings(**base)


@pytest.fixture(autouse=True)
def fake_brain_module():
    mod = types.ModuleType("fake_brain")

    def run_compliance(asset_id, brand, platform, region, body_text, conn):
        conn.execute("INSERT INTO lens_scores (asset_id, lens_name, score, reason) VALUES (?,?,?,?)",
                     (asset_id, "claims", 88, "clean"))
        conn.execute("UPDATE assets SET tier='highly_recommended', confidence_score=88 WHERE id=?", (asset_id,))
        return {"tier": "highly_recommended"}

    mod.run_compliance = run_compliance
    sys.modules["fake_brain"] = mod
    yield
    del sys.modules["fake_brain"]


def test_run_compliance_calls_the_real_brain_function_and_reads_results_back(conn):
    aid = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "LinkedIn", "region": "Singapore",
                                          "body_text": "Cover for stock in transit.", "status": "pending"})
    result = BrainAdapter(_settings()).run_compliance(conn, aid)
    assert result["tier"] == "highly_recommended"
    assert result["lens_scores"]["claims"]["score"] == 88


def test_missing_function_config_raises_clear_error(conn):
    aid = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "LinkedIn", "region": "Singapore", "body_text": "x", "status": "pending"})
    with pytest.raises(AdapterError, match="not configured"):
        BrainAdapter(_settings(brain_compliance_func="")).run_compliance(conn, aid)


def test_decision_fallback_writes_status_and_lesson_and_approval_receipt(conn):
    aid = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "LinkedIn", "region": "Singapore",
                                          "body_text": "Cover for stock in transit.", "status": "pending", "tier": "recommended_review"})
    out = BrainAdapter(_settings()).record_decision(conn, aid, "approved", "Aisha")
    assert out["approval_receipt"] is True
    assert conn.execute("SELECT status FROM assets WHERE id=?", (aid,)).fetchone()[0] == "approved"

    aid2 = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "X", "region": "Singapore", "body_text": "y", "status": "pending"})
    BrainAdapter(_settings()).record_decision(conn, aid2, "rejected", "Aisha", tag="too salesy", note="pushy CTA")
    lesson = conn.execute("SELECT * FROM lessons_learned WHERE asset_id=?", (aid2,)).fetchone()
    assert lesson["tag"] == "too salesy" and conn.execute("SELECT status FROM assets WHERE id=?", (aid2,)).fetchone()[0] == "rejected"


def test_decision_requires_reviewer_and_tag_when_needed(conn):
    aid = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "LinkedIn", "region": "Singapore", "body_text": "x", "status": "pending"})
    with pytest.raises(AdapterError, match="reviewer"):
        BrainAdapter(_settings()).record_decision(conn, aid, "approved", "")
    with pytest.raises(AdapterError, match="reason tag"):
        BrainAdapter(_settings()).record_decision(conn, aid, "rejected", "Aisha")
