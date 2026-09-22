"""Market-aware scheduling.

Each JA Assure market has its own time zone, so "9am" means something different in
Singapore, Jakarta and Bangkok. Slots start from sensible per-platform priors and
switch to the times that actually performed best once enough posts are scored.
Nothing is ever scheduled in local quiet hours (22:00-07:00).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import Settings
from .utils import parse_iso, utcnow

REGION_TZ = {
    "singapore": "Asia/Singapore",
    "malaysia": "Asia/Kuala_Lumpur",
    "hong kong": "Asia/Hong_Kong",
    "hongkong": "Asia/Hong_Kong",
    "indonesia": "Asia/Jakarta",
    "thailand": "Asia/Bangkok",
}
TZ_LABEL = {
    "Asia/Singapore": "SGT",
    "Asia/Kuala_Lumpur": "MYT",
    "Asia/Hong_Kong": "HKT",
    "Asia/Jakarta": "WIB",
    "Asia/Bangkok": "ICT",
}
DEFAULT_REGION = "singapore"
QUIET_START, QUIET_END = 22, 7  # local hours

# platform -> (allowed weekdays Mon=0, [(hour, minute), ...])
PRIOR_SLOTS: dict[str, tuple[set[int], list[tuple[int, int]]]] = {
    "linkedin": ({1, 2, 3}, [(8, 30), (12, 0), (17, 30)]),
    "instagram": ({0, 1, 2, 3, 4, 5, 6}, [(12, 30), (19, 30)]),
    "x": ({0, 1, 2, 3, 4}, [(9, 0), (12, 30), (18, 0)]),
    "tiktok": ({0, 1, 2, 3, 4, 5, 6}, [(19, 0), (21, 0)]),
}
MIN_SAMPLES_FOR_LEARNING = 8


def region_tz(region: str | None) -> ZoneInfo:
    return ZoneInfo(REGION_TZ.get((region or DEFAULT_REGION).strip().lower(), REGION_TZ[DEFAULT_REGION]))


def tz_label(region: str | None) -> str:
    return TZ_LABEL.get(str(region_tz(region)), "local")


def _slot_times(platform: str, learned_hours: list[int] | None) -> tuple[set[int], list[tuple[int, int]]]:
    weekdays, times = PRIOR_SLOTS.get(platform, PRIOR_SLOTS["linkedin"])
    if learned_hours:
        times = [(h, 0) for h in learned_hours if not (h >= QUIET_START or h < QUIET_END)]
    return weekdays, times


def is_quiet(local_dt: datetime) -> bool:
    return local_dt.hour >= QUIET_START or local_dt.hour < QUIET_END


def candidate_slots(now_utc: datetime, platform: str, region: str | None, learned_hours: list[int] | None = None, days: int = 14) -> list[datetime]:
    tz = region_tz(region)
    weekdays, times = _slot_times(platform, learned_hours)
    now_local = now_utc.astimezone(tz)
    out: list[datetime] = []
    for d in range(days + 1):
        day = (now_local + timedelta(days=d)).date()
        if day.weekday() not in weekdays:
            continue
        for hour, minute in times:
            local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            if not is_quiet(local):
                out.append(local.astimezone(now_utc.tzinfo))
    return sorted(out)


def timing_fit(platform: str, region: str | None, when_utc: datetime, learned_hours: list[int] | None = None) -> int:
    """Timing lens: 100 = inside a recommended window, 60 = within 3h of one, 30 = otherwise."""
    tz = region_tz(region)
    local = when_utc.astimezone(tz)
    weekdays, times = _slot_times(platform, learned_hours)
    if local.weekday() not in weekdays:
        return 30
    best = min(
        abs((local - datetime(local.year, local.month, local.day, h, m, tzinfo=tz)).total_seconds()) / 60
        for h, m in times
    ) if times else 999
    if best <= 90:
        return 100
    if best <= 180:
        return 60
    return 30


def choose_slot(conn: sqlite3.Connection, platform: str, region: str | None, settings: Settings, now: datetime | None = None) -> tuple[datetime, str]:
    now = now or utcnow()
    earliest = now + timedelta(minutes=settings.min_lead_minutes)
    if settings.schedule_mode == "immediate":
        return now + timedelta(seconds=30), "immediate mode (demo)"

    from .learning import best_hours  # local import: learning imports this module

    learned = best_hours(conn, platform, region)
    taken = [
        parse_iso(r["scheduled_for"])
        for r in conn.execute(
            "SELECT scheduled_for FROM publish_jobs WHERE platform=? AND scheduled_for IS NOT NULL "
            "AND status IN ('queued','retry','publishing','scheduled','published')",
            (platform,),
        )
    ]
    gap = timedelta(minutes=settings.min_slot_gap_minutes)
    for slot in candidate_slots(now, platform, region, learned):
        if slot < earliest:
            continue
        if any(abs(slot - t) < gap for t in taken):
            continue
        source = "learned best hour" if learned else "market prior"
        label = f"{slot.astimezone(region_tz(region)):%a %H:%M} {tz_label(region)}"
        return slot, f"{source}: {label}"
    return earliest, "fallback: no free slot in 14 days"
