from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    analytics_router,
    assessments_router,
    auth_router,
    candidates_router,
    jobs_router,
    resume_router,
    uploads_router,
)
from app.core.config import settings
from app.core.logger import get_logger
from app.db.redis import close_redis, get_redis
from app.db.session import engine

logger = get_logger("main")

PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting HireIQ API v%s [%s]", settings.APP_VERSION, settings.ENV)

    # Verify DB connectivity
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected.")
    except Exception as e:
        logger.error("PostgreSQL connection failed: %s", e)

    # Verify Redis connectivity
    try:
        r = await get_redis()
        await r.ping()
        logger.info("Redis connected.")
    except Exception as e:
        logger.error("Redis connection failed: %s", e)

    # Load ML models (non-fatal)
    try:
        from ml.loader import load_models
        load_models()
        logger.info("ML models loaded.")
    except Exception as e:
        logger.warning("ML models not loaded (non-fatal): %s", e)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    await close_redis()
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    # Hide docs in production
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled %s on %s %s: %s",
        type(exc).__name__, request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router,        prefix=PREFIX)
app.include_router(candidates_router,  prefix=PREFIX)
app.include_router(uploads_router,     prefix=PREFIX)
app.include_router(jobs_router,        prefix=PREFIX)
app.include_router(assessments_router, prefix=PREFIX)
app.include_router(analytics_router,   prefix=PREFIX)
app.include_router(resume_router,      prefix=PREFIX)


# ── Health / Root ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    return {
        "name": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Liveness probe — returns 200 when the API is running."""
    checks: dict = {"api": "ok"}

    try:
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"

    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ok" if all_ok else "degraded", "checks": checks, "version": settings.APP_VERSION},
    )
