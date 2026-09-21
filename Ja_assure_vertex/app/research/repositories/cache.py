"""Cache Manager — request hashing, cache keys, TTL, in-flight detection.

Cache is checked BEFORE any Tavily or Groq call.
This is the single highest-value cost control in the system.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.research.enums import ResearchType
from app.research.registry import get_research_config

logger = logging.getLogger("ja_assure")


def normalize_objective(objective: str | None) -> str:
    """Normalize the objective for hashing: lowercase, whitespace-collapsed."""
    if not objective:
        return ""
    return " ".join(objective.strip().lower().split())


def compute_request_hash(
    brand: str,
    market: str,
    research_type: str,
    competitors: list[str],
    topics: list[str],
    lookback_days: int,
    objective: str | None,
) -> str:
    """Compute a deterministic hash for a research request.

    max_sources and force_refresh are deliberately EXCLUDED —
    they control execution, not the semantic identity of the question.
    """
    canonical = json.dumps({
        "brand": brand.strip().lower(),
        "market": market.strip().lower(),
        "research_type": research_type,
        "competitors": sorted(c.strip().lower() for c in competitors),
        "topics": sorted(t.strip().lower() for t in topics),
        "lookback_days": lookback_days,
        "objective_normalized": normalize_objective(objective),
    }, sort_keys=True)

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_cache_key(research_type: str, request_hash: str) -> str:
    """Build a cache key from research type and request hash."""
    return f"research:{research_type}:{request_hash[:16]}"


class CacheManager:
    """Manages research cache using Supabase with in-memory fallback."""

    def __init__(self, supabase_url: str, supabase_key: str):
        self._memory_cache: dict[str, dict] = {}
        try:
            from supabase import create_client
            self._client = create_client(supabase_url, supabase_key)
        except Exception:
            self._client = None

    def get_valid(self, cache_key: str) -> dict | None:
        """Look up a valid (non-expired) cache entry."""
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if datetime.fromisoformat(entry["expires_at"]) > datetime.now(timezone.utc):
                return entry
        if self._client:
            try:
                now = datetime.now(timezone.utc).isoformat()
                result = (
                    self._client.table("research_cache")
                    .select("*")
                    .eq("cache_key", cache_key)
                    .gte("expires_at", now)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
            except Exception:
                pass
        return None

    def get_stale(self, cache_key: str) -> dict | None:
        """Get an expired cache entry for stale fallback."""
        try:
            result = (
                self._client.table("research_cache")
                .select("*")
                .eq("cache_key", cache_key)
                .order("expires_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Stale cache lookup failed: {e}")
            return None

    def write(
        self,
        cache_key: str,
        request_hash: str,
        research_run_id: UUID,
        research_type: str,
        ttl_hours: int,
    ):
        """Write or update a cache entry."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        data = {
            "cache_key": cache_key,
            "request_hash": request_hash,
            "research_run_id": str(research_run_id),
            "research_type": research_type,
            "ttl_hours": ttl_hours,
            "expires_at": expires_at.isoformat(),
        }

        self._memory_cache[cache_key] = data
        if self._client:
            try:
                self._client.table("research_cache").upsert(
                    data, on_conflict="cache_key"
                ).execute()
            except Exception as e:
                logger.warning(f"Supabase cache write failed: {e}")

    def invalidate(self, cache_key: str):
        """Delete a cache entry."""
        try:
            self._client.table("research_cache").delete().eq(
                "cache_key", cache_key
            ).execute()
            logger.info(f"Cache invalidated: key={cache_key}")
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
