from __future__ import annotations

import json
from datetime import timedelta

from hands.approvals import record_approval
from hands.learning import best_hours, hashtag_leaderboard, insights_for, write_lessons
from hands.metrics import collect_metrics
from hands.performance import score_pending, tier_for
from hands.pipeline import run_metrics_cycle, run_publish_cycle
from hands.providers import MockProvider
from hands.providers.base import ProviderMetrics
from hands.utils import dumps

from .conftest import NOW, add_asset

LATER = NOW + timedelta(days=15)      # far enough that every smart slot is in the past


class Scripted(MockProvider):
    """Returns metrics chosen by the test, keyed by the text's first word."""

    def __init__(self, table):
        super().__init__()
        self.table = table

    def fetch_metrics(self, post_id, platform):
        return self.table.get(post_id, ProviderMetrics(status="sent"))


HIGH = dict(status="sent", impressions=2000, likes=200, comments=40, shares=30, saves=0, clicks=40)
LOW = dict(status="sent", impressions=100, likes=1, comments=0, shares=0, saves=0, clicks=0)


def publish(conn, settings, provider, **asset_kw):
    aid = add_asset(conn, **asset_kw)
    run_publish_cycle(conn, provider, settings, NOW)
    return aid, conn.execute("SELECT * FROM publish_jobs WHERE asset_id=?", (str(aid),)).fetchone()


def test_tiers():
    assert [tier_for(x) for x in (95, 60, 40, 5)] == ["top_performer", "solid", "weak", "underperforming"]


def test_mock_metrics_are_deterministic():
    a, b = MockProvider().fetch_metrics("mock_abc", "linkedin"), MockProvider().fetch_metrics("mock_abc", "linkedin")
    assert a.impressions == b.impressions and a.likes == b.likes


def test_not_due_yet_means_no_metrics(conn, settings, provider):
    publish(conn, settings, provider)
    out = collect_metrics(conn, provider, settings, NOW + timedelta(minutes=1))
    assert out["snapshots"] == 0


def test_full_loop_scores_lessons_and_snapshots(conn, settings):
    p = Scripted({})
    a, ja = publish(conn, settings, p, platform="LinkedIn", body="Alpha post about stock in transit.")
    b, jb = publish(conn, settings, p, platform="LinkedIn", body="Bravo post about vault cover.")
    p.table = {ja["external_post_id"]: ProviderMetrics(**HIGH), jb["external_post_id"]: ProviderMetrics(**LOW)}

    out = run_metrics_cycle(conn, p, settings, LATER)
    assert out["metrics"]["snapshots"] == 2 and out["metrics"]["published"] == 2
    scores = {r["job_id"]: r for r in conn.execute("SELECT * FROM performance_scores")}
    assert scores[ja["id"]]["tier"] == "top_performer" and scores[jb["id"]]["tier"] == "underperforming"
    assert scores[ja["id"]]["total_score"] > 80 > 30 > scores[jb["id"]]["total_score"]

    lessons = conn.execute("SELECT * FROM lessons_learned ORDER BY id").fetchall()
    assert {l["tag"] for l in lessons} == {"perf:top_performer", "perf:underperforming"}
    assert "Repeat what worked" in [l for l in lessons if l["tag"] == "perf:top_performer"][0]["note"]

    # second run: nothing new, nothing duplicated
    out2 = run_metrics_cycle(conn, p, settings, LATER + timedelta(minutes=5))
    assert out2["performance"]["scored"] == []
    assert write_lessons(conn, [ja["id"], jb["id"]]) == 0
    assert conn.execute("SELECT COUNT(*) FROM lessons_learned").fetchone()[0] == 2


def test_new_snapshot_rescores_after_min_interval(conn, settings):
    p = Scripted({})
    _, job = publish(conn, settings, p)
    p.table = {job["external_post_id"]: ProviderMetrics(**LOW)}
    run_metrics_cycle(conn, p, settings, LATER)
    first = conn.execute("SELECT total_score FROM performance_scores").fetchone()[0]
    p.table = {job["external_post_id"]: ProviderMetrics(**HIGH)}
    run_metrics_cycle(conn, p, settings, LATER + timedelta(hours=3))
    second = conn.execute("SELECT total_score FROM performance_scores").fetchone()[0]
    assert second > first
    assert conn.execute("SELECT COUNT(*) FROM post_metrics").fetchone()[0] == 2      # snapshots kept, not overwritten


def test_missing_metric_is_not_treated_as_zero(conn, settings):
    p = Scripted({})
    _, job = publish(conn, settings, p)
    p.table = {job["external_post_id"]: ProviderMetrics(status="sent", impressions=1600, likes=100, comments=20, shares=10)}  # no clicks
    run_metrics_cycle(conn, p, settings, LATER)
    row = conn.execute("SELECT * FROM performance_scores").fetchone()
    assert row["conversion_score"] is None
    assert "conversion" in json.loads(row["explain_json"])["skipped_lenses"]
    assert row["total_score"] > 50                                                    # weights were re-normalised


def test_metrics_not_reported_yet_stays_pending(conn, settings):
    p = Scripted({})
    _, job = publish(conn, settings, p)
    p.table = {job["external_post_id"]: ProviderMetrics(status="scheduled")}         # no numbers yet
    out = collect_metrics(conn, p, settings, LATER)
    assert out["snapshots"] == 0 and out["pending"] >= 1
    assert conn.execute("SELECT COUNT(*) FROM post_metrics").fetchone()[0] == 0


def test_provider_reported_error_marks_job_failed(conn, settings):
    p = Scripted({})
    _, job = publish(conn, settings, p)
    p.table = {job["external_post_id"]: ProviderMetrics(status="error")}
    collect_metrics(conn, p, settings, LATER)
    assert conn.execute("SELECT status FROM publish_jobs").fetchone()[0] == "failed"


def test_insights_and_hashtag_leaderboard_feed_the_content_agent(conn, settings):
    p = Scripted({})
    table = {}
    for i, (tags, m, body) in enumerate([
        (["#JewellersBlock"], HIGH, "Short and sharp."),
        (["#JewellersBlock", "#InsurTech"], HIGH, "Another short one."),
        (["#Random"], LOW, "A very long winded caption " * 12),
    ]):
        _, job = publish(conn, settings, p, body=body + f" v{i}")
        conn.execute("UPDATE publish_jobs SET hashtags_json=? WHERE id=?", (dumps(tags), job["id"]))
        table[job["external_post_id"]] = ProviderMetrics(**m)
    p.table = table
    run_metrics_cycle(conn, p, settings, LATER)

    board = hashtag_leaderboard(conn, "Jade", "linkedin")
    assert board[0]["tag"] == "#jewellersblock" and board[0]["uses"] == 2
    assert "#random" not in [b["tag"] for b in board]                                # low scorers are not "proven"

    ins = insights_for(conn, "Jade", "linkedin")
    assert ins["ready"] and "PERFORMANCE INSIGHTS" in ins["prompt_block"]
    assert "Shorter posts performed better" in ins["prompt_block"]
    assert "compliance" in ins["prompt_block"].lower()


def test_insights_empty_until_data_exists(conn):
    ins = insights_for(conn, "Jade", "linkedin")
    assert ins["scored_posts"] == 0 and ins["prompt_block"] == ""


def test_timing_switches_to_learned_hours_after_enough_samples(conn):
    for i in range(8):
        hour = 4 if i < 4 else 1        # 12:00 SGT scores high, 09:00 SGT scores low
        cur = conn.execute(
            "INSERT INTO publish_jobs (asset_id, platform, brand, region, status, scheduled_for, created_at, updated_at) "
            "VALUES (?, 'linkedin', 'Jade', 'Singapore', 'published', ?, 'a', 'a')",
            (str(i), f"2026-09-{10 + i:02d}T{hour:02d}:00:00.000Z"))
        conn.execute("INSERT INTO performance_scores (job_id, total_score, tier, computed_at) VALUES (?,?,?,?)",
                     (cur.lastrowid, 90 if hour == 4 else 20, "x", "now"))
    assert 12 in best_hours(conn, "linkedin", "Singapore")
