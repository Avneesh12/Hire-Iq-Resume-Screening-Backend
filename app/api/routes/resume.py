"""
Resume screening endpoint.
POST /api/v1/resume/screen  — matches a resume against a job's required skills.
Frontend sends: { job_id, resume_text, parsed_resume? }
Frontend expects: ResumeScreeningResult shape.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.logger import get_logger
from app.db.models import JobOpening, User
from app.db.session import get_db
from app.services.matcher import match_score
from app.services.skill_extractor import extract_skills

logger = get_logger("resume")
router = APIRouter(prefix="/resume", tags=["Resume Screening"])


class ScreeningRequest(BaseModel):
    job_id: str
    resume_text: str = Field(min_length=10)
    parsed_resume: dict | None = None   # optional ParsedResume dict


class ScreeningResult(BaseModel):
    matchScore: float
    matchPercentage: float
    recommendation: str     # strong_match | match | weak_match | no_match
    matchedSkills: list[str]
    missingSkills: list[str]
    experienceMatch: bool
    strengths: list[str]
    gaps: list[str]
    summary: str


@router.post("/screen", response_model=ScreeningResult)
async def screen_resume(
    body: ScreeningRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ScreeningResult:
    # Load job to get required skills + experience requirements
    job = await db.get(JobOpening, body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    required_skills: list[str] = [s.lower() for s in (job.required_skills or [])]
    preferred_skills: list[str] = [s.lower() for s in (job.preferred_skills or [])]
    min_exp: int = job.min_experience_years or 0

    # Extract candidate skills from resume text
    candidate_skills: list[str] = extract_skills(body.resume_text)

    # If parsed_resume already has skills, merge them
    if body.parsed_resume and body.parsed_resume.get("skills"):
        extra = [s.lower() for s in body.parsed_resume["skills"]]
        candidate_skills = list(set(candidate_skills) | set(extra))

    # Matching
    candidate_set = set(candidate_skills)
    required_set = set(required_skills)
    preferred_set = set(preferred_skills)

    matched_required = sorted(candidate_set & required_set)
    matched_preferred = sorted(candidate_set & preferred_set)
    missing_required = sorted(required_set - candidate_set)

    raw_score = match_score(candidate_skills, required_skills) if required_skills else min(len(candidate_skills) / 15.0, 1.0)
    match_pct = round(raw_score * 100, 1)

    # Experience match heuristic
    total_exp_years: float | None = None
    if body.parsed_resume:
        total_exp_years = body.parsed_resume.get("totalExperienceYears")
    experience_match = (total_exp_years is None) or (total_exp_years >= min_exp)

    # Recommendation thresholds
    if match_pct >= 80:
        recommendation = "strong_match"
    elif match_pct >= 60:
        recommendation = "match"
    elif match_pct >= 35:
        recommendation = "weak_match"
    else:
        recommendation = "no_match"

    # Strengths = matched skills + preferred skills found
    strengths: list[str] = []
    if matched_required:
        strengths.append(f"Matches {len(matched_required)} of {len(required_set)} required skills")
    if matched_preferred:
        strengths.append(f"Has {len(matched_preferred)} preferred skills: {', '.join(matched_preferred[:3])}")
    if experience_match and total_exp_years is not None:
        strengths.append(f"{total_exp_years:.0f} years of experience meets the {min_exp}+ year requirement")

    # Gaps
    gaps: list[str] = []
    if missing_required:
        gaps.append(f"Missing required skills: {', '.join(missing_required[:5])}")
    if not experience_match and total_exp_years is not None:
        gaps.append(f"Has {total_exp_years:.0f} years experience but {min_exp}+ required")

    # Summary
    summary = (
        f"Candidate matches {len(matched_required)}/{len(required_set) or 1} required skills "
        f"({match_pct:.0f}% match). "
        f"Recommendation: {recommendation.replace('_', ' ').title()}."
    )

    return ScreeningResult(
        matchScore=round(raw_score, 4),
        matchPercentage=match_pct,
        recommendation=recommendation,
        matchedSkills=matched_required + [s for s in matched_preferred if s not in matched_required],
        missingSkills=missing_required,
        experienceMatch=experience_match,
        strengths=strengths or ["Resume processed successfully"],
        gaps=gaps,
        summary=summary,
    )
