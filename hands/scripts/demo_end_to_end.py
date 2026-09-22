"""One-command demo:  python -m hands.scripts.demo_end_to_end

generate -> approve -> PRE-FLIGHT -> schedule -> metrics -> 4 performance lenses -> lessons -> insights for the content agent.
Uses a throw-away database and the MOCK provider, so nothing is ever posted and your real data is untouched.
Metrics here are SYNTHETIC (clearly labelled); with PROVIDER=buffer they come from the real platforms.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

_demo_db = Path(tempfile.gettempdir()) / "ja_hands_demo.db"
for suffix in ("", "-wal", "-shm"):
    Path(str(_demo_db) + suffix).unlink(missing_ok=True)
os.environ.update({"DB_PATH": str(_demo_db), "PROVIDER": "mock", "DRY_RUN": "true", "SCHEDULE_MODE": "immediate",
                   "SCORE_MIN_AGE_HOURS": "0", "GEMINI_API_KEY": "", "RATE_LIMIT_PER_HOUR": "10", "RATE_LIMIT_PER_DAY": "50"})

from ..config import get_settings  # noqa: E402  (after env is prepared)
from ..db import connect, init_schema  # noqa: E402
from ..learning import insights_for  # noqa: E402
from ..pipeline import run_metrics_cycle, run_publish_cycle  # noqa: E402
from ..providers import build_provider  # noqa: E402
from ..utils import loads, utcnow  # noqa: E402
from .seed_demo import seed  # noqa: E402


def line(char="-"):
    print(char * 100)


def main() -> int:
    settings, conn = get_settings(), connect()
    init_schema(conn)
    provider = build_provider(settings)
    ids = seed(conn)
    print(f"\nHANDS DEMO  |  provider={provider.name} (nothing is posted)  |  db={_demo_db}\n")

    line("=")
    print("STEP 1  Publish cycle: approved assets -> jobs -> 4-gate pre-flight -> schedule")
    line("=")
    out = run_publish_cycle(conn, provider, settings)
    rows = conn.execute("SELECT j.*, a.body_text FROM publish_jobs j JOIN assets a ON CAST(a.id AS TEXT)=j.asset_id ORDER BY j.id").fetchall()
    label_of = {v: k for k, v in ids.items()}
    print(f"{'asset':<26}{'platform':<11}{'status':<11}why")
    line()
    for r in rows:
        why = (r["last_error"] or f"{r['slot_reason']} | tags: {' '.join(loads(r['hashtags_json'], []) or [])}")[:64]
        print(f"{label_of.get(int(r['asset_id']), r['asset_id']):<26}{r['platform']:<11}{r['status']:<11}{why}")
    blocked = sum(1 for r in rows if r["status"] == "blocked")
    print(f"\n-> {sum(1 for r in rows if r['status']=='scheduled')} scheduled, {blocked} STOPPED by the gates, "
          f"and 'still_pending' was never touched (only approved assets are picked up).")
    tampered = conn.execute("SELECT status FROM assets WHERE id=?", (ids["tampered"],)).fetchone()[0]
    print(f"-> the tampered asset was sent back to human review: assets.status is now '{tampered}'.")

    line("=")
    print("STEP 2  Metrics cycle: collect engagement -> 4 performance lenses -> lessons")
    line("=")
    later = utcnow() + timedelta(days=1)
    out = run_metrics_cycle(conn, provider, settings, later)
    print(f"{'asset':<26}{'platform':<11}{'engage':>7}{'reach':>7}{'conv':>7}{'timing':>7}{'total':>7}  tier")
    line()
    for s in conn.execute("SELECT s.*, j.platform, j.asset_id FROM performance_scores s JOIN publish_jobs j ON j.id=s.job_id ORDER BY s.total_score DESC"):
        f = lambda v: "  n/a" if v is None else f"{v:5.0f}"
        print(f"{label_of.get(int(s['asset_id'])):<26}{s['platform']:<11}{f(s['engagement_score']):>7}{f(s['reach_score']):>7}"
              f"{f(s['conversion_score']):>7}{f(s['timing_score']):>7}{s['total_score']:>7.0f}  {s['tier']}")
    print(f"\n-> {out['performance']['lessons_written']} performance lessons written into the Brain's lessons_learned table:")
    for l in conn.execute("SELECT tag, note FROM lessons_learned"):
        print(f"   [{l['tag']}] {l['note'][:110]}")

    line("=")
    print("STEP 3  What the Content agent now receives (GET /insights?brand=Jade&platform=linkedin)")
    line("=")
    ins = insights_for(conn, None, None)
    print(ins["prompt_block"] or "(not enough scored posts yet: the block appears once there are 3+)")

    line("=")
    print("STEP 4  Audit trail (last 8 events)")
    line("=")
    for a in conn.execute("SELECT ts, event, job_id, detail FROM audit_log ORDER BY id DESC LIMIT 8"):
        print(f"{a['ts']}  {a['event']:<32} job={a['job_id']}  {(a['detail'] or '')[:50]}")
    print("\nDone. Run the real thing with:  uvicorn hands.api:app --port 8002   and   python -m hands.worker\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
