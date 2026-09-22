"""One-command demo:  python -m hub.scripts.demo_hub

Simulates the content agent's response shape (from its README) so the whole chain runs
without any live services: generate -> Supabase store 1 -> Brain assets -> compliance
(a stub, since no real Brain function is configured) -> Supabase store 2 -> Hands.
Uses a throw-away SQLite file and PRINTS what it would have sent to Supabase (no keys needed).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_db = Path(tempfile.gettempdir()) / "ja_hub_demo.db"
for suf in ("", "-wal", "-shm"):
    Path(str(_db) + suf).unlink(missing_ok=True)
os.environ.update({"DB_PATH": str(_db), "CONTENT_AGENT_URL": "http://demo.invalid", "BRAIN_COMPLIANCE_FUNC": ""})

from hands.bridge.brain_stub import ensure_brain_tables  # noqa: E402
from hands.db import connect, init_schema  # noqa: E402

from .. import content_store, outbox  # noqa: E402
from ..config import get_hub_settings  # noqa: E402
from ..content_client import ContentClient  # noqa: E402
from ..orchestrator import generate_and_process  # noqa: E402
from ..supabase_rest import SupabaseRest  # noqa: E402

FAKE_CONTENT_AGENT_RESPONSE = {
    "success": True, "agent": "content",
    "data": {
        "campaign": {"title": "Jewellers Block Awareness"},
        "linkedin": {"post": "A jeweller's stock is only as safe as its weakest handover."},
        "instagram": {"caption": "Three questions every jeweller should ask about stock cover."},
        "x": {"tweet": "Do you know where your jewellers block cover starts and stops?"},
        "ab_variants": [],
    },
}


def main() -> int:
    conn = connect()
    init_schema(conn)
    ensure_brain_tables(conn)
    outbox.init_hub_schema(conn)
    settings = get_hub_settings()
    content_sb = SupabaseRest("", "")       # not configured on purpose: demo shows the outbox catching writes
    compliance_sb = SupabaseRest("", "")

    print("=" * 100)
    print("HUB DEMO  |  Supabase not configured on purpose -> writes queue in hub_outbox instead of being lost")
    print("=" * 100)

    with patch.object(ContentClient, "generate", return_value=(FAKE_CONTENT_AGENT_RESPONSE, 842)):
        result = generate_and_process(conn, settings, ContentClient(settings.content_agent_url), content_sb, compliance_sb,
                                      request_body={"brand": "Jade", "platform": ["LinkedIn", "Instagram", "X"]},
                                      brand="Jade", region="Singapore", run_compliance=False)

    print("\nSTEP 1  generate_and_process() result:")
    print(json.dumps(result, indent=2)[:1500])

    print("\nSTEP 2  Assets created in the Brain's `assets` table (status='pending'):")
    for r in conn.execute("SELECT id, brand, platform, status, body_text FROM assets"):
        print(f"  [{r['id']}] {r['platform']:<10} {r['status']:<10} {r['body_text'][:70]}")

    print("\nSTEP 3  Queued for Supabase (hub_outbox) because no Supabase project was configured:")
    for r in conn.execute("SELECT target, table_name, on_conflict FROM hub_outbox"):
        print(f"  target={r['target']:<11} table={r['table_name']:<20} on_conflict={r['on_conflict']}")

    print("\nTo actually store to Supabase: fill SUPABASE_CONTENT_URL/KEY in .env, then POST /sync/outbox,")
    print("or just call /generate again once they're set - failed sends always retry from the outbox.\n")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
