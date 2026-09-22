"""Background sync.   Run:  python -m hub.scripts.sync_worker

Periodically retries the outbox and re-mirrors any compliance changes to Supabase,
independent of whether /generate is being called. Safe to run alongside the API.
"""
from __future__ import annotations

import logging
import time

from hands.db import connect, init_schema

from .. import compliance_store, outbox
from ..config import get_hub_settings
from ..supabase_rest import SupabaseRest

log = logging.getLogger("hub.sync_worker")


def run_once() -> dict:
    settings = get_hub_settings()
    conn = connect()
    init_schema(conn)
    outbox.init_hub_schema(conn)
    content_sb = SupabaseRest(settings.supabase_content_url, settings.supabase_content_key)
    compliance_sb = SupabaseRest(settings.supabase_compliance_url, settings.supabase_compliance_key)
    try:
        flushed = outbox.flush(conn, {"content": content_sb, "compliance": compliance_sb})
        synced = compliance_store.sync(conn, compliance_sb)
        return {"outbox": flushed, "compliance": synced}
    finally:
        conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_hub_settings()
    log.info("Hub sync worker starting (every %ss)", settings.sync_interval_seconds)
    while True:
        try:
            log.info("sync: %s", run_once())
        except Exception:  # noqa: BLE001 - one bad cycle must not kill the loop
            log.exception("sync cycle failed")
        time.sleep(settings.sync_interval_seconds)


if __name__ == "__main__":
    main()
