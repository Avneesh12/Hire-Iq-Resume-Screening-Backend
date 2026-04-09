"""
Celery worker — processes resume files asynchronously after upload.
Runs separately from the FastAPI process:
    celery -A app.workers.resume_processor worker --loglevel=info
"""
import asyncio
from datetime import datetime, timezone

from celery import Celery

from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import AsyncSessionLocal
from app.db.models import Candidate, ResumeUpload, UploadBatch
from app.db.redis import cache_delete_pattern
from app.services.resume_parser import parse_resume
from app.services.skill_extractor import extract_skills
from app.services.scorer import score_resume

logger = get_logger("worker")

celery_app = Celery(
    "hireiq",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # fair dispatch — one task per worker at a time
)


def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


def _display_name_from_filename(filename: str) -> str:
    return filename.rsplit(".", 1)[0].replace("_", " ").strip().title() or "Unknown Candidate"


def _normalize_candidate_identity(upload_id: str, filename: str, extracted_fields: dict) -> tuple[str, str]:
    name = (extracted_fields.get("name") or "").strip() or _display_name_from_filename(filename)
    email = (extracted_fields.get("email") or "").strip().lower() or f"{upload_id[:8]}@pending.hireiq"
    return name, email


@celery_app.task(
    name="process_resume",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def process_resume_task(self, upload_id: str, file_bytes_b64: str, filename: str, job_id: str | None):
    """
    Background task:
      1. Parse resume text from file bytes
      2. Extract skills
      3. Run ML scoring
      4. Create Candidate row
      5. Update ResumeUpload status
      6. Bust analytics cache
    """
    import base64
    file_bytes = base64.b64decode(file_bytes_b64)

    async def _process():
        async with AsyncSessionLocal() as db:
            upload = await db.get(ResumeUpload, upload_id)
            if not upload:
                logger.error("Upload %s not found", upload_id)
                return

            try:
                upload.status = "processing"
                await db.commit()

                # Parse text
                text = parse_resume(file_bytes, filename)
                skills = extract_skills(text)
                
                # Extract all fields (experience, education, certifications, languages, etc.)
                from app.services.field_extractor import extract_all_fields
                extracted_fields = extract_all_fields(text)
                
                score_data = await score_resume(text, skills)

                # Try to use ML screening for better parsed data
                ml_screening_data = None
                try:
                    from ml.loader import get_models
                    from ml.predictor import predict
                    models = get_models()
                    if models:
                        ml_result = predict(text, models)
                        ml_screening_data = {
                            "predicted_role": ml_result["role"].replace("_", " ").title(),
                            "confidence": ml_result["confidence"],
                            "top_matches": [r.replace("_", " ").title() for r in ml_result["top3"]],
                        }
                        logger.info("ML screening successful for %s: %s", filename, ml_screening_data.get("predicted_role"))
                except Exception as e:
                    logger.debug("ML screening unavailable for %s: %s", filename, e)

                # Build parsed resume dict with all extracted fields
                parsed = {
                    "rawText": text,
                    "name": extracted_fields.get("name"),
                    "email": extracted_fields.get("email"),
                    "phone": extracted_fields.get("phone"),
                    "location": extracted_fields.get("location"),
                    "summary": extracted_fields.get("summary"),
                    "skills": skills,
                    "experience": extracted_fields.get("experience", []),
                    "education": extracted_fields.get("education", []),
                    "certifications": extracted_fields.get("certifications", []),
                    "languages": extracted_fields.get("languages", []),
                    "totalExperienceYears": extracted_fields.get("totalExperienceYears"),
                }
                
                # Add ML screening data if available
                if ml_screening_data:
                    parsed.update(ml_screening_data)

                # Create Candidate
                candidate_name, candidate_email = _normalize_candidate_identity(upload_id, filename, extracted_fields)
                candidate = Candidate(
                    name=candidate_name,
                    email=candidate_email,
                    phone=extracted_fields.get("phone"),
                    location=extracted_fields.get("location"),
                    applied_job_id=job_id,
                    resume_upload_id=upload_id,
                    parsed_resume=parsed,
                    score=score_data,
                    status="new",
                    tags=[],
                )
                db.add(candidate)
                await db.flush()

                # Update upload
                upload.status = "scored"
                upload.candidate_id = candidate.id
                upload.processed_at = datetime.now(timezone.utc)
                upload.parsed_data = parsed

                # Update batch progress
                batch = await db.get(UploadBatch, upload.batch_id)
                if batch:
                    batch.processed_files = (batch.processed_files or 0) + 1
                    processed = batch.processed_files + batch.failed_files
                    if processed >= batch.total_files:
                        batch.status = "complete" if batch.failed_files == 0 else "partial_failure"

                await db.commit()
                # Bust analytics cache
                await cache_delete_pattern("analytics:*")
                logger.info("Processed resume %s → candidate %s", upload_id, candidate.id)

            except Exception as exc:
                upload.status = "failed"
                upload.error_message = str(exc)
                # Update batch failed count
                batch = await db.get(UploadBatch, upload.batch_id)
                if batch:
                    batch.failed_files = (batch.failed_files or 0) + 1
                    processed = batch.processed_files + batch.failed_files
                    if processed >= batch.total_files:
                        batch.status = "partial_failure"
                await db.commit()
                logger.error("Failed to process upload %s: %s", upload_id, exc)
                raise

    run_async(_process())
