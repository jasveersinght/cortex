from __future__ import annotations

import sys
import types
from unittest.mock import patch

from fastapi.testclient import TestClient

from .. import api
from ..content_client import ContentClient


def fake_brain(monkeypatch):
    mod = types.ModuleType("fake_brain2")

    def run_compliance(asset_id, brand, platform, region, body_text, conn):
        conn.execute("UPDATE assets SET tier='highly_recommended', confidence_score=90 WHERE id=?", (asset_id,))
        return {"tier": "highly_recommended"}

    mod.run_compliance = run_compliance
    sys.modules["fake_brain2"] = mod
    monkeypatch.setenv("BRAIN_COMPLIANCE_FUNC", "fake_brain2:run_compliance")


def test_health_reports_component_status(conn, monkeypatch):
    monkeypatch.setenv("DB_PATH", conn.execute("PRAGMA database_list").fetchone()["file"])
    with TestClient(api.app) as client:
        r = client.get("/health").json()
        assert "content_agent_reachable" in r and r["content_supabase_configured"] is False


def test_generate_endpoint_runs_the_full_chain(monkeypatch, tmp_path):
    from hands.db import connect as _connect
    from hands.bridge.brain_stub import ensure_brain_tables as _ensure

    monkeypatch.setenv("DB_PATH", str(tmp_path / "api_test.db"))
    _c = _connect()
    _ensure(_c)
    _c.close()
    fake_brain(monkeypatch)
    response = {"data": {"linkedin": {"post": "Copy about cover."}}}
    with TestClient(api.app) as client, patch.object(ContentClient, "generate", return_value=(response, 300)):
        out = client.post("/generate", json={"request": {"brand": "Jade"}, "brand": "Jade", "region": "Singapore"}).json()
    assert out["ok"] and out["assets_created"][0]["platform"] == "LinkedIn"
    assert out["compliance"][0]["tier"] == "highly_recommended"


def test_decision_endpoint_requires_reviewer(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api_test2.db"))
    from hands.db import connect, init_schema
    from hands.bridge.brain_stub import ensure_brain_tables
    from hands.db import insert_dynamic

    c = connect()
    init_schema(c)
    ensure_brain_tables(c)
    aid = insert_dynamic(c, "assets", {"brand": "Jade", "platform": "X", "region": "Singapore", "body_text": "x", "status": "pending"})
    c.close()
    with TestClient(api.app) as client:
        r = client.post(f"/assets/{aid}/decision", json={"decision": "approved", "reviewer": ""})
    assert r.status_code == 422


def test_api_key_protects_generate_but_not_health(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api_test3.db"))
    monkeypatch.setenv("HUB_API_KEY", "s3cret")
    with TestClient(api.app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/generate", json={"request": {}, "brand": "Jade"}).status_code == 401
