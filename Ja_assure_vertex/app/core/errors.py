from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorResponse(BaseModel):
    error: ErrorDetail

class DiscoverException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

# Standard Error Codes (as specified by user)
INVALID_RESEARCH_REQUEST = "INVALID_RESEARCH_REQUEST"
RESEARCH_RUN_NOT_FOUND = "RESEARCH_RUN_NOT_FOUND"
RESEARCH_RUN_FAILED = "RESEARCH_RUN_FAILED"
TAVILY_ERROR = "TAVILY_ERROR"
GROQ_ERROR = "GROQ_ERROR"
SUPABASE_ERROR = "SUPABASE_ERROR"
CACHE_ERROR = "CACHE_ERROR"
INVALID_AI_OUTPUT = "INVALID_AI_OUTPUT"

async def discover_exception_handler(request: Request, exc: DiscoverException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}}
    )
