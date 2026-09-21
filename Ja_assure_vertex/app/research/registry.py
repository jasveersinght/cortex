"""Research type registry.

Adding a new research type requires only a new entry here
plus its query templates. No changes to ResearchManager,
the Tavily adapter, the evidence processor, or the Groq analyst.
"""

from app.research.enums import Complexity, ResearchType
from app.research.models import ResearchTypeConfig

RESEARCH_TYPE_REGISTRY: dict[ResearchType, ResearchTypeConfig] = {
    ResearchType.COMPETITOR_MONITORING: ResearchTypeConfig(
        name="Competitor Monitoring",
        query_templates=[
            "{competitor} new product launch {market}",
            "{competitor} pricing {market}",
            "{competitor} marketing campaign {market}",
            "{competitor} partnership {market}",
            "{competitor} product update {market}",
            "{competitor} market expansion {market}",
            "{competitor} technology {market}",
        ],
        ttl_hours=24,
        default_complexity=Complexity.MEDIUM,
        default_lookback_days=30,
        requires_competitors=True,
        finding_type_hints=[
            "product_launch", "service_launch", "campaign",
            "partnership", "pricing_change", "market_entry",
            "technology_change",
        ],
    ),
    ResearchType.MARKET_RESEARCH: ResearchTypeConfig(
        name="Market Research",
        query_templates=[
            "{brand} market size {market}",
            "new entrants {industry} {market}",
            "regulation {industry} {market}",
            "customer demand {industry} {market}",
            "distribution channels {industry} {market}",
        ],
        ttl_hours=24,
        default_complexity=Complexity.MEDIUM,
        default_lookback_days=90,
        requires_competitors=False,
        finding_type_hints=[
            "market_entry", "market_exit", "regulatory_change",
            "customer_signal", "industry_trend",
        ],
    ),
    ResearchType.TREND_RESEARCH: ResearchTypeConfig(
        name="Trend Research",
        query_templates=[
            "emerging trends {industry} {market}",
            "{industry} news {market}",
            "technology shifts {industry} {market}",
            "{industry} commentary analysis {market}",
        ],
        ttl_hours=6,
        default_complexity=Complexity.LOW,
        default_lookback_days=14,
        requires_competitors=False,
        finding_type_hints=[
            "industry_trend", "technology_change",
            "customer_signal", "social_signal",
        ],
    ),
    ResearchType.CAMPAIGN_RESEARCH: ResearchTypeConfig(
        name="Campaign Research",
        query_templates=[
            "{competitor} advertising campaign {market}",
            "{competitor} marketing messaging {market}",
            "{competitor} creative themes {market}",
            "{competitor} marketing channels {market}",
        ],
        ttl_hours=12,
        default_complexity=Complexity.MEDIUM,
        default_lookback_days=60,
        requires_competitors=True,
        finding_type_hints=[
            "campaign", "social_signal", "customer_signal",
        ],
    ),
}


def get_research_config(research_type: ResearchType) -> ResearchTypeConfig:
    """Get configuration for a research type from the registry."""
    return RESEARCH_TYPE_REGISTRY[research_type]
