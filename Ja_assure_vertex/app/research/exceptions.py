"""Research-specific exceptions."""

from app.core.errors import DiscoverException


class ResearchRunNotFound(DiscoverException):
    def __init__(self, run_id: str):
        super().__init__(
            code="RESEARCH_RUN_NOT_FOUND",
            message=f"Research run '{run_id}' not found.",
            status_code=404,
        )


class InvalidResearchRequest(DiscoverException):
    def __init__(self, message: str):
        super().__init__(
            code="INVALID_RESEARCH_REQUEST",
            message=message,
            status_code=422,
        )


class TavilyError(DiscoverException):
    def __init__(self, message: str):
        super().__init__(
            code="TAVILY_ERROR",
            message=message,
            status_code=502,
        )


class GroqError(DiscoverException):
    def __init__(self, message: str):
        super().__init__(
            code="GROQ_ERROR",
            message=message,
            status_code=502,
        )


class SupabaseError(DiscoverException):
    def __init__(self, message: str):
        super().__init__(
            code="SUPABASE_ERROR",
            message=message,
            status_code=500,
        )


class CacheError(DiscoverException):
    def __init__(self, message: str):
        super().__init__(
            code="CACHE_ERROR",
            message=message,
            status_code=500,
        )


class InvalidAIOutput(DiscoverException):
    def __init__(self, message: str):
        super().__init__(
            code="INVALID_AI_OUTPUT",
            message=message,
            status_code=500,
        )
