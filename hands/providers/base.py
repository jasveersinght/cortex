"""The provider contract. Swap Buffer for anything else by implementing this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ProviderError(Exception):
    """Base class for provider failures."""


class TransientProviderError(ProviderError):
    """Worth retrying (rate limit, network blip).

    ambiguous=True means the provider MAY have accepted the request before we lost
    the answer (read timeout, 5xx). Retrying blindly could double-post, so those go
    to 'needs_review' instead of being retried automatically.
    """

    def __init__(self, message: str, ambiguous: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.ambiguous = ambiguous
        self.retry_after = retry_after


class PermanentProviderError(ProviderError):
    """Retrying will not help (bad channel, text too long, auth failure)."""


@dataclass
class PostPayload:
    text: str
    platform: str
    brand: str | None
    scheduled_for: datetime
    media_url: str | None = None
    media_type: str | None = None      # image | video
    first_comment: str | None = None
    ai_generated: bool = False
    idempotency_key: str = ""


@dataclass
class ProviderResult:
    post_id: str
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderMetrics:
    status: str | None = None          # scheduled | sent | error (provider wording, lower-cased)
    impressions: float | None = None
    reach: float | None = None
    views: float | None = None
    likes: float | None = None
    comments: float | None = None
    shares: float | None = None
    saves: float | None = None
    clicks: float | None = None
    engagement_rate: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return any(
            v is not None
            for v in (self.impressions, self.reach, self.views, self.likes, self.comments, self.shares, self.saves, self.clicks)
        )


class Provider(ABC):
    name = "base"

    @abstractmethod
    def validate(self, platform: str, brand: str | None) -> str | None:
        """Return an error message if this provider cannot post to platform/brand, else None."""

    @abstractmethod
    def schedule_post(self, payload: PostPayload) -> ProviderResult: ...

    @abstractmethod
    def fetch_metrics(self, post_id: str, platform: str) -> ProviderMetrics | None: ...

    def health(self) -> dict[str, Any]:
        return {"provider": self.name, "ok": True}
