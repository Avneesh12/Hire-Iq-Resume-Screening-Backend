"""
Redis client — used for:
  1. Response caching (analytics, job lists, etc.)
  2. JWT token denylist (logout invalidation)
  3. Upload processing queue (via Celery broker)
"""
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("redis")

# Single connection pool shared across the app
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    """Return deserialized value or None on miss."""
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL_SECONDS) -> None:
    """Serialize and store with TTL (seconds)."""
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, default=str))


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    r = await get_redis()
    keys = await r.keys(pattern)
    if keys:
        return await r.delete(*keys)
    return 0


# ── Token denylist (logout) ───────────────────────────────────────────────────

DENYLIST_PREFIX = "token:denied:"


async def deny_token(jti: str, ttl_seconds: int) -> None:
    """Add a JWT ID to the denylist until it naturally expires."""
    r = await get_redis()
    await r.setex(f"{DENYLIST_PREFIX}{jti}", ttl_seconds, "1")


async def is_token_denied(jti: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(f"{DENYLIST_PREFIX}{jti}"))


# ── Cache key builders ────────────────────────────────────────────────────────

def key_analytics_metrics() -> str:
    return "analytics:metrics"

def key_analytics_funnel() -> str:
    return "analytics:funnel"

def key_analytics_skills(limit: int) -> str:
    return f"analytics:skills:{limit}"

def key_analytics_score_dist() -> str:
    return "analytics:score_distribution"

def key_analytics_trends(days: int) -> str:
    return f"analytics:upload_trends:{days}"

def key_candidate(candidate_id: str) -> str:
    return f"candidate:{candidate_id}"

def key_job(job_id: str) -> str:
    return f"job:{job_id}"

def key_jobs_list() -> str:
    return "jobs:list"
