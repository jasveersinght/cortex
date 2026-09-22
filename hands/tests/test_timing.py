from datetime import datetime, timezone

from hands.config import get_settings
from hands.timing import candidate_slots, choose_slot, is_quiet, region_tz, timing_fit

from .conftest import NOW


def test_linkedin_slots_only_tue_to_thu_and_never_quiet():
    slots = candidate_slots(NOW, "linkedin", "Singapore")
    tz = region_tz("Singapore")
    assert slots and all(s.astimezone(tz).weekday() in {1, 2, 3} for s in slots)
    assert not any(is_quiet(s.astimezone(tz)) for s in slots)


def test_markets_use_their_own_timezone():
    sg = candidate_slots(NOW, "instagram", "Singapore")[0]
    jkt = candidate_slots(NOW, "instagram", "Indonesia")[0]
    assert sg.astimezone(region_tz("Singapore")).hour == jkt.astimezone(region_tz("Indonesia")).hour  # both 12:30 local
    assert sg != jkt


def test_choose_slot_is_in_future_and_spaced(conn):
    s = get_settings()
    first, why = choose_slot(conn, "x", "Singapore", s, NOW)
    assert first > NOW and "market prior" in why
    conn.execute("INSERT INTO publish_jobs (asset_id, platform, status, scheduled_for, created_at, updated_at) VALUES ('1','x','scheduled',?, 'a','a')",
                 (first.strftime("%Y-%m-%dT%H:%M:%S.000Z"),))
    second, _ = choose_slot(conn, "x", "Singapore", s, NOW)
    assert second != first and abs((second - first).total_seconds()) >= 90 * 60


def test_timing_fit_lens():
    inside = datetime(2026, 9, 22, 0, 30, tzinfo=timezone.utc)   # Tue 08:30 SGT
    weekend = datetime(2026, 9, 26, 0, 30, tzinfo=timezone.utc)  # Sat
    assert timing_fit("linkedin", "Singapore", inside) == 100
    assert timing_fit("linkedin", "Singapore", weekend) == 30
