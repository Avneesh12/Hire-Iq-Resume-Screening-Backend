from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import get_current_user
from app.api.schemas.schemas import (
    AddNoteRequest, ApiResponse, BulkStatusRequest,
    CandidateStatus, UpdateStatusRequest,
)
from app.core.logger import get_logger
from app.db.models import Candidate, JobOpening, RecruiterNote, User
from app.db.redis import cache_delete_pattern
from app.db.session import get_db

logger = get_logger("candidates")
router = APIRouter(prefix="/candidates", tags=["Candidates"])


def _serialize(c: Candidate) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "location": c.location,
        "status": c.status,
        "appliedJobId": c.applied_job_id,
        "appliedJobTitle": c.applied_job.title if c.applied_job else None,
        "resumeUploadId": c.resume_upload_id,
        "parsedResume": c.parsed_resume or {},
        "score": c.score,
        "recruiterNotes": [
            {
                "id": n.id,
                "authorId": n.author_id,
                "authorName": n.author.name if n.author else "Unknown",
                "content": n.content,
                "createdAt": n.created_at.isoformat(),
            }
            for n in (c.notes or [])
        ],
        "assessmentResults": [],
        "tags": c.tags or [],
        "createdAt": c.created_at.isoformat(),
        "updatedAt": c.updated_at.isoformat(),
        "avatarUrl": c.avatar_url,
    }


@router.get("", response_model=dict)
async def list_candidates(
    search: str | None = Query(None),
    status: CandidateStatus | None = Query(None),
    # Frontend sends snake_case params
    job_id: str | None = Query(None, alias="job_id"),
    min_score: float | None = Query(None, alias="min_score"),
    max_score: float | None = Query(None, alias="max_score"),
    sort_by: str = Query("createdAt", alias="sort_by"),
    sort_order: str = Query("desc", alias="sort_order"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="page_size"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    q = select(Candidate).options(
        selectinload(Candidate.notes).selectinload(RecruiterNote.author),
        selectinload(Candidate.applied_job),
    )

    if search:
        q = q.where(
            or_(
                Candidate.name.ilike(f"%{search}%"),
                Candidate.email.ilike(f"%{search}%"),
            )
        )
    if status:
        q = q.where(Candidate.status == status)
    if job_id:
        q = q.where(Candidate.applied_job_id == job_id)
    if min_score is not None:
        q = q.where(Candidate.score["overall"].as_float() >= min_score)
    if max_score is not None:
        q = q.where(Candidate.score["overall"].as_float() <= max_score)

    # Sorting
    if sort_by == "name":
        col = Candidate.name.asc() if sort_order == "asc" else Candidate.name.desc()
    elif sort_by == "status":
        col = Candidate.status.asc() if sort_order == "asc" else Candidate.status.desc()
    elif sort_by == "score":
        col = (
            Candidate.score["overall"].as_float().asc()
            if sort_order == "asc"
            else Candidate.score["overall"].as_float().desc()
        )
    else:
        col = Candidate.created_at.asc() if sort_order == "asc" else Candidate.created_at.desc()
    q = q.order_by(col)

    total = await db.scalar(select(func.count()).select_from(q.subquery())) or 0
    result = await db.execute(q.offset((page - 1) * page_size).limit(page_size))
    candidates = result.scalars().all()

    return {
        "data": [_serialize(c) for c in candidates],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/{candidate_id}", response_model=dict)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.notes).selectinload(RecruiterNote.author),
            selectinload(Candidate.applied_job),
        )
        .where(Candidate.id == candidate_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return _serialize(c)


@router.patch("/{candidate_id}/status", response_model=dict)
async def update_status(
    candidate_id: str,
    body: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Candidate)
        .options(
            selectinload(Candidate.notes).selectinload(RecruiterNote.author),
            selectinload(Candidate.applied_job),
        )
        .where(Candidate.id == candidate_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    c.status = body.status
    c.updated_at = datetime.now(timezone.utc)
    await cache_delete_pattern("analytics:*")
    return _serialize(c)


@router.post("/{candidate_id}/notes", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_note(
    candidate_id: str,
    body: AddNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    c = await db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    note = RecruiterNote(
        candidate_id=candidate_id,
        author_id=current_user.id,
        content=body.content,
    )
    db.add(note)
    await db.flush()
    return {
        "id": note.id,
        "authorId": note.author_id,
        "authorName": current_user.name,
        "content": note.content,
        "createdAt": note.created_at.isoformat(),
    }


@router.get("/{candidate_id}/score", response_model=dict)
async def get_score(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    c = await db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not c.score:
        raise HTTPException(status_code=404, detail="Score not yet available.")
    return c.score


@router.patch("/bulk-status", response_model=ApiResponse)
async def bulk_update_status(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ApiResponse:
    result = await db.execute(select(Candidate).where(Candidate.id.in_(body.ids)))
    candidates = result.scalars().all()
    now = datetime.now(timezone.utc)
    for c in candidates:
        c.status = body.status
        c.updated_at = now
    await cache_delete_pattern("analytics:*")
    logger.info("Bulk status update: %d candidates → %s", len(candidates), body.status)
    return ApiResponse(success=True, message=f"Updated {len(candidates)} candidates.", data=None)
