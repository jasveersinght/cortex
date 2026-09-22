"""Calls the content agent over HTTP exactly as it is. The request body is passed through untouched."""
from __future__ import annotations

import time
from typing import Any

import requests


class ContentAgentError(Exception):
    pass


class ContentClient:
    def __init__(self, base_url: str, session: requests.Session | None = None, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def generate(self, request_body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """POST /api/content/generate. Returns (response_json, latency_ms)."""
        started = time.perf_counter()
        try:
            resp = self.session.post(f"{self.base_url}/api/content/generate", json=request_body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ContentAgentError(f"content agent unreachable at {self.base_url}: {exc}") from exc
        latency = int((time.perf_counter() - started) * 1000)
        if resp.status_code >= 400:
            raise ContentAgentError(f"content agent returned HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise ContentAgentError("content agent did not return JSON") from exc
        if not isinstance(data, dict):
            raise ContentAgentError("content agent returned an unexpected JSON shape")
        return data, latency

    def reachable(self) -> bool:
        try:
            self.session.get(f"{self.base_url}/openapi.json", timeout=5)
            return True
        except requests.RequestException:
            return False
