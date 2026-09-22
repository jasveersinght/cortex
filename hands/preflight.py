"""The 4-gate pre-flight check (mirrors the Brain's 4 compliance lenses).

    1. Approval  - a human approved it, with a receipt, and it was not auto-rejected.
    2. Integrity - the text is byte-for-byte what the human approved (tamper check).
    3. Platform  - length, media and channel are valid for the destination.
    4. Safety    - kill switch off, rate limits respected, not a duplicate.

Every gate returns pass/fail with a plain-English reason. Any 'block' stops the post;
a 'defer' just waits (kill switch, rate limit) without burning a retry.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .approvals import get_approval
from .config import Settings
from .db import get_flag
from .media import is_public_url
from .platform_rules import PlatformRule, count_length
from .providers.base import Provider
from .utils import parse_iso, sha256_text, to_iso, utcnow

DUPLICATE_WINDOW_DAYS = 30
DEFER_MINUTES = 15


@dataclass
class GateResult:
    name: str
    passed: bool
    reason: str
    severity: str = "block"     # block | defer (only meaningful when passed is False)
    code: str = ""              # stored as publish_jobs.block_code

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreflightReport:
    gates: list[GateResult] = field(default_factory=list)
    retry_after: datetime | None = None

    @property
    def action(self) -> str:
        failed = [g for g in self.gates if not g.passed]
        if any(g.severity == "block" for g in failed):
            return "block"
        return "defer" if failed else "pass"

    @property
    def ok(self) -> bool:
        return self.action == "pass"

    @property
    def block_code(self) -> str | None:
        for g in self.gates:
            if not g.passed and g.severity == "block":
                return g.code or g.name
        return None

    def summary(self) -> str:
        return "; ".join(f"[{g.name}] {g.reason}" for g in self.gates if not g.passed) or "all gates passed"

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "gates": [g.to_dict() for g in self.gates]}


def gate_approval(conn: sqlite3.Connection, asset: sqlite3.Row, settings: Settings) -> GateResult:
    status = str(asset["status"] or "").lower()
    if status != "approved":
        return GateResult("approval", False, f"asset status is '{status}', not 'approved'", code="approval")
    if str(asset["tier"] or "").lower() == "suspicious":
        return GateResult("approval", False, "compliance tier is 'suspicious'; it must never be published", code="approval")
    rec = get_approval(conn, asset["id"])
    if settings.require_approval_record and rec is None:
        return GateResult("approval", False, "no approval record (who approved it, and when)", code="approval")
    who = f"approved by {rec['approved_by']} at {rec['approved_at']}" if rec else "approved (no record required)"
    return GateResult("approval", True, who)


def gate_integrity(conn: sqlite3.Connection, asset: sqlite3.Row) -> GateResult:
    rec = get_approval(conn, asset["id"])
    if rec is None:
        return GateResult("integrity", True, "skipped: no approval record to compare against")
    if sha256_text(asset["body_text"]) != rec["body_hash"]:
        return GateResult("integrity", False, "text was edited after approval; it needs a fresh human approval", code="integrity")
    return GateResult("integrity", True, "text matches what the human approved")


def gate_platform_fit(
    asset: sqlite3.Row,
    platform: str,
    rule: PlatformRule,
    media: sqlite3.Row | None,
    provider: Provider,
) -> GateResult:
    body = asset["body_text"] or ""
    if not body.strip():
        return GateResult("platform_fit", False, "post text is empty", code="platform_fit")
    size = count_length(body, rule)
    if size > rule.limit:
        return GateResult("platform_fit", False, f"text is {size} units, {platform} allows {rule.limit}; shorten and re-approve", code="platform_fit")
    if rule.media == "required" and media is None:
        return GateResult("platform_fit", False, f"{platform} needs an image or video and none is attached", code="platform_fit")
    if rule.media == "video_required" and (media is None or media["media_type"] != "video"):
        return GateResult("platform_fit", False, f"{platform} needs a video and none is attached", code="platform_fit")
    if media is not None and not is_public_url(media["media_url"]):
        return GateResult("platform_fit", False, "media URL is not publicly reachable (localhost/private); set PUBLIC_MEDIA_BASE_URL", code="platform_fit")
    problem = provider.validate(platform, asset["brand"])
    if problem:
        return GateResult("platform_fit", False, problem, code="platform_fit")
    return GateResult("platform_fit", True, f"{size}/{rule.limit} units, media ok, channel ok")


def gate_safety(conn: sqlite3.Connection, job_id: int | None, platform: str, body_hash: str, settings: Settings, now: datetime) -> tuple[GateResult, datetime | None]:
    if get_flag(conn, "kill_switch", "off") == "on":
        return GateResult("safety", False, "kill switch is ON; posting is paused", severity="defer", code="safety"), now + timedelta(minutes=DEFER_MINUTES)

    dup = conn.execute(
        "SELECT id FROM publish_jobs WHERE platform=? AND body_hash=? AND id != ? "
        "AND status IN ('scheduled','published','publishing') AND created_at >= ?",
        (platform, body_hash, job_id or -1, to_iso(now - timedelta(days=DUPLICATE_WINDOW_DAYS))),
    ).fetchone()
    if dup:
        return GateResult("safety", False, f"identical text already posted on {platform} (job {dup['id']}) in the last {DUPLICATE_WINDOW_DAYS} days", code="safety"), None

    for label, delta, cap in (("hour", timedelta(hours=1), settings.rate_limit_per_hour), ("day", timedelta(days=1), settings.rate_limit_per_day)):
        sent = conn.execute(
            "SELECT COUNT(*) AS n FROM publish_jobs WHERE platform=? AND submitted_at IS NOT NULL AND submitted_at >= ? "
            "AND status IN ('scheduled','published','publishing') AND id != ?",
            (platform, to_iso(now - delta), job_id or -1),
        ).fetchone()["n"]
        if sent >= cap:
            return GateResult("safety", False, f"rate limit: {sent}/{cap} posts on {platform} in the last {label}", severity="defer", code="safety"), now + timedelta(minutes=DEFER_MINUTES)
    return GateResult("safety", True, "kill switch off, under rate limits, not a duplicate"), None


def run_preflight(
    conn: sqlite3.Connection,
    *,
    asset: sqlite3.Row,
    job_id: int | None,
    platform: str,
    rule: PlatformRule,
    media: sqlite3.Row | None,
    provider: Provider,
    settings: Settings,
    now: datetime | None = None,
) -> PreflightReport:
    now = now or utcnow()
    report = PreflightReport()
    report.gates.append(gate_approval(conn, asset, settings))
    report.gates.append(gate_integrity(conn, asset))
    report.gates.append(gate_platform_fit(asset, platform, rule, media, provider))
    safety, retry_after = gate_safety(conn, job_id, platform, sha256_text(asset["body_text"]), settings, now)
    report.gates.append(safety)
    report.retry_after = retry_after
    return report
