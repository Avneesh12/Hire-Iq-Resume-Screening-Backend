from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import get_current_user
from app.api.schemas.schemas import ApiResponse, AssignRequest, CreateAssessmentRequest
from app.core.logger import get_logger
from app.db.models import Assessment, AssessmentAssignment, Candidate, User
from app.db.session import get_db

logger = get_logger("assessments")
router = APIRouter(prefix="/assessments", tags=["Assessments"])


def _serialize_assessment(a: Assessment) -> dict:
    assignments = a.assignments or []
    return {
        "id": a.id,
        "title": a.title,
        "type": a.assessment_type,
        "description": a.description,
        "durationMinutes": a.duration_minutes,
        "totalQuestions": a.total_questions,
        "maxScore": a.max_score,
        "status": a.status,
        "createdAt": a.created_at.isoformat(),
        "assignedCount": len(assignments),
        "completedCount": sum(1 for x in assignments if x.status == "submitted"),
    }


def _serialize_assignment(aa: AssessmentAssignment) -> dict:
    return {
        "id": aa.id,
        "assessmentId": aa.assessment_id,
        "assessmentTitle": aa.assessment.title if aa.assessment else "",
        "candidateId": aa.candidate_id,
        "candidateName": aa.candidate.name if aa.candidate else "",
        "candidateEmail": aa.candidate.email if aa.candidate else "",
        "status": aa.status,
        "sentAt": aa.sent_at.isoformat(),
        "expiresAt": aa.expires_at.isoformat(),
        "startedAt": aa.started_at.isoformat() if aa.started_at else None,
        "submittedAt": aa.submitted_at.isoformat() if aa.submitted_at else None,
        "result": aa.result,
    }


@router.get("", response_model=list)
async def list_assessments(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    result = await db.execute(
        select(Assessment)
        .options(selectinload(Assessment.assignments))
        .order_by(Assessment.created_at.desc())
    )
    return [_serialize_assessment(a) for a in result.scalars().all()]


@router.get("/assignments", response_model=list)
async def list_assignments(
    candidate_id: str | None = Query(None),
    assessment_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    q = select(AssessmentAssignment).options(
        selectinload(AssessmentAssignment.assessment),
        selectinload(AssessmentAssignment.candidate),
    )
    if candidate_id:
        q = q.where(AssessmentAssignment.candidate_id == candidate_id)
    if assessment_id:
        q = q.where(AssessmentAssignment.assessment_id == assessment_id)
    result = await db.execute(q)
    return [_serialize_assignment(aa) for aa in result.scalars().all()]


@router.get("/{assessment_id}", response_model=dict)
async def get_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Assessment)
        .options(selectinload(Assessment.assignments))
        .where(Assessment.id == assessment_id)
    )
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return _serialize_assessment(a)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    body: CreateAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    assessment = Assessment(
        title=body.title,
        assessment_type=body.type,
        description=body.description,
        duration_minutes=body.duration_minutes,
        total_questions=body.total_questions,
        max_score=body.max_score,
        status=body.status,
    )
    db.add(assessment)
    await db.flush()
    # Re-query to get empty assignments list for serialisation
    await db.refresh(assessment)
    logger.info("Assessment created: %s (%s)", body.title, assessment.id)
    return _serialize_assessment(assessment)


@router.delete("/{assessment_id}", response_model=ApiResponse)
async def delete_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ApiResponse:
    a = await db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    await db.delete(a)
    return ApiResponse(success=True, message="Assessment deleted.", data=None)


@router.post("/assign", response_model=list, status_code=status.HTTP_201_CREATED)
async def assign_assessment(
    body: AssignRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    assessment = await db.get(Assessment, body.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=7)
    created = []

    for cid in body.candidate_ids:
        candidate = await db.get(Candidate, cid)
        if not candidate:
            continue

        # Skip if already assigned
        existing = await db.scalar(
            select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == body.assessment_id,
                AssessmentAssignment.candidate_id == cid,
            )
        )
        if existing:
            continue

        aa = AssessmentAssignment(
            assessment_id=body.assessment_id,
            candidate_id=cid,
            status="sent",
            sent_at=now,
            expires_at=expires,
        )
        db.add(aa)
        candidate.status = "assessment_sent"
        await db.flush()

        created.append({
            "id": aa.id,
            "assessmentId": aa.assessment_id,
            "assessmentTitle": assessment.title,
            "candidateId": cid,
            "candidateName": candidate.name,
            "candidateEmail": candidate.email,
            "status": "sent",
            "sentAt": now.isoformat(),
            "expiresAt": expires.isoformat(),
            "startedAt": None,
            "submittedAt": None,
            "result": None,
        })

    if not created:
        raise HTTPException(
            status_code=400,
            detail="No valid or unassigned candidates found.",
        )

    logger.info("Assigned assessment %s to %d candidates", body.assessment_id, len(created))
    return created
