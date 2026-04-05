from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.api.dependencies.models import models_dependency
from app.api.schemas.resume import ResumeRequest, ResumeResponse
from app.core.logger import get_logger
from app.services.matcher import match_score
from app.services.resume_parser import parse_resume
from app.services.skill_extractor import extract_skills
from app.utils.file_handler import read_upload_bytes
from ml.predictor import predict

logger = get_logger("resume_route")
router = APIRouter(prefix="/resume", tags=["Resume Screening"])


@router.post(
    "/screen",
    response_model=ResumeResponse,
    summary="Screen resume text",
    description=(
        "Submit raw resume text and receive a predicted job role, "
        "ensemble confidence, top-3 matches, and extracted skills."
    ),
)
async def screen_resume(
    request: ResumeRequest,
    models: dict = Depends(models_dependency),
) -> ResumeResponse:
    """
    Screen a resume from plain text.

    - **text**: Raw resume text (20–10 000 characters)
    - Returns predicted role, confidence score, top-3 matches, and skills
    """
    try:
        result = predict(request.text, models)
        skills = extract_skills(request.text)
        score = match_score(skills)

        return ResumeResponse(
            predicted_role=result["role"].replace("_", " ").title(),
            confidence=f"{round(result['confidence'] * 100)}%",
            top_matches=[r.replace("_", " ").title() for r in result["top3"]],
            extracted_skills=skills,
            match_score=score,
        )
    except Exception as e:
        logger.error("Prediction failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed. Please try again.",
        )


@router.post(
    "/screen/upload",
    response_model=ResumeResponse,
    summary="Screen resume from file upload",
    description=(
        "Upload a resume file (.pdf, .txt, or .docx) and receive a predicted "
        "job role with confidence score."
    ),
)
async def screen_resume_upload(
    file: UploadFile = File(..., description="Resume file (.pdf, .txt, or .docx)"),
    models: dict = Depends(models_dependency),
) -> ResumeResponse:
    """
    Screen a resume uploaded as a file.

    - **file**: PDF, TXT, or DOCX resume (max 5 MB)
    - Returns predicted role, confidence, top-3 matches, and skills
    """
    file_bytes, filename = await read_upload_bytes(file)

    try:
        text = parse_resume(file_bytes, filename)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    try:
        result = predict(text, models)
        skills = extract_skills(text)
        score = match_score(skills)

        return ResumeResponse(
            predicted_role=result["role"].replace("_", " ").title(),
            confidence=f"{round(result['confidence'] * 100)}%",
            top_matches=[r.replace("_", " ").title() for r in result["top3"]],
            extracted_skills=skills,
            match_score=score,
        )
    except Exception as e:
        logger.error("Prediction failed for %s: %s", filename, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed. Please try again.",
        )
