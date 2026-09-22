"""Tiny Supabase (PostgREST) client. Plain HTTP, so there is no SDK version to fight with.

Use the *service_role* key (server side only, never in a browser). Tables have RLS enabled
with no policies, so the public anon key can read nothing.
"""
from __future__ import annotations

from typing import Any

import requests


class SupabaseError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class SupabaseRest:
    def __init__(self, url: str, key: str, session: requests.Session | None = None, timeout: int = 20):
        self.url = url.rstrip("/")
        self.key = key
        self.session = session or requests.Session()
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.key)

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(self, method: str, table: str, *, params: dict[str, str] | None = None, json: Any = None, prefer: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            raise SupabaseError("Supabase is not configured (URL/key missing)")
        try:
            resp = self.session.request(method, f"{self.url}/rest/v1/{table}", params=params, json=json,
                                        headers=self._headers(prefer), timeout=self.timeout)
        except requests.RequestException as exc:
            raise SupabaseError(f"network error talking to Supabase: {exc}") from exc
        if resp.status_code >= 300:
            raise SupabaseError(f"Supabase {method} {table} -> HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code)
        try:
            data = resp.json() if resp.text else []
        except ValueError:
            data = []
        return data if isinstance(data, list) else [data]

    def upsert(self, table: str, rows: dict[str, Any] | list[dict[str, Any]], on_conflict: str) -> list[dict[str, Any]]:
        rows = rows if isinstance(rows, list) else [rows]
        if not rows:
            return []
        return self._request("POST", table, params={"on_conflict": on_conflict}, json=rows,
                             prefer="resolution=merge-duplicates,return=representation")

    def insert(self, table: str, rows: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = rows if isinstance(rows, list) else [rows]
        return self._request("POST", table, json=rows, prefer="return=representation") if rows else []

    def select(self, table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        return self._request("GET", table, params=params or {})

    def ping(self, table: str) -> bool:
        try:
            self.select(table, {"limit": "1"})
            return True
        except SupabaseError:
            return False
