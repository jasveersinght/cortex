from __future__ import annotations

from unittest.mock import patch

from ..config import HubSettings
from ..content_client import ContentClient
from ..content_store import save_generation
from ..orchestrator import generate_and_process
from ..supabase_rest import SupabaseRest

RESPONSE = {"data": {"linkedin": {"post": "LinkedIn copy about jewellers block."}, "x": {"tweet": "X copy about cover."}}}


def _settings():
    return HubSettings(content_agent_url="http://demo.invalid", research_agent_url="", hands_api_url="",
                       brain_path="", brain_compliance_func="", brain_decision_func="",
                       supabase_content_url="", supabase_content_key="", supabase_compliance_url="", supabase_compliance_key="",
                       content_context_field="", hub_api_key="", sync_interval_seconds=120)


class FakeSb:
    enabled = True

    def __init__(self):
        self.sent = []

    def upsert(self, table, rows, on_conflict):
        self.sent.append((table, rows))
        return rows


def test_generate_and_process_creates_assets_and_stores_content(conn):
    sb = FakeSb()
    with patch.object(ContentClient, "generate", return_value=(RESPONSE, 500)):
        out = generate_and_process(conn, _settings(), ContentClient("http://demo.invalid"), sb, FakeSb(),
                                    request_body={"brand": "Jade"}, brand="Jade", region="Singapore", run_compliance=False)
    assert out["ok"] and out["stored_in_supabase"] is True
    assert {a["platform"] for a in out["assets_created"]} == {"LinkedIn", "X"}
    assert conn.execute("SELECT COUNT(*) FROM assets WHERE status='pending'").fetchone()[0] == 2
    gen_rows = [r for t, r in sb.sent if t == "content_generations"][0]
    assert gen_rows[0]["brand"] == "Jade" and gen_rows[0]["latency_ms"] == 500
    item_rows = [r for t, r in sb.sent if t == "content_items"][0]
    assert {i["platform"] for i in item_rows} == {"LinkedIn", "X"}


def test_content_agent_failure_is_reported_not_raised(conn):
    from ..content_client import ContentAgentError

    with patch.object(ContentClient, "generate", side_effect=ContentAgentError("connection refused")):
        out = generate_and_process(conn, _settings(), ContentClient("http://demo.invalid"), FakeSb(), FakeSb(),
                                    request_body={}, brand="Jade")
    assert out["ok"] is False and out["stage"] == "content_agent"
    assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0


def test_save_generation_queues_locally_when_supabase_is_down(conn):
    from ..supabase_rest import SupabaseError

    class Down:
        enabled = True

        def upsert(self, *a, **k):
            raise SupabaseError("down")

    out = save_generation(conn, Down(), brand="Jade", region="Singapore", request_body={}, response={}, latency_ms=1,
                          items=[{"platform": "LinkedIn", "body_text": "hi"}])
    assert out["stored_in_supabase"] is False and out["queued_for_retry"] is True
    assert conn.execute("SELECT COUNT(*) FROM hub_outbox").fetchone()[0] == 2
