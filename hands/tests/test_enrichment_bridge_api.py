from __future__ import annotations

from fastapi.testclient import TestClient

from hands import enrichment
from hands.api import app
from hands.bridge.content_ingest import extract_text, ingest_content_output
from hands.config import get_settings
from hands.db import get_asset
from hands.platform_rules import rule_for

from .conftest import add_asset


# ------------------------------------------------------------------ enrichment
def test_gemini_hashtags_are_sanitised_and_claims_screened(conn, settings, monkeypatch):
    monkeypatch.setattr(enrichment, "_gemini_hashtags", lambda prompt, s: ["#Guaranteed", "jewellery insurance!", "#InsurTech", "#insurtech", "#100Percent", "#SafeTransit"])
    aid = add_asset(conn)
    en = enrichment.enrich(conn, get_asset(conn, aid), "linkedin", rule_for("linkedin", settings), settings)
    assert en.source == "gemini"
    assert en.hashtags == ["#jewelleryinsurance", "#InsurTech", "#SafeTransit"]
    assert set(en.dropped) == {"#Guaranteed", "#100Percent"}


def test_heuristic_fallback_is_brand_aware_and_clean(conn, settings):
    aid = add_asset(conn, brand="DoctorShield")
    en = enrichment.enrich(conn, get_asset(conn, aid), "linkedin", rule_for("linkedin", settings), settings)
    assert en.source == "heuristic" and "#MedicalIndemnity" in en.hashtags and "#Singapore" in en.hashtags
    assert all(len(t) > 1 for t in en.hashtags)


def test_enrichment_can_be_switched_off(conn, monkeypatch):
    monkeypatch.setenv("ENRICHMENT_MODE", "off")
    s = get_settings()
    aid = add_asset(conn)
    assert enrichment.enrich(conn, get_asset(conn, aid), "linkedin", rule_for("linkedin", s), s).hashtags == []


# ------------------------------------------------------------------ bridge
def test_extract_text_handles_the_shapes_a_prompt_can_return():
    assert extract_text("plain") == "plain"
    assert extract_text({"post": "A", "hashtags": ["#x"]}) == "A"
    assert extract_text({"hook": "H", "body": "B", "cta": "C", "hashtags": ["#x"]}) == "H\n\nB\n\nC"
    assert extract_text({"caption": {"text": "nested"}}) == "nested"
    assert extract_text({}) == ""


def test_ingest_creates_pending_assets_and_attaches_video(conn):
    payload = {"success": True, "agent": "content", "data": {
        "campaign": {"title": "ignored"}, "messaging": {"core_message": "ignored"},
        "linkedin": {"post": "LinkedIn copy"}, "instagram": {"caption": "IG copy"}, "x": {"tweet": "X copy"}, "ab_variants": []}}
    created = ingest_content_output(conn, payload, brand="Jade", region="Singapore", video_url="https://cdn.example.com/reel.mp4")
    assert [c["platform"] for c in created] == ["LinkedIn", "Instagram", "X"]
    assert created[1]["media"] == "video" and created[0]["media"] is None
    a = get_asset(conn, created[0]["asset_id"])
    assert a["status"] == "pending" and a["body_text"] == "LinkedIn copy" and a["brand"] == "Jade"


# ------------------------------------------------------------------ API
def test_api_end_to_end(conn, monkeypatch):
    aid = add_asset(conn, approve=False)
    with TestClient(app) as api:
        assert api.get("/health").json()["provider"]["provider"] == "mock"

        # no receipt yet -> the Hands refuses
        r = api.post(f"/preflight/{aid}").json()
        assert r["platforms"]["linkedin"]["action"] == "block"

        assert api.post(f"/approvals/{aid}", json={"approved_by": "Aisha"}).status_code == 200
        assert api.post(f"/preflight/{aid}").json()["platforms"]["linkedin"]["action"] == "pass"

        run = api.post("/publish/run").json()
        assert len(run["intake"]["created"]) == 1 and run["results"][0]["status"] == "scheduled"

        q = api.get("/queue").json()
        assert q[0]["status"] == "scheduled" and q[0]["hashtags"]
        detail = api.get(f"/jobs/{q[0]['id']}").json()
        assert [g["name"] for g in detail["preflight"]["gates"]] == ["approval", "integrity", "platform_fit", "safety"]

        assert api.post(f"/jobs/{q[0]['id']}/retry").status_code == 409          # scheduled jobs cannot be retried
        assert api.get("/summary").json()["jobs_by_status"] == {"scheduled": 1}
        assert api.get("/insights", params={"brand": "Jade"}).json()["prompt_block"] == ""
        assert api.get("/audit").json()
        assert api.post("/approvals/9999", json={"approved_by": "x"}).status_code == 404


def test_api_key_protects_mutations_only(conn, monkeypatch):
    monkeypatch.setenv("HANDS_API_KEY", "s3cret")
    with TestClient(app) as api:
        assert api.get("/health").status_code == 200
        assert api.post("/killswitch", json={"on": True}).status_code == 401
        assert api.post("/killswitch", json={"on": True}, headers={"X-Hands-Key": "s3cret"}).json() == {"kill_switch": "on"}
        assert api.get("/killswitch").json() == {"kill_switch": "on"}


def test_kill_switch_via_api_stops_publishing(conn):
    add_asset(conn)
    with TestClient(app) as api:
        api.post("/killswitch", json={"on": True})
        run = api.post("/publish/run").json()
        assert run["results"][0]["status"] == "deferred"
        api.post("/killswitch", json={"on": False})
