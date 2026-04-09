import base64
import mimetypes
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import get_current_user
from app.api.schemas.schemas import ApiResponse
from app.core.config import settings
from app.core.logger import get_logger
from app.db.models import JobOpening, ResumeUpload, UploadBatch, User
from app.db.redis import cache_delete_pattern
from app.db.session import get_db
from app.utils.file_handler import validate_upload

logger = get_logger("uploads")
router = APIRouter(tags=["Uploads"])


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_upload(u: ResumeUpload) -> dict:
    return {
        "id": u.id,
        "filename": u.filename,
        "fileSize": u.file_size,
        "mimeType": u.mime_type,
        "status": u.status,
        "candidateId": u.candidate_id,
        "jobId": u.job_id,
        "uploadedAt": u.uploaded_at.isoformat(),
        "processedAt": u.processed_at.isoformat() if u.processed_at else None,
        "errorMessage": u.error_message,
        "parsedData": u.parsed_data,
    }


def _serialize_batch(b: UploadBatch, job_title: str | None = None) -> dict:
    return {
        "id": b.id,
        "uploadedAt": b.uploaded_at.isoformat(),
        "totalFiles": b.total_files,
        "processedFiles": b.processed_files,
        "failedFiles": b.failed_files,
        "jobId": b.job_id,
        "jobTitle": job_title or (b.job.title if b.job else None),
        "uploads": [_serialize_upload(u) for u in (b.uploads or [])],
        "status": b.status,
    }


def _resolve_batch_status(processed: int, failed: int, total: int) -> str:
    if total == 0:
        return "complete"
    if processed + failed < total:
        return "processing"
    if failed == 0:
        return "complete"
    if processed > 0:
        return "partial_failure"
    return "partial_failure"


def _display_name_from_filename(filename: str) -> str:
    return filename.rsplit(".", 1)[0].replace("_", " ").strip().title() or "Unknown Candidate"


def _normalize_identity(upload_id: str, filename: str, fields: dict) -> tuple[str, str]:
    name = (fields.get("name") or "").strip() or _display_name_from_filename(filename)
    email = (fields.get("email") or "").strip().lower() or f"{upload_id[:8]}@pending.hireiq"
    return name, email


# ── Core inline processor ─────────────────────────────────────────────────────

async def _process_inline(
    db: AsyncSession,
    batch: UploadBatch,
    upload: ResumeUpload,
    file_bytes: bytes,
    filename: str,
    job_id: str | None,
) -> None:
    """Process a resume synchronously (Celery fallback for dev mode)."""
    from app.db.models import Candidate
    from app.services.resume_parser import parse_resume
    from app.services.skill_extractor import extract_skills
    from app.services.scorer import score_resume
    from app.services.field_extractor import extract_all_fields

    try:
        text = parse_resume(file_bytes, filename)
        skills = extract_skills(text)
        fields = extract_all_fields(text)
        score_data = await score_resume(text, skills)

        # Try ML enrichment
        ml_data: dict = {}
        try:
            from ml.loader import get_models
            from ml.predictor import predict
            models = get_models()
            if models:
                ml_result = predict(text, models)
                ml_data = {
                    "predictedRole": ml_result["role"].replace("_", " ").title(),
                    "mlConfidence": ml_result["confidence"],
                }
        except Exception as e:
            logger.debug("ML unavailable: %s", e)

        parsed: dict = {
            "rawText": text,
            "name": fields.get("name"),
            "email": fields.get("email"),
            "phone": fields.get("phone"),
            "location": fields.get("location"),
            "summary": fields.get("summary"),
            "skills": skills,
            "experience": fields.get("experience", []),
            "education": fields.get("education", []),
            "certifications": fields.get("certifications", []),
            "languages": fields.get("languages", []),
            "totalExperienceYears": fields.get("totalExperienceYears"),
            **ml_data,
        }

        cand_name, cand_email = _normalize_identity(upload.id, filename, fields)
        candidate = Candidate(
            name=cand_name,
            email=cand_email,
            phone=fields.get("phone"),
            location=fields.get("location"),
            applied_job_id=job_id,
            resume_upload_id=upload.id,
            parsed_resume=parsed,
            score=score_data,
            status="new",
            tags=[],
        )
        db.add(candidate)
        await db.flush()

        upload.status = "scored"
        upload.candidate_id = candidate.id
        upload.processed_at = datetime.now(timezone.utc)
        upload.parsed_data = parsed
        batch.processed_files = (batch.processed_files or 0) + 1
        logger.info("Inline processed: upload=%s candidate=%s score=%.1f",
                    upload.id, candidate.id, score_data.get("overall", 0))
    except Exception as exc:
        logger.error("Inline processing failed for %s: %s", filename, exc, exc_info=True)
        upload.status = "failed"
        upload.error_message = str(exc)
        batch.failed_files = (batch.failed_files or 0) + 1


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/resumes/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_resumes(
    files: list[UploadFile] = File(...),
    job_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Upload one or more resumes. Creates UploadBatch + Candidates."""
    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.MAX_BATCH_FILES} files per batch.",
        )

    job_title: str | None = None
    if job_id:
        job = await db.get(JobOpening, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        job_title = job.title

    batch = UploadBatch(
        uploaded_by=current_user.id,
        job_id=job_id,
        total_files=len(files),
        processed_files=0,
        failed_files=0,
        status="uploading",
    )
    db.add(batch)
    await db.flush()

    inline_used = False

    for file in files:
        filename = file.filename or "unknown"
        mime = file.content_type or (mimetypes.guess_type(filename)[0] or "application/octet-stream")

        try:
            file_bytes = await validate_upload(file)
        except HTTPException as e:
            db.add(ResumeUpload(
                batch_id=batch.id,
                filename=filename,
                file_size=0,
                mime_type=mime,
                status="failed",
                job_id=job_id,
                error_message=e.detail,
            ))
            batch.failed_files += 1
            continue

        upload = ResumeUpload(
            batch_id=batch.id,
            filename=filename,
            file_size=len(file_bytes),
            mime_type=mime,
            status="pending",
            job_id=job_id,
        )
        db.add(upload)
        await db.flush()

        try:
            from app.workers.resume_processor import process_resume_task
            process_resume_task.delay(
                upload.id,
                base64.b64encode(file_bytes).decode(),
                filename,
                job_id,
            )
        except Exception as e:
            logger.warning("Celery unavailable, falling back to inline: %s", e)
            inline_used = True
            await _process_inline(db, batch, upload, file_bytes, filename, job_id)

    batch.status = _resolve_batch_status(
        batch.processed_files, batch.failed_files, batch.total_files
    ) if inline_used else "processing"

    await db.commit()
    await db.refresh(batch, attribute_names=["uploads"])
    await cache_delete_pattern("analytics:*")

    return _serialize_batch(batch, job_title)


@router.get("/resumes/batches", response_model=dict)
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="page_size"),
    job_id: str | None = Query(None, alias="job_id"),
    status: str | None = Query(None),
    date_from: str | None = Query(None, alias="date_from"),
    date_to: str | None = Query(None, alias="date_to"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    q = select(UploadBatch).options(
        selectinload(UploadBatch.uploads),
        selectinload(UploadBatch.job),
    )
    if job_id:
        q = q.where(UploadBatch.job_id == job_id)
    if status:
        q = q.where(UploadBatch.status == status)
    q = q.order_by(UploadBatch.uploaded_at.desc())

    total = await db.scalar(select(func.count()).select_from(q.subquery())) or 0
    result = await db.execute(q.offset((page - 1) * page_size).limit(page_size))
    batches = result.scalars().all()

    return {
        "data": [_serialize_batch(b) for b in batches],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/resumes/batches/{batch_id}", response_model=dict)
async def get_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(UploadBatch)
        .options(selectinload(UploadBatch.uploads), selectinload(UploadBatch.job))
        .where(UploadBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    return _serialize_batch(batch)


@router.post("/resumes/{upload_id}/retry", response_model=dict)
async def retry_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    upload = await db.get(ResumeUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")
    if upload.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed uploads can be retried.")
    upload.status = "pending"
    upload.error_message = None
    await db.commit()
    return _serialize_upload(upload)


@router.delete("/resumes/{upload_id}", response_model=ApiResponse)
async def delete_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ApiResponse:
    upload = await db.get(ResumeUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")
    await db.delete(upload)
    await db.commit()
    return ApiResponse(success=True, message="Upload deleted.", data=None)
