from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _s(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class HubSettings:
    content_agent_url: str
    research_agent_url: str
    hands_api_url: str
    brain_path: str
    brain_compliance_func: str
    brain_decision_func: str
    supabase_content_url: str
    supabase_content_key: str
    supabase_compliance_url: str
    supabase_compliance_key: str
    content_context_field: str
    hub_api_key: str
    sync_interval_seconds: int

    @classmethod
    def from_env(cls) -> "HubSettings":
        try:
            interval = int(_s("SYNC_INTERVAL_SECONDS", "120") or 120)
        except ValueError:
            interval = 120
        return cls(
            content_agent_url=_s("CONTENT_AGENT_URL", "http://127.0.0.1:8001").rstrip("/"),
            research_agent_url=_s("RESEARCH_AGENT_URL", "http://127.0.0.1:8000").rstrip("/"),
            hands_api_url=_s("HANDS_API_URL", "http://127.0.0.1:8002").rstrip("/"),
            brain_path=_s("BRAIN_PATH"),
            brain_compliance_func=_s("BRAIN_COMPLIANCE_FUNC"),
            brain_decision_func=_s("BRAIN_DECISION_FUNC"),
            supabase_content_url=_s("SUPABASE_CONTENT_URL").rstrip("/"),
            supabase_content_key=_s("SUPABASE_CONTENT_KEY"),
            supabase_compliance_url=_s("SUPABASE_COMPLIANCE_URL").rstrip("/"),
            supabase_compliance_key=_s("SUPABASE_COMPLIANCE_KEY"),
            content_context_field=_s("CONTENT_CONTEXT_FIELD"),
            hub_api_key=_s("HUB_API_KEY"),
            sync_interval_seconds=interval,
        )


def get_hub_settings() -> HubSettings:
    return HubSettings.from_env()
