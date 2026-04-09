from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, cast, Date, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.core.logger import get_logger
from app.db.models import Candidate, ResumeUpload, UploadBatch, User
from app.db.redis import (
    cache_get, cache_set,
    key_analytics_funnel, key_analytics_metrics,
    key_analytics_score_dist, key_analytics_skills,
    key_analytics_trends,
)
from app.db.session import get_db

logger = get_logger("analytics")
router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/metrics", response_model=dict)
async def dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    cached = await cache_get(key_analytics_metrics())
    if cached:
        return cached

    total = await db.scalar(select(func.count(Candidate.id))) or 0

    shortlisted = await db.scalar(
        select(func.count(Candidate.id)).where(Candidate.status == "shortlisted")
    ) or 0

    pending = await db.scalar(
        select(func.count(Candidate.id)).where(
            Candidate.status.in_(["new", "under_review"])
        )
    ) or 0

    # Average score from JSONB column
    avg_score = await db.scalar(
        select(func.avg(Candidate.score["overall"].as_float())).where(
            Candidate.score.isnot(None)
        )
    ) or 0.0

    processing_q = await db.scalar(
        select(func.count(UploadBatch.id)).where(UploadBatch.status == "processing")
    ) or 0

    today = datetime.now(timezone.utc).date()
    today_uploads = await db.scalar(
        select(func.count(UploadBatch.id)).where(
            func.date(UploadBatch.uploaded_at) == today
        )
    ) or 0

    processed = await db.scalar(func.sum(UploadBatch.processed_files)) or 0

    # Week-over-week change
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_this_week = await db.scalar(
        select(func.count(Candidate.id)).where(Candidate.created_at >= week_ago)
    ) or 0

    result = {
        "totalCandidates": total,
        "resumesProcessed": processed,
        "shortlisted": shortlisted,
        "pendingReview": pending,
        "averageScore": round(float(avg_score), 1),
        "processingQueue": processing_q,
        "todayUploads": today_uploads,
        "weeklyChange": {
            "candidates": new_this_week,
            "processed": new_this_week,
            "shortlisted": max(0, shortlisted - max(0, shortlisted - 2)),
        },
    }
    await cache_set(key_analytics_metrics(), result, ttl=settings.ANALYTICS_CACHE_TTL)
    return result


@router.get("/upload-trends", response_model=list)
async def upload_trends(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    cached = await cache_get(key_analytics_trends(days))
    if cached:
        return cached

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            cast(UploadBatch.uploaded_at, Date).label("date"),
            func.sum(UploadBatch.total_files).label("uploads"),
            func.sum(UploadBatch.processed_files).label("processed"),
            func.sum(UploadBatch.failed_files).label("failed"),
        )
        .where(UploadBatch.uploaded_at >= since)
        .group_by(cast(UploadBatch.uploaded_at, Date))
        .order_by(cast(UploadBatch.uploaded_at, Date))
    )
    rows = result.all()

    # Fill in missing days with zeros
    date_map = {
        str(r.date): {"date": str(r.date), "uploads": r.uploads, "processed": r.processed, "failed": r.failed}
        for r in rows
    }
    trend = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        trend.append(date_map.get(d, {"date": d, "uploads": 0, "processed": 0, "failed": 0}))

    await cache_set(key_analytics_trends(days), trend, ttl=settings.ANALYTICS_CACHE_TTL)
    return trend


@router.get("/score-distribution", response_model=list)
async def score_distribution(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    cached = await cache_get(key_analytics_score_dist())
    if cached:
        return cached

    # Use JSONB extraction and case expression in PostgreSQL
    score_col = Candidate.score["overall"].as_float()
    result = await db.execute(
        select(
            case(
                (score_col <= 20, "0-20"),
                (score_col <= 40, "21-40"),
                (score_col <= 60, "41-60"),
                (score_col <= 80, "61-80"),
                else_="81-100",
            ).label("range"),
            func.count().label("count"),
        )
        .where(Candidate.score.isnot(None))
        .group_by(text("range"))
    )
    rows = {r.range: r.count for r in result}

    dist = [
        {"range": r, "count": rows.get(r, 0)}
        for r in ["0-20", "21-40", "41-60", "61-80", "81-100"]
    ]
    await cache_set(key_analytics_score_dist(), dist, ttl=settings.ANALYTICS_CACHE_TTL)
    return dist


@router.get("/skills", response_model=list)
async def skill_frequency(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    cached = await cache_get(key_analytics_skills(limit))
    if cached:
        return cached

    # Unnest the JSONB skills array and count occurrences
    result = await db.execute(
        text("""
            SELECT skill, COUNT(*) as cnt
            FROM candidates,
                 jsonb_array_elements_text(parsed_resume->'skills') AS skill
            GROUP BY skill
            ORDER BY cnt DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.all()
    total = await db.scalar(select(func.count(Candidate.id))) or 1

    data = [
        {
            "skill": r.skill,
            "count": r.cnt,
            "percentage": round(r.cnt / total * 100, 1),
        }
        for r in rows
    ]
    await cache_set(key_analytics_skills(limit), data, ttl=settings.ANALYTICS_CACHE_TTL)
    return data


@router.get("/funnel", response_model=list)
async def conversion_funnel(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    cached = await cache_get(key_analytics_funnel())
    if cached:
        return cached

    statuses_per_stage = [
        ("Applied", None),   # all candidates
        ("Screened", ["under_review", "shortlisted", "assessment_sent",
                       "assessment_complete", "interviewing", "offered", "hired"]),
        ("Shortlisted", ["shortlisted", "assessment_sent",
                          "assessment_complete", "interviewing", "offered", "hired"]),
        ("Assessment", ["assessment_sent", "assessment_complete", "interviewing", "offered", "hired"]),
        ("Interview", ["interviewing", "offered", "hired"]),
        ("Offer", ["offered", "hired"]),
        ("Hired", ["hired"]),
    ]

    funnel = []
    for stage, statuses in statuses_per_stage:
        if statuses is None:
            count = await db.scalar(select(func.count(Candidate.id))) or 0
        else:
            count = await db.scalar(
                select(func.count(Candidate.id)).where(Candidate.status.in_(statuses))
            ) or 0
        funnel.append({"stage": stage, "count": count})

    await cache_set(key_analytics_funnel(), funnel, ttl=settings.ANALYTICS_CACHE_TTL)
    return funnel
