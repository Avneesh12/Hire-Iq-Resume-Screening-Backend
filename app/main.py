from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import resume_router
from app.core.config import settings
from app.core.logger import get_logger
from ml.loader import load_models

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML models once at startup; release resources on shutdown."""
    logger.info("Starting up — loading models...")
    load_models()
    logger.info("Models loaded. Application ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(resume_router, prefix="/api/v1")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Health check")
async def health() -> dict:
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": settings.APP_VERSION}
