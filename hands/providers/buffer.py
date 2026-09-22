"""Buffer GraphQL provider (https://developers.buffer.com).

Notes from Buffer's docs that shape this file:
* GraphQL always answers HTTP 200; failures are typed `MutationError`s in `data`,
  system errors are in the top-level `errors` array.
* Scheduling uses `mode: customScheduled` + `dueAt` (UTC ISO). Media must be a public URL.
* Instagram requires `metadata.instagram.shouldShareToFeed` and `type`.
* Post metrics need a personal API key and refresh roughly once a day, and a metric
  missing from the response means "not reported yet", NOT zero.
"""
from __future__ import annotations

from typing import Any

import requests

from ..utils import to_iso
from .base import (
    PermanentProviderError,
    PostPayload,
    Provider,
    ProviderMetrics,
    ProviderResult,
    TransientProviderError,
)

CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt text } }
    ... on MutationError { message }
  }
}
"""

POST_METRICS = """
query PostMetrics($id: PostId!) {
  post(input: { id: $id }) {
    id
    status
    metrics { type name value unit }
    metricsUpdatedAt
  }
}
"""

# Buffer PostMetricType -> our snapshot column
_METRIC_MAP = {
    "impressions": "impressions",
    "reach": "reach",
    "views": "views",
    "reactions": "likes",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "reposts": "shares",
    "saves": "saves",
    "clicks": "clicks",
    "linkclicks": "clicks",
    "engagementrate": "engagement_rate",
}
_ACCUMULATE = {"shares"}  # reposts + shares are added together

_TRANSIENT_HINTS = ("rate limit", "too many", "try again", "temporar", "timeout", "unavailable")


class BufferProvider(Provider):
    name = "buffer"

    def __init__(self, api_key: str, channel_map: dict[str, str], api_url: str = "https://api.buffer.com",
                 scheduling_type: str = "automatic", timeout: int = 30, session: requests.Session | None = None):
        self.api_key = api_key
        self.channel_map = {k.lower(): v for k, v in channel_map.items()}
        self.api_url = api_url
        self.scheduling_type = scheduling_type if scheduling_type in {"automatic", "notification"} else "automatic"
        self.timeout = timeout
        self.session = session or requests.Session()

    # ---- helpers ---------------------------------------------------------
    def _channel_id(self, platform: str, brand: str | None) -> str | None:
        if brand:
            hit = self.channel_map.get(f"{brand.strip().lower()}:{platform}")
            if hit:
                return hit
        return self.channel_map.get(platform)

    def validate(self, platform: str, brand: str | None) -> str | None:
        if not self.api_key:
            return "BUFFER_API_KEY is not set"
        if not self._channel_id(platform, brand):
            return f"no Buffer channel configured for '{platform}' (set BUFFER_CHANNEL_MAP)"
        return None

    def _gql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.session.post(
                self.api_url,
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.ConnectionError as exc:  # never reached the server: safe to retry
            raise TransientProviderError(f"connection error: {exc}") from exc
        except requests.Timeout as exc:  # may have been processed: do NOT auto-retry
            raise TransientProviderError(f"timeout: {exc}", ambiguous=True) from exc

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 0) or 0) or None
            raise TransientProviderError("Buffer rate limit (HTTP 429)", retry_after=retry_after)
        if resp.status_code in (401, 403):
            raise PermanentProviderError(f"Buffer rejected the API key (HTTP {resp.status_code})")
        if resp.status_code >= 500:
            raise TransientProviderError(f"Buffer server error (HTTP {resp.status_code})", ambiguous=True)
        if resp.status_code >= 400:
            raise PermanentProviderError(f"Buffer HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            body = resp.json()
        except ValueError as exc:
            raise TransientProviderError("Buffer returned non-JSON", ambiguous=True) from exc

        errors = body.get("errors")
        if errors:
            first = errors[0]
            code = (first.get("extensions") or {}).get("code", "")
            msg = f"Buffer error {code}: {first.get('message', '')}".strip()
            if code in {"UNAUTHORIZED", "FORBIDDEN"}:
                raise PermanentProviderError(msg)
            if code in {"RATE_LIMITED", "RATE_LIMIT_EXCEEDED"}:
                raise TransientProviderError(msg)
            if code == "INTERNAL_SERVER_ERROR":
                raise TransientProviderError(msg, ambiguous=True)
            raise PermanentProviderError(msg)
        return body.get("data") or {}

    # ---- contract --------------------------------------------------------
    def schedule_post(self, payload: PostPayload) -> ProviderResult:
        problem = self.validate(payload.platform, payload.brand)
        if problem:
            raise PermanentProviderError(problem)

        post_input: dict[str, Any] = {
            "text": payload.text,
            "channelId": self._channel_id(payload.platform, payload.brand),
            "schedulingType": self.scheduling_type,
            "mode": "customScheduled",
            "dueAt": to_iso(payload.scheduled_for),
        }
        if payload.media_url and payload.media_type in {"image", "video"}:
            post_input["assets"] = [{payload.media_type: {"url": payload.media_url}}]

        metadata: dict[str, Any] = {}
        if payload.platform == "instagram":
            ig: dict[str, Any] = {
                "type": "reel" if payload.media_type == "video" else "post",
                "shouldShareToFeed": True,
            }
            if payload.first_comment:
                ig["firstComment"] = payload.first_comment
            if payload.ai_generated:
                ig["isAiGenerated"] = True
            metadata["instagram"] = ig
        elif payload.platform == "linkedin" and payload.first_comment:
            metadata["linkedin"] = {"firstComment": payload.first_comment}
        elif payload.platform == "tiktok" and payload.ai_generated and payload.media_type == "video":
            metadata["tiktok"] = {"isAiGenerated": True}
        if metadata:
            post_input["metadata"] = metadata

        data = self._gql(CREATE_POST, {"input": post_input}).get("createPost") or {}
        post = data.get("post")
        if post and post.get("id"):
            return ProviderResult(post_id=post["id"], url=None, raw=data)

        message = str(data.get("message") or "Buffer returned no post and no error message")
        if any(h in message.lower() for h in _TRANSIENT_HINTS):
            raise TransientProviderError(f"Buffer: {message}")
        raise PermanentProviderError(f"Buffer: {message}")

    def fetch_metrics(self, post_id: str, platform: str) -> ProviderMetrics | None:
        data = self._gql(POST_METRICS, {"id": post_id}).get("post")
        if not data:
            return None
        metrics = ProviderMetrics(status=str(data.get("status") or "").lower() or None, raw=data)
        for m in data.get("metrics") or []:
            key = _METRIC_MAP.get(str(m.get("type", "")).replace("_", "").lower())
            if not key:
                continue
            value = float(m.get("value") or 0)
            current = getattr(metrics, key)
            setattr(metrics, key, (current or 0) + value if key in _ACCUMULATE else value)
        return metrics

    def health(self) -> dict[str, Any]:
        info: dict[str, Any] = {"provider": self.name, "configured": bool(self.api_key), "channels": sorted(self.channel_map)}
        if not self.api_key:
            info["ok"] = False
            return info
        try:
            data = self._gql("query { account { organizations { id name } } }", {})
            info["ok"] = True
            info["organizations"] = (data.get("account") or {}).get("organizations", [])
        except Exception as exc:  # noqa: BLE001 - health must never raise
            info["ok"] = False
            info["error"] = str(exc)
        return info

    def list_channels(self, organization_id: str) -> list[dict[str, Any]]:
        query = "query C($org: OrganizationId!) { channels(input: { organizationId: $org }) { id name displayName service } }"
        return self._gql(query, {"org": organization_id}).get("channels") or []
