"""Settings, read from environment variables (never hard-coded secrets)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

try:  # .env is optional; real env vars always win
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _channel_map(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(k).strip().lower(): str(v).strip() for k, v in data.items() if str(v).strip()}


@dataclass(frozen=True)
class Settings:
    db_path: str = "ja_assure.db"
    provider: str = "mock"
    dry_run: bool = False

    buffer_api_key: str = ""
    buffer_org_id: str = ""
    buffer_api_url: str = "https://api.buffer.com"
    buffer_scheduling_type: str = "automatic"
    buffer_channel_map: dict[str, str] = field(default_factory=dict)

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    enrichment_mode: str = "auto"

    content_agent_base_url: str = "http://127.0.0.1:8001"
    public_media_base_url: str = ""

    schedule_mode: str = "smart"
    rate_limit_per_hour: int = 3
    rate_limit_per_day: int = 8
    x_char_limit: int = 280
    require_approval_record: bool = True
    revert_tampered_to_pending: bool = True
    ai_disclosure: bool = True
    min_lead_minutes: int = 10
    min_slot_gap_minutes: int = 90

    enable_worker: bool = False
    publish_poll_seconds: int = 300
    metrics_poll_seconds: int = 1800
    max_attempts: int = 4
    backoff_base_seconds: int = 300
    metrics_min_interval_minutes: int = 60
    score_min_age_hours: int = 24
    stale_publishing_minutes: int = 10

    mock_fail_rate: float = 0.0
    api_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=_str("DB_PATH", "ja_assure.db"),
            provider=_str("PROVIDER", "mock").lower(),
            dry_run=_bool("DRY_RUN", False),
            buffer_api_key=_str("BUFFER_API_KEY"),
            buffer_org_id=_str("BUFFER_ORG_ID"),
            buffer_api_url=_str("BUFFER_API_URL", "https://api.buffer.com"),
            buffer_scheduling_type=_str("BUFFER_SCHEDULING_TYPE", "automatic").lower(),
            buffer_channel_map=_channel_map(_str("BUFFER_CHANNEL_MAP")),
            gemini_api_key=_str("GEMINI_API_KEY"),
            gemini_model=_str("GEMINI_MODEL", "gemini-3.6-flash"),
            enrichment_mode=_str("ENRICHMENT_MODE", "auto").lower(),
            content_agent_base_url=_str("CONTENT_AGENT_BASE_URL", "http://127.0.0.1:8001").rstrip("/"),
            public_media_base_url=_str("PUBLIC_MEDIA_BASE_URL").rstrip("/"),
            schedule_mode=_str("SCHEDULE_MODE", "smart").lower(),
            rate_limit_per_hour=_int("RATE_LIMIT_PER_HOUR", 3),
            rate_limit_per_day=_int("RATE_LIMIT_PER_DAY", 8),
            x_char_limit=_int("X_CHAR_LIMIT", 280),
            require_approval_record=_bool("REQUIRE_APPROVAL_RECORD", True),
            revert_tampered_to_pending=_bool("REVERT_TAMPERED_TO_PENDING", True),
            ai_disclosure=_bool("AI_DISCLOSURE", True),
            min_lead_minutes=_int("MIN_LEAD_MINUTES", 10),
            min_slot_gap_minutes=_int("MIN_SLOT_GAP_MINUTES", 90),
            enable_worker=_bool("ENABLE_WORKER", False),
            publish_poll_seconds=_int("PUBLISH_POLL_SECONDS", 300),
            metrics_poll_seconds=_int("METRICS_POLL_SECONDS", 1800),
            max_attempts=_int("MAX_ATTEMPTS", 4),
            backoff_base_seconds=_int("BACKOFF_BASE_SECONDS", 300),
            metrics_min_interval_minutes=_int("METRICS_MIN_INTERVAL_MINUTES", 60),
            score_min_age_hours=_int("SCORE_MIN_AGE_HOURS", 24),
            stale_publishing_minutes=_int("STALE_PUBLISHING_MINUTES", 10),
            mock_fail_rate=_float("MOCK_FAIL_RATE", 0.0),
            api_key=_str("HANDS_API_KEY"),
        )


def get_settings() -> Settings:
    """Re-read on every call so tests and scripts can change the environment."""
    return Settings.from_env()
