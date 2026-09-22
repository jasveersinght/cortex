from __future__ import annotations

from datetime import timedelta

from hands import audit
from hands.approvals import record_approval
from hands.config import get_settings
from hands.db import get_asset, set_flag
from hands.intake import sync_approved
from hands.media import set_media
from hands.pipeline import preview_preflight, run_publish_cycle
from hands.providers import MockProvider
from hands.providers.base import PermanentProviderError, TransientProviderError
from hands.publisher import claim, publish_due, recover_stale

from .conftest import NOW, add_asset


def job_of(conn, asset_id, platform=None):
    sql = "SELECT * FROM publish_jobs WHERE asset_id=?" + (" AND platform=?" if platform else "")
    return conn.execute(sql, (str(asset_id), platform) if platform else (str(asset_id),)).fetchone()


# ---------------------------------------------------------------- happy path
def test_approved_asset_is_scheduled_with_receipt(conn, settings, provider):
    aid = add_asset(conn)
    out = run_publish_cycle(conn, provider, settings, NOW)
    assert len(out["intake"]["created"]) == 1
    job = job_of(conn, aid)
    assert job["status"] == "scheduled"
    assert job["external_post_id"].startswith("mock_")
    assert job["submitted_at"] and job["provider"] == "mock"
    assert job["hashtags_json"] and "#" in job["final_text"]
    assert job["final_text"].startswith("Protect your stock")     # body untouched, hashtags appended


def test_second_run_never_double_posts(conn, settings, provider):
    add_asset(conn)
    run_publish_cycle(conn, provider, settings, NOW)
    again = run_publish_cycle(conn, provider, settings, NOW + timedelta(minutes=5))
    assert again["intake"]["created"] == [] and again["results"] == []
    assert conn.execute("SELECT COUNT(*) FROM publish_jobs").fetchone()[0] == 1


def test_multi_platform_asset_fans_out(conn, settings, provider):
    aid = add_asset(conn, platform="LinkedIn, X")
    run_publish_cycle(conn, provider, settings, NOW)
    platforms = {r["platform"] for r in conn.execute("SELECT platform FROM publish_jobs WHERE asset_id=?", (str(aid),))}
    assert platforms == {"linkedin", "x"}


def test_pending_and_rejected_assets_are_ignored(conn, settings, provider):
    add_asset(conn, status="pending", approve=False)
    add_asset(conn, status="rejected", approve=False)
    out = run_publish_cycle(conn, provider, settings, NOW)
    assert out["intake"]["created"] == []


# ---------------------------------------------------------------- gate 1: approval
def test_status_approved_without_receipt_is_blocked(conn, settings, provider):
    aid = add_asset(conn, approve=False)             # Brain says approved, but no human receipt
    run_publish_cycle(conn, provider, settings, NOW)
    job = job_of(conn, aid)
    assert job["status"] == "blocked" and job["block_code"] == "approval"
    assert "no approval record" in job["last_error"]


def test_suspicious_tier_never_publishes_even_if_approved(conn, settings, provider):
    aid = add_asset(conn, tier="suspicious")
    run_publish_cycle(conn, provider, settings, NOW)
    assert job_of(conn, aid)["status"] == "blocked"


def test_approval_requires_a_name(conn):
    aid = add_asset(conn, approve=False)
    try:
        record_approval(conn, aid, "  ")
    except ValueError:
        return
    raise AssertionError("anonymous approval must be rejected")


# ---------------------------------------------------------------- gate 2: integrity
def test_edit_after_approval_is_blocked_and_sent_back_to_review(conn, settings, provider):
    aid = add_asset(conn)
    conn.execute("UPDATE assets SET body_text=? WHERE id=?", ("Guaranteed payout, always covered!", aid))
    run_publish_cycle(conn, provider, settings, NOW)
    job = job_of(conn, aid)
    assert job["status"] == "blocked" and job["block_code"] == "integrity"
    assert get_asset(conn, aid)["status"] == "pending"          # returned to the human queue


def test_reapproval_after_edit_revives_the_job(conn, settings, provider):
    aid = add_asset(conn)
    conn.execute("UPDATE assets SET body_text=? WHERE id=?", ("A safer, re-written caption about transit cover.", aid))
    run_publish_cycle(conn, provider, settings, NOW)
    assert job_of(conn, aid)["status"] == "blocked"
    conn.execute("UPDATE assets SET status='approved' WHERE id=?", (aid,))    # human re-approves in the Brain UI ...
    record_approval(conn, aid, "Aisha (reviewer)")                            # ... and the receipt is refreshed
    out = run_publish_cycle(conn, provider, settings, NOW + timedelta(minutes=1))
    assert out["intake"]["requeued"] and job_of(conn, aid)["status"] == "scheduled"


# ---------------------------------------------------------------- gate 3: platform fit
def test_text_too_long_for_x_is_blocked_not_truncated(conn, settings, provider):
    aid = add_asset(conn, platform="X", body="word " * 80)
    run_publish_cycle(conn, provider, settings, NOW)
    job = job_of(conn, aid)
    assert job["status"] == "blocked" and job["block_code"] == "platform_fit" and "allows 280" in job["last_error"]
    assert get_asset(conn, aid)["body_text"] == "word " * 80         # nothing was silently cut


def test_instagram_needs_media_and_tiktok_needs_video(conn, settings, provider):
    ig = add_asset(conn, platform="Instagram")
    tt = add_asset(conn, platform="TikTok")
    set_media(conn, tt, "https://cdn.example.com/pic.png")            # an image is not enough for TikTok
    run_publish_cycle(conn, provider, settings, NOW)
    assert "needs an image or video" in job_of(conn, ig)["last_error"]
    assert "needs a video" in job_of(conn, tt)["last_error"]


def test_localhost_media_is_rejected_until_public_base_url_is_set(conn, monkeypatch, provider):
    aid = add_asset(conn, platform="Instagram")
    set_media(conn, aid, "http://127.0.0.1:8001/outputs/reel.mp4")
    run_publish_cycle(conn, provider, get_settings(), NOW)
    assert "not publicly reachable" in job_of(conn, aid)["last_error"]
    conn.execute("UPDATE publish_jobs SET status='queued', block_code=NULL WHERE asset_id=?", (str(aid),))
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "https://abc123.ngrok.app")
    run_publish_cycle(conn, provider, get_settings(), NOW + timedelta(minutes=1))
    assert job_of(conn, aid)["status"] == "scheduled"


def test_unsupported_platform_is_recorded_not_crashed(conn, settings, provider):
    aid = add_asset(conn, platform="Facebook")
    out = run_publish_cycle(conn, provider, settings, NOW)
    assert out["intake"]["unsupported"] == ["Facebook"]
    assert job_of(conn, aid, "facebook")["status"] == "blocked"


# ---------------------------------------------------------------- gate 4: safety
def test_kill_switch_defers_then_resumes(conn, settings, provider):
    aid = add_asset(conn)
    set_flag(conn, "kill_switch", "on")
    run_publish_cycle(conn, provider, settings, NOW)
    job = job_of(conn, aid)
    assert job["status"] == "queued" and job["attempts"] == 0 and "kill switch" in job["last_error"]
    set_flag(conn, "kill_switch", "off")
    run_publish_cycle(conn, provider, settings, NOW + timedelta(minutes=20))
    assert job_of(conn, aid)["status"] == "scheduled"


def test_rate_limit_defers_extra_posts(conn, monkeypatch, provider):
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "1")
    ids = [add_asset(conn, platform="X", body=f"Post number {i} about jewellers block cover.") for i in range(2)]
    run_publish_cycle(conn, provider, get_settings(), NOW)
    statuses = sorted(job_of(conn, i)["status"] for i in ids)
    assert statuses == ["queued", "scheduled"]


def test_duplicate_text_is_blocked(conn, settings, provider):
    first = add_asset(conn, platform="X", body="Same words twice.")
    second = add_asset(conn, platform="X", body="Same words twice.")
    run_publish_cycle(conn, provider, settings, NOW)
    assert {job_of(conn, first)["status"], job_of(conn, second)["status"]} == {"scheduled", "blocked"}


# ---------------------------------------------------------------- failure handling
class Flaky(MockProvider):
    def __init__(self, errors):
        super().__init__()
        self.errors = list(errors)
        self.calls = 0

    def schedule_post(self, payload):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return super().schedule_post(payload)


def test_transient_error_retries_with_backoff_then_succeeds(conn, settings):
    aid = add_asset(conn)
    p = Flaky([TransientProviderError("429")])
    run_publish_cycle(conn, p, settings, NOW)
    job = job_of(conn, aid)
    assert job["status"] == "retry" and job["attempts"] == 1 and job["next_attempt_at"] > "2026-09-21T02:04"
    assert publish_due(conn, p, settings, now=NOW + timedelta(minutes=1)) == []          # too early
    publish_due(conn, p, settings, now=NOW + timedelta(minutes=10))
    assert job_of(conn, aid)["status"] == "scheduled" and p.calls == 2


def test_gives_up_after_max_attempts(conn, monkeypatch):
    monkeypatch.setenv("MAX_ATTEMPTS", "2")
    s = get_settings()
    aid = add_asset(conn)
    p = Flaky([TransientProviderError("429")] * 5)
    run_publish_cycle(conn, p, s, NOW)
    publish_due(conn, p, s, now=NOW + timedelta(hours=1))
    job = job_of(conn, aid)
    assert job["status"] == "failed" and "gave up" in job["last_error"]


def test_permanent_error_fails_immediately(conn, settings):
    aid = add_asset(conn)
    run_publish_cycle(conn, Flaky([PermanentProviderError("channel disconnected")]), settings, NOW)
    job = job_of(conn, aid)
    assert job["status"] == "failed" and job["attempts"] == 1


def test_ambiguous_timeout_is_never_auto_retried(conn, settings):
    aid = add_asset(conn)
    p = Flaky([TransientProviderError("read timeout", ambiguous=True)])
    run_publish_cycle(conn, p, settings, NOW)
    assert job_of(conn, aid)["status"] == "needs_review"
    publish_due(conn, p, settings, now=NOW + timedelta(hours=2))
    assert p.calls == 1                                           # it did NOT try again on its own


def test_crash_recovery_is_safe(conn, settings):
    a, b = add_asset(conn, body="One."), add_asset(conn, body="Two.", platform="X")
    sync_approved(conn, settings, NOW)
    ja, jb = job_of(conn, a)["id"], job_of(conn, b)["id"]
    old = "2026-09-21T01:00:00.000Z"
    conn.execute("UPDATE publish_jobs SET status='publishing', updated_at=? WHERE id IN (?,?)", (old, ja, jb))
    conn.execute("UPDATE publish_jobs SET submitted_at=? WHERE id=?", (old, jb))      # b had already reached the provider
    assert recover_stale(conn, settings, NOW) == 2
    assert job_of(conn, a)["status"] == "queued"
    assert job_of(conn, b)["status"] == "needs_review"


def test_claim_is_atomic(conn, settings):
    add_asset(conn)
    sync_approved(conn, settings, NOW)
    jid = conn.execute("SELECT id FROM publish_jobs").fetchone()["id"]
    assert claim(conn, jid, NOW) is True
    assert claim(conn, jid, NOW) is False


# ---------------------------------------------------------------- preview + audit
def test_preview_preflight_has_no_side_effects(conn, settings, provider):
    aid = add_asset(conn, platform="X, Instagram")
    out = preview_preflight(conn, aid, None, provider, settings)
    assert out["platforms"]["x"]["action"] == "pass"
    assert out["platforms"]["instagram"]["action"] == "block"
    assert conn.execute("SELECT COUNT(*) FROM publish_jobs").fetchone()[0] == 0


def test_every_decision_is_audited(conn, settings, provider):
    add_asset(conn)
    run_publish_cycle(conn, provider, settings, NOW)
    events = {r["event"] for r in conn.execute("SELECT event FROM audit_log")}
    assert {"approval_recorded", "job_created", "scheduled"} <= events
