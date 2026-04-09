from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Shared config ─────────────────────────────────────────────────────────────

class CamelModel(BaseModel):
    """Base model: snake_case internally, camelCase in JSON (matches TS types)."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ApiResponse(CamelModel):
    success: bool
    message: Optional[str] = None
    data: Any = None


class PaginatedResponse(CamelModel):
    data: list[Any]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    admin = "admin"
    recruiter = "recruiter"
    hiring_manager = "hiring_manager"

class CandidateStatus(str, Enum):
    new = "new"
    under_review = "under_review"
    shortlisted = "shortlisted"
    assessment_sent = "assessment_sent"
    assessment_complete = "assessment_complete"
    interviewing = "interviewing"
    offered = "offered"
    rejected = "rejected"
    hired = "hired"

class UploadStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    parsed = "parsed"
    scored = "scored"
    failed = "failed"

class BatchStatus(str, Enum):
    uploading = "uploading"
    processing = "processing"
    complete = "complete"
    partial_failure = "partial_failure"

class JobStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    closed = "closed"

class JobType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"

class AssessmentType(str, Enum):
    technical = "technical"
    behavioral = "behavioral"
    cognitive = "cognitive"
    coding = "coding"

class AssessmentStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"

class AssignmentStatus(str, Enum):
    sent = "sent"
    opened = "opened"
    in_progress = "in_progress"
    submitted = "submitted"
    expired = "expired"

class Recommendation(str, Enum):
    strong_hire = "strong_hire"
    hire = "hire"
    maybe = "maybe"
    no_hire = "no_hire"


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserOut(CamelModel):
    id: str
    name: str
    email: str
    role: UserRole
    organization: str
    avatar: Optional[str] = None
    created_at: datetime = Field(alias="createdAt")


class AuthResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterRequest(CamelModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    organization: str = Field(min_length=2, max_length=200)


class ForgotPasswordRequest(CamelModel):
    email: EmailStr


# ── Resume / Parsed Data ──────────────────────────────────────────────────────

class WorkExperience(CamelModel):
    company: str
    title: str
    start_date: str = Field(alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    current: bool = False
    description: Optional[str] = None
    skills: list[str] = []


class Education(CamelModel):
    institution: str
    degree: str
    field: str
    start_year: Optional[int] = Field(None, alias="startYear")
    end_year: Optional[int] = Field(None, alias="endYear")
    gpa: Optional[float] = None


class ParsedResume(CamelModel):
    raw_text: str = Field(alias="rawText")
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    skills: list[str] = []
    experience: list[WorkExperience] = []
    education: list[Education] = []
    certifications: list[str] = []
    languages: list[str] = []
    total_experience_years: Optional[float] = Field(None, alias="totalExperienceYears")


# ── Candidate Score ───────────────────────────────────────────────────────────

class ScoreBreakdown(CamelModel):
    skills: float
    experience: float
    education: float
    role_alignment: float = Field(alias="roleAlignment")
    communication: float


class CandidateScore(CamelModel):
    overall: float
    breakdown: ScoreBreakdown
    predicted_role: str = Field(alias="predictedRole")
    confidence: float
    skill_match: float = Field(alias="skillMatch")
    experience_match: float = Field(alias="experienceMatch")
    ai_explanation: str = Field(alias="aiExplanation")
    strengths: list[str] = []
    concerns: list[str] = []
    recommendation: Recommendation


# ── Recruiter Notes ───────────────────────────────────────────────────────────

class RecruiterNoteOut(CamelModel):
    id: str
    author_id: str = Field(alias="authorId")
    author_name: str = Field(alias="authorName")
    content: str
    created_at: datetime = Field(alias="createdAt")


class AddNoteRequest(CamelModel):
    content: str = Field(min_length=1, max_length=5000)


# ── Candidates ────────────────────────────────────────────────────────────────

class CandidateOut(CamelModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    status: CandidateStatus
    applied_job_id: Optional[str] = Field(None, alias="appliedJobId")
    applied_job_title: Optional[str] = Field(None, alias="appliedJobTitle")
    resume_upload_id: str = Field(alias="resumeUploadId")
    parsed_resume: dict = Field(alias="parsedResume")
    score: Optional[dict] = None
    recruiter_notes: list[RecruiterNoteOut] = Field([], alias="recruiterNotes")
    tags: list[str] = []
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    avatar_url: Optional[str] = Field(None, alias="avatarUrl")


class UpdateStatusRequest(CamelModel):
    status: CandidateStatus


class BulkStatusRequest(CamelModel):
    ids: list[str] = Field(min_length=1)
    status: CandidateStatus


# ── Uploads ───────────────────────────────────────────────────────────────────

class ResumeUploadOut(CamelModel):
    id: str
    filename: str
    file_size: int = Field(alias="fileSize")
    mime_type: str = Field(alias="mimeType")
    status: UploadStatus
    candidate_id: Optional[str] = Field(None, alias="candidateId")
    job_id: Optional[str] = Field(None, alias="jobId")
    uploaded_at: datetime = Field(alias="uploadedAt")
    processed_at: Optional[datetime] = Field(None, alias="processedAt")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    parsed_data: Optional[dict] = Field(None, alias="parsedData")


class UploadBatchOut(CamelModel):
    id: str
    uploaded_at: datetime = Field(alias="uploadedAt")
    total_files: int = Field(alias="totalFiles")
    processed_files: int = Field(alias="processedFiles")
    failed_files: int = Field(alias="failedFiles")
    job_id: Optional[str] = Field(None, alias="jobId")
    job_title: Optional[str] = Field(None, alias="jobTitle")
    uploads: list[ResumeUploadOut] = []
    status: BatchStatus


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobOpeningOut(CamelModel):
    id: str
    title: str
    department: str
    location: str
    type: JobType = Field(alias="type")
    status: JobStatus
    description: str
    required_skills: list[str] = Field(alias="requiredSkills")
    preferred_skills: list[str] = Field(alias="preferredSkills")
    min_experience_years: int = Field(alias="minExperienceYears")
    max_experience_years: Optional[int] = Field(None, alias="maxExperienceYears")
    salary_min: Optional[int] = Field(None, alias="salaryMin")
    salary_max: Optional[int] = Field(None, alias="salaryMax")
    currency: Optional[str] = None
    candidate_count: int = Field(alias="candidateCount")
    shortlisted_count: int = Field(alias="shortlistedCount")
    created_at: datetime = Field(alias="createdAt")
    closing_date: Optional[datetime] = Field(None, alias="closingDate")
    hiring_manager_id: Optional[str] = Field(None, alias="hiringManagerId")


class CreateJobRequest(CamelModel):
    title: str
    department: str
    location: str
    type: JobType = Field(JobType.full_time, alias="type")
    status: JobStatus = JobStatus.draft
    description: str = ""
    required_skills: list[str] = Field([], alias="requiredSkills")
    preferred_skills: list[str] = Field([], alias="preferredSkills")
    min_experience_years: int = Field(0, alias="minExperienceYears")
    max_experience_years: Optional[int] = Field(None, alias="maxExperienceYears")
    salary_min: Optional[int] = Field(None, alias="salaryMin")
    salary_max: Optional[int] = Field(None, alias="salaryMax")
    currency: Optional[str] = None
    closing_date: Optional[datetime] = Field(None, alias="closingDate")
    hiring_manager_id: Optional[str] = Field(None, alias="hiringManagerId")


# ── Assessments ───────────────────────────────────────────────────────────────

class AssessmentOut(CamelModel):
    id: str
    title: str
    type: AssessmentType
    description: str
    duration_minutes: int = Field(alias="durationMinutes")
    total_questions: int = Field(alias="totalQuestions")
    max_score: int = Field(alias="maxScore")
    status: AssessmentStatus
    created_at: datetime = Field(alias="createdAt")
    assigned_count: int = Field(alias="assignedCount")
    completed_count: int = Field(alias="completedCount")


class CreateAssessmentRequest(CamelModel):
    title: str
    type: AssessmentType
    description: str = ""
    duration_minutes: int = Field(30, alias="durationMinutes")
    total_questions: int = Field(10, alias="totalQuestions")
    max_score: int = Field(100, alias="maxScore")
    status: AssessmentStatus = AssessmentStatus.draft


class AssignRequest(CamelModel):
    assessment_id: str
    candidate_ids: list[str] = Field(min_length=1)


class AssessmentAssignmentOut(CamelModel):
    id: str
    assessment_id: str = Field(alias="assessmentId")
    assessment_title: str = Field(alias="assessmentTitle")
    candidate_id: str = Field(alias="candidateId")
    candidate_name: str = Field(alias="candidateName")
    candidate_email: str = Field(alias="candidateEmail")
    status: AssignmentStatus
    sent_at: datetime = Field(alias="sentAt")
    expires_at: datetime = Field(alias="expiresAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    submitted_at: Optional[datetime] = Field(None, alias="submittedAt")
    result: Optional[dict] = None


# ── Analytics ─────────────────────────────────────────────────────────────────

class WeeklyChange(CamelModel):
    candidates: int
    processed: int
    shortlisted: int


class DashboardMetrics(CamelModel):
    total_candidates: int = Field(alias="totalCandidates")
    resumes_processed: int = Field(alias="resumesProcessed")
    shortlisted: int
    pending_review: int = Field(alias="pendingReview")
    average_score: float = Field(alias="averageScore")
    processing_queue: int = Field(alias="processingQueue")
    today_uploads: int = Field(alias="todayUploads")
    weekly_change: WeeklyChange = Field(alias="weeklyChange")


class UploadTrend(CamelModel):
    date: str
    uploads: int
    processed: int
    failed: int


class ScoreDistribution(CamelModel):
    range: str
    count: int


class SkillFrequency(CamelModel):
    skill: str
    count: int
    percentage: float


class ConversionFunnel(CamelModel):
    stage: str
    count: int
