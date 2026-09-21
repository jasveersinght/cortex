"""Enumerations for the Research / Discover Agent."""

from enum import Enum


class ResearchType(str, Enum):
    COMPETITOR_MONITORING = "competitor_monitoring"
    MARKET_RESEARCH = "market_research"
    TREND_RESEARCH = "trend_research"
    CAMPAIGN_RESEARCH = "campaign_research"


class Complexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TavilyOperation(str, Enum):
    SEARCH = "search"
    EXTRACT = "extract"
    CRAWL = "crawl"
    MAP = "map"
    RESEARCH = "research"


class RunStatus(str, Enum):
    IDLE = "IDLE"
    CHECKING_CACHE = "CHECKING_CACHE"
    PLANNING = "PLANNING"
    RETRIEVING = "RETRIEVING"
    NORMALIZING = "NORMALIZING"
    FILTERING = "FILTERING"
    DETECTING_CHANGES = "DETECTING_CHANGES"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"


class SourceType(str, Enum):
    WEB = "web"
    NEWS = "news"
    COMPANY_SITE = "company_site"
    REGULATOR = "regulator"
    INDUSTRY = "industry"
    SOCIAL = "social"
    OTHER = "other"


class Relevance(str, Enum):
    RELEVANT = "RELEVANT"
    UNCERTAIN = "UNCERTAIN"
    IRRELEVANT = "IRRELEVANT"


class ChangeStatus(str, Enum):
    NEW = "NEW"
    CHANGED = "CHANGED"
    UNCHANGED = "UNCHANGED"
    REMOVED = "REMOVED"


class FindingType(str, Enum):
    PRODUCT_LAUNCH = "product_launch"
    SERVICE_LAUNCH = "service_launch"
    CAMPAIGN = "campaign"
    PARTNERSHIP = "partnership"
    PRICING_CHANGE = "pricing_change"
    MARKET_ENTRY = "market_entry"
    MARKET_EXIT = "market_exit"
    MARKET_GAP = "market_gap"
    TECHNOLOGY_CHANGE = "technology_change"
    CUSTOMER_SIGNAL = "customer_signal"
    INDUSTRY_TREND = "industry_trend"
    TREND = "trend"
    REGULATORY_CHANGE = "regulatory_change"
    SOCIAL_SIGNAL = "social_signal"
    OTHER = "other"


class ExtractPolicy(str, Enum):
    DISABLED = "disabled"
    ON_DEMAND = "on_demand"


# Valid markets for JA Assure
VALID_MARKETS = [
    "Singapore",
    "Malaysia",
    "Hong Kong",
    "Indonesia",
    "Thailand",
]
