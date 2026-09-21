"""Request schemas for the Discover API."""

from pydantic import BaseModel, Field, field_validator
from app.research.enums import ResearchType, VALID_MARKETS


class ResearchRequest(BaseModel):
    """Request to start a research run."""
    brand: str = Field(..., min_length=1, max_length=120, description="Brand name to research.")
    market: str = Field(..., description="Target market. One of: Singapore, Malaysia, Hong Kong, Indonesia, Thailand.")
    research_type: ResearchType = Field(..., description="Type of research to perform.")
    objective: str | None = Field(None, max_length=500, description="Optional free-text research objective.")
    competitors: list[str] = Field(default_factory=list, description="Optional list of competitors (max 10).")
    topics: list[str] = Field(default_factory=list, description="Optional list of topics (max 10).")
    lookback_days: int | None = Field(None, ge=1, le=365, description="Lookback window in days.")
    force_refresh: bool = Field(False, description="If true, bypass cache.")
    max_sources: int = Field(20, description="Maximum sources to retrieve (5..50). Clamped if out of range.")

    @field_validator("brand")
    @classmethod
    def validate_brand(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Brand must not be empty.")
        return v

    @field_validator("market")
    @classmethod
    def validate_market(cls, v: str) -> str:
        v = v.strip()
        if v not in VALID_MARKETS:
            raise ValueError(f"Market must be one of: {', '.join(VALID_MARKETS)}. Got: '{v}'")
        return v

    @field_validator("competitors")
    @classmethod
    def validate_competitors(cls, v: list[str]) -> list[str]:
        # Strip, drop empties, deduplicate case-insensitively, cap at 10
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in v:
            stripped = item.strip()
            if stripped and stripped.lower() not in seen:
                seen.add(stripped.lower())
                cleaned.append(stripped)
        return cleaned[:10]

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in v:
            stripped = item.strip()
            if stripped and stripped.lower() not in seen:
                seen.add(stripped.lower())
                cleaned.append(stripped)
        return cleaned[:10]

    @field_validator("objective")
    @classmethod
    def validate_objective(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("max_sources")
    @classmethod
    def clamp_max_sources(cls, v: int) -> int:
        return max(5, min(50, v))
