"""Mock provider for demos and tests. NOTHING is posted and the metrics are SYNTHETIC."""
from __future__ import annotations

import hashlib
import random

from .base import PostPayload, Provider, ProviderMetrics, ProviderResult, TransientProviderError

# rough plausible ranges per platform: (impressions min/max, engagement-rate min/max in %)
_RANGES = {
    "linkedin": ((300, 4000), (0.6, 6.0)),
    "instagram": ((400, 6000), (0.8, 7.0)),
    "x": ((150, 3000), (0.3, 3.5)),
    "tiktok": ((800, 20000), (1.5, 12.0)),
}


class MockProvider(Provider):
    name = "mock"

    def __init__(self, fail_rate: float = 0.0):
        self.fail_rate = fail_rate

    def validate(self, platform: str, brand: str | None) -> str | None:
        return None

    def schedule_post(self, payload: PostPayload) -> ProviderResult:
        if self.fail_rate and random.random() < self.fail_rate:
            raise TransientProviderError("mock: simulated rate limit (429)")
        digest = hashlib.sha1((payload.idempotency_key or payload.text).encode()).hexdigest()[:12]
        return ProviderResult(
            post_id=f"mock_{digest}",
            url=f"https://example.invalid/{payload.platform}/{digest}",
            raw={"mock": True, "note": "nothing was posted"},
        )

    def fetch_metrics(self, post_id: str, platform: str) -> ProviderMetrics | None:
        rng = random.Random(post_id)  # deterministic per post
        (imp_lo, imp_hi), (er_lo, er_hi) = _RANGES.get(platform, _RANGES["linkedin"])
        impressions = rng.randint(imp_lo, imp_hi)
        er = rng.uniform(er_lo, er_hi) / 100
        interactions = impressions * er
        return ProviderMetrics(
            status="sent",
            impressions=impressions,
            reach=round(impressions * rng.uniform(0.6, 0.9)),
            likes=round(interactions * 0.70),
            comments=round(interactions * 0.12),
            shares=round(interactions * 0.10),
            saves=round(interactions * 0.08),
            clicks=round(impressions * rng.uniform(0.002, 0.02)),
            raw={"mock": True, "synthetic": "demo data, not real engagement"},
        )
