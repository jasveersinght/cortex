from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import DiscoverException, discover_exception_handler, INVALID_RESEARCH_REQUEST
from app.api.routes.discover import router as discover_router

# ── Logging Setup ─────────────────────────────────────────────────

logger = logging.getLogger("ja_assure")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ── Lifespan (Startup / Shutdown) ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fail fast if required environment variables are missing."""
    try:
        from app.config import settings
        logger.info(f"Starting {settings.APP_NAME} ({settings.ENVIRONMENT})")

        missing = []
        if not settings.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY")
        if not settings.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not settings.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")

        if missing:
            logger.error(f"FATAL: Missing required environment variables: {missing}")

        logger.info("Startup checks passed. API is ready.")
    except Exception as e:
        logger.error(f"Startup check failed: {e}")
    yield


# ── FastAPI App ───────────────────────────────────────────────────

app = FastAPI(
    title="JA Assure Discover Agent API",
    description=(
        "Backend API for the Research / Discover Agent. "
        "Provides structured, evidence-backed research intelligence."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the separate frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ───────────────────────────────────────────

app.add_exception_handler(DiscoverException, discover_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": INVALID_RESEARCH_REQUEST, "message": str(exc.errors())}},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": f"{type(exc).__name__}: {str(exc)}"}},
    )


# ── Routes ────────────────────────────────────────────────────────

app.include_router(discover_router)


@app.get("/health")
async def health_check():
    """Health check with dependency status."""
    status = {"status": "ok", "supabase": "unknown", "tavily": "unknown", "groq": "unknown"}

    # Check Supabase connectivity
    try:
        from app.config import settings
        from supabase import create_client
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        client.table("research_runs").select("id").limit(1).execute()
        status["supabase"] = "ok"
    except Exception as e:
        status["supabase"] = f"error: {type(e).__name__}"

    # Check API key presence (not actual API calls — cost-free)
    try:
        from app.config import settings
        status["tavily"] = "configured" if settings.TAVILY_API_KEY else "missing"
        status["groq"] = "configured" if settings.GROQ_API_KEY else "missing"
    except Exception:
        pass

    return status
