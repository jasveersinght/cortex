from __future__ import annotations

from hands.approvals import record_approval
from hands.db import insert_dynamic

from .. import compliance_store, outbox
from ..supabase_rest import SupabaseError, SupabaseRest


class FakeClient:
    def __init__(self, fail=False):
        self.fail, self.enabled, self.sent = fail, True, []

    def upsert(self, table, rows, on_conflict):
        if self.fail:
            raise SupabaseError("simulated outage")
        self.sent.append((table, rows, on_conflict))
        return rows


def test_outbox_queues_on_failure_and_flushes_later(conn):
    client = FakeClient(fail=True)
    outbox.enqueue(conn, "content", "content_generations", "id", [{"id": "1"}], "boom")
    assert conn.execute("SELECT COUNT(*) FROM hub_outbox").fetchone()[0] == 1

    result = outbox.flush(conn, {"content": client})
    assert result == {"sent": 0, "pending": 1}
    assert conn.execute("SELECT COUNT(*) FROM hub_outbox").fetchone()[0] == 1        # still queued

    client.fail = False
    result = outbox.flush(conn, {"content": client})
    assert result == {"sent": 1, "pending": 0}
    assert conn.execute("SELECT COUNT(*) FROM hub_outbox").fetchone()[0] == 0        # drained
    assert client.sent[0][0] == "content_generations"


def test_compliance_sync_is_idempotent(conn):
    aid = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "LinkedIn", "region": "Singapore",
                                          "body_text": "Cover for stock in transit.", "status": "approved", "tier": "highly_recommended"})
    record_approval(conn, aid, "Aisha")
    conn.execute("INSERT INTO lens_scores (asset_id, lens_name, score, reason) VALUES (?,?,?,?)", (aid, "claims", 92, "no prohibited language"))
    conn.execute("INSERT INTO lessons_learned (asset_id, tag, note) VALUES (?,?,?)", (aid, "perf:top_performer", "Repeat what worked."))

    client = FakeClient()
    out = compliance_store.sync(conn, client)
    assert out["reviews"] == 1 and out["decisions"] == 1 and out["lessons"] == 1

    review_rows = [c for c in client.sent if c[0] == "compliance_reviews"][0][1]
    assert review_rows[0]["tier"] == "highly_recommended" and review_rows[0]["lens_scores"]["claims"]["score"] == 92

    client.sent.clear()
    again = compliance_store.sync(conn, client)
    assert again == {"reviews": 0, "decisions": 0, "lessons": 0, "errors": 0}          # nothing re-sent
    assert client.sent == []


def test_compliance_sync_resends_after_a_change(conn):
    aid = insert_dynamic(conn, "assets", {"brand": "Jade", "platform": "LinkedIn", "region": "Singapore",
                                          "body_text": "Text.", "status": "pending", "tier": "vigilant"})
    client = FakeClient()
    compliance_store.sync(conn, client)
    client.sent.clear()

    conn.execute("UPDATE assets SET status='approved', tier='highly_recommended' WHERE id=?", (aid,))
    record_approval(conn, aid, "Aisha")
    out = compliance_store.sync(conn, client)
    assert out["reviews"] == 1 and out["decisions"] == 1


def test_sync_skipped_when_not_configured(conn):
    out = compliance_store.sync(conn, SupabaseRest("", ""))
    assert out == {"skipped": "compliance Supabase is not configured"}
