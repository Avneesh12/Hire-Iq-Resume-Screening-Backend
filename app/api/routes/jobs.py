from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.schemas.schemas import ApiResponse, CreateJobRequest
from app.core.logger import get_logger
from app.db.models import Candidate, JobOpening, User
from app.db.redis import cache_delete, cache_get, cache_set, key_job, key_jobs_list
from app.db.session import get_db

logger = get_logger("jobs")
router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _serialize(job: JobOpening, candidate_count: int = 0, shortlisted_count: int = 0) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "location": job.location,
        # DB stores as job_type; frontend expects "type"
        "type": job.job_type,
        "status": job.status,
        "description": job.description,
        "requiredSkills": job.required_skills or [],
        "preferredSkills": job.preferred_skills or [],
        "minExperienceYears": job.min_experience_years,
        "maxExperienceYears": job.max_experience_years,
        "salaryMin": job.salary_min,
        "salaryMax": job.salary_max,
        "currency": job.currency,
        "candidateCount": candidate_count,
        "shortlistedCount": shortlisted_count,
        "createdAt": job.created_at.isoformat(),
        "closingDate": job.closing_date.isoformat() if job.closing_date else None,
        "hiringManagerId": job.hiring_manager_id,
    }


async def _candidate_counts(db: AsyncSession, job_id: str) -> tuple[int, int]:
    total = await db.scalar(
        select(func.count()).where(Candidate.applied_job_id == job_id)
    ) or 0
    shortlisted = await db.scalar(
        select(func.count()).where(
            Candidate.applied_job_id == job_id,
            Candidate.status == "shortlisted",
        )
    ) or 0
    return total, shortlisted


@router.get("", response_model=dict)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="page_size"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    cached = await cache_get(key_jobs_list())
    if cached:
        return cached

    result = await db.execute(
        select(JobOpening).order_by(JobOpening.created_at.desc())
    )
    jobs = result.scalars().all()

    data = []
    for job in jobs:
        total, shortlisted = await _candidate_counts(db, job.id)
        data.append(_serialize(job, total, shortlisted))

    total_count = len(data)
    response = {
        "data": data,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total_count // page_size)),
    }
    await cache_set(key_jobs_list(), response, ttl=120)
    return response


@router.get("/{job_id}", response_model=dict)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    cached = await cache_get(key_job(job_id))
    if cached:
        return cached

    job = await db.get(JobOpening, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    total, shortlisted = await _candidate_counts(db, job_id)
    result = _serialize(job, total, shortlisted)
    await cache_set(key_job(job_id), result, ttl=120)
    return result


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    job = JobOpening(
        title=body.title,
        department=body.department,
        location=body.location,
        job_type=body.type,
        status=body.status,
        description=body.description,
        required_skills=body.required_skills,
        preferred_skills=body.preferred_skills,
        min_experience_years=body.min_experience_years,
        max_experience_years=body.max_experience_years,
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        currency=body.currency,
        closing_date=body.closing_date,
        hiring_manager_id=body.hiring_manager_id or current_user.id,
    )
    db.add(job)
    await db.flush()
    await cache_delete(key_jobs_list())
    logger.info("Job created: %s (%s)", body.title, job.id)
    return _serialize(job)


@router.patch("/{job_id}", response_model=dict)
async def update_job(
    job_id: str,
    body: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    job = await db.get(JobOpening, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    data = body.model_dump(exclude_unset=True, by_alias=False)
    for field, value in data.items():
        # "type" in schema → "job_type" in ORM
        db_field = "job_type" if field == "type" else field
        if hasattr(job, db_field):
            setattr(job, db_field, value)
    job.updated_at = datetime.now(timezone.utc)

    await cache_delete(key_job(job_id))
    await cache_delete(key_jobs_list())
    total, shortlisted = await _candidate_counts(db, job_id)
    return _serialize(job, total, shortlisted)


@router.delete("/{job_id}", response_model=ApiResponse)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ApiResponse:
    job = await db.get(JobOpening, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    await db.delete(job)
    await cache_delete(key_job(job_id))
    await cache_delete(key_jobs_list())
    return ApiResponse(success=True, message="Job deleted.", data=None)


@router.get("/{job_id}/candidates", response_model=dict)
async def get_job_candidates(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="page_size"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    if not await db.get(JobOpening, job_id):
        raise HTTPException(status_code=404, detail="Job not found.")

    total_q = select(func.count()).where(Candidate.applied_job_id == job_id)
    total = await db.scalar(total_q) or 0

    result = await db.execute(
        select(Candidate)
        .where(Candidate.applied_job_id == job_id)
        .order_by(Candidate.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    candidates = result.scalars().all()

    return {
        "data": [
            {
                "id": c.id, "name": c.name, "email": c.email,
                "status": c.status, "score": c.score,
                "appliedJobId": c.applied_job_id,
                "createdAt": c.created_at.isoformat(),
            }
            for c in candidates
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }
