from __future__ import annotations

from ..config import Settings
from .base import (
    PermanentProviderError,
    PostPayload,
    Provider,
    ProviderError,
    ProviderMetrics,
    ProviderResult,
    TransientProviderError,
)
from .buffer import BufferProvider
from .mock import MockProvider


def build_provider(settings: Settings) -> Provider:
    """DRY_RUN=true always wins, so a demo can never post for real by accident."""
    if settings.dry_run or settings.provider == "mock":
        return MockProvider(fail_rate=settings.mock_fail_rate)
    if settings.provider == "buffer":
        return BufferProvider(
            api_key=settings.buffer_api_key,
            channel_map=settings.buffer_channel_map,
            api_url=settings.buffer_api_url,
            scheduling_type=settings.buffer_scheduling_type,
        )
    raise ValueError(f"unknown PROVIDER '{settings.provider}' (use 'mock' or 'buffer')")


__all__ = [
    "BufferProvider", "MockProvider", "Provider", "ProviderError", "TransientProviderError",
    "PermanentProviderError", "PostPayload", "ProviderResult", "ProviderMetrics", "build_provider",
]
