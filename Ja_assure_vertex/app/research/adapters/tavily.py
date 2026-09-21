"""Tavily Research Adapter.

Owns the Tavily SDK, retries, timeouts, and vendor error translation.
Business logic never touches the Tavily SDK directly.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Protocol

from app.research.enums import TavilyOperation
from app.research.models import PlannedQuery, RawSource, ResearchPlan

logger = logging.getLogger("ja_assure")


# ── Protocol (for testing / swapping) ─────────────────────────────

class TavilyAdapterProtocol(Protocol):
    def search(self, query: PlannedQuery) -> list[RawSource]: ...
    def extract(self, urls: list[str]) -> list[RawSource]: ...
    def research(self, query: PlannedQuery) -> list[RawSource]: ...


# ── Concrete Implementation ──────────────────────────────────────

class TavilyResearchAdapter:
    """Adapter wrapping the tavily-python SDK."""

    def __init__(self, api_key: str):
        from tavily import TavilyClient
        self._api_key = api_key or ""
        self._client = TavilyClient(api_key=api_key)

    def search(self, query: PlannedQuery) -> list[RawSource]:
        """Execute a Tavily search."""
        logger.info(f"Tavily search: query='{query.query}', max_results={query.max_results}")
        try:
            response = self._client.search(
                query=query.query,
                max_results=query.max_results,
                search_depth="advanced",
                include_raw_content=False,
            )
            return self._parse_search_results(response, query)
        except Exception as e:
            logger.error(f"Tavily search failed: {type(e).__name__}: {e}")
            raise

    def extract(self, urls: list[str]) -> list[RawSource]:
        """Extract content from specific URLs."""
        if not urls:
            return []
        logger.info(f"Tavily extract: {len(urls)} URLs")
        try:
            response = self._client.extract(urls=urls)
            return self._parse_extract_results(response)
        except Exception as e:
            logger.error(f"Tavily extract failed: {type(e).__name__}: {e}")
            raise

    def research(self, query: PlannedQuery) -> list[RawSource]:
        """Deep research — most expensive, used only at HIGH complexity."""
        logger.info(f"Tavily research (deep): query='{query.query}'")
        try:
            # Use search with advanced depth as research equivalent
            response = self._client.search(
                query=query.query,
                max_results=min(query.max_results, 20),
                search_depth="advanced",
                include_raw_content=True,
            )
            return self._parse_search_results(response, query)
        except Exception as e:
            logger.error(f"Tavily research failed: {type(e).__name__}: {e}")
            raise

    def _parse_search_results(
        self, response: dict, query: PlannedQuery
    ) -> list[RawSource]:
        """Parse Tavily search response into RawSource objects."""
        sources: list[RawSource] = []
        results = response.get("results", [])

        for r in results:
            published = self._parse_date(r.get("published_date"))
            sources.append(RawSource(
                url=r.get("url", ""),
                title=r.get("title"),
                content=r.get("content") or r.get("raw_content"),
                published_at=published,
                score=r.get("score"),
                source_operation=query.operation,
                query=query.query,
                raw=r,
            ))

        logger.info(f"Tavily search returned {len(sources)} results")
        return sources

    def _parse_extract_results(self, response: dict) -> list[RawSource]:
        """Parse Tavily extract response into RawSource objects."""
        sources: list[RawSource] = []
        results = response.get("results", [])

        for r in results:
            sources.append(RawSource(
                url=r.get("url", ""),
                title=None,
                content=r.get("raw_content") or r.get("content"),
                published_at=None,
                score=None,
                source_operation=TavilyOperation.EXTRACT,
                query="extract",
                raw=r,
            ))

        logger.info(f"Tavily extract returned {len(sources)} results")
        return sources

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse a date string without using AI."""
        if not date_str:
            return None
        try:
            from dateutil import parser as dateutil_parser
            return dateutil_parser.parse(date_str).replace(tzinfo=timezone.utc)
        except Exception:
            logger.debug(f"Could not parse date: {date_str}")
            return None

    def execute_plan(
        self,
        plan: ResearchPlan,
        max_sources: int,
    ) -> tuple[list[RawSource], int, list[str]]:
        """Execute all queries in a research plan."""
        if not self._api_key or self._api_key.startswith("tvly-placeholder") or len(self._api_key) < 10:
            logger.warning("Tavily API key is unconfigured or placeholder — skipping live Tavily search.")
            return [], 0, ["Tavily API key unconfigured"]

        all_sources: list[RawSource] = []
        tavily_calls = 0
        failed_queries: list[str] = []
        used_research = False

        for pq in plan.queries:
            if len(all_sources) >= max_sources:
                logger.info(f"Max sources ({max_sources}) reached, stopping queries")
                break

            try:
                # Select operation based on plan
                if pq.operation == TavilyOperation.RESEARCH and not used_research:
                    sources = self._retry(lambda: self.research(pq), retries=1, backoff=[3])
                    used_research = True
                else:
                    sources = self._retry(lambda: self.search(pq), retries=2, backoff=[1, 3])

                all_sources.extend(sources)
                tavily_calls += 1
            except Exception as e:
                logger.warning(
                    f"Query failed (isolated): query='{pq.query}', "
                    f"error={type(e).__name__}: {e}"
                )
                failed_queries.append(pq.query)
                tavily_calls += 1  # still count the attempt

        # Optional: extract high-value URLs if extract policy is enabled
        if plan.extract_policy.enabled and all_sources:
            extract_candidates = [
                s for s in all_sources
                if s.score is not None
                and s.score >= plan.extract_policy.min_search_score
                and (not s.content or len(s.content or "") < plan.extract_policy.min_content_chars)
            ]
            extract_urls = [s.url for s in extract_candidates[:plan.extract_policy.max_urls]]

            if extract_urls:
                try:
                    extracted = self._retry(
                        lambda: self.extract(extract_urls), retries=2, backoff=[1, 3]
                    )
                    all_sources.extend(extracted)
                    tavily_calls += 1
                except Exception as e:
                    logger.warning(f"Extract step failed: {e}")

        return all_sources, tavily_calls, failed_queries

    def _retry(self, fn, retries: int = 2, backoff: list[float] | None = None):
        """Retry a function with exponential backoff."""
        if backoff is None:
            backoff = [1, 3]

        last_error = None
        for attempt in range(1 + retries):
            try:
                return fn()
            except Exception as e:
                last_error = e
                if attempt < retries:
                    delay = backoff[min(attempt, len(backoff) - 1)]
                    logger.warning(
                        f"Retry {attempt + 1}/{retries}: sleeping {delay}s, "
                        f"error={type(e).__name__}"
                    )
                    time.sleep(delay)
        raise last_error
