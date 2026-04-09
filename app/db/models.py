"""
SQLAlchemy ORM models — one class per DB table.
All PKs are UUIDs, timestamps are timezone-aware.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="recruiter")
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    jobs: Mapped[list["JobOpening"]] = relationship("JobOpening", back_populates="hiring_manager")
    notes: Mapped[list["RecruiterNote"]] = relationship("RecruiterNote", back_populates="author")


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobOpening(Base):
    __tablename__ = "job_openings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False, default="full_time")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list] = mapped_column(ARRAY(String), default=list)
    preferred_skills: Mapped[list] = mapped_column(ARRAY(String), default=list)
    min_experience_years: Mapped[int] = mapped_column(Integer, default=0)
    max_experience_years: Mapped[int | None] = mapped_column(Integer)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(10))
    closing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hiring_manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    hiring_manager: Mapped[User | None] = relationship("User", back_populates="jobs")
    candidates: Mapped[list["Candidate"]] = relationship("Candidate", back_populates="applied_job")


# ── Upload Batches ────────────────────────────────────────────────────────────

class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job_openings.id", ondelete="SET NULL"))
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="uploading", index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    uploads: Mapped[list["ResumeUpload"]] = relationship("ResumeUpload", back_populates="batch", lazy="selectin")
    job: Mapped[JobOpening | None] = relationship("JobOpening")


# ── Resume Uploads ────────────────────────────────────────────────────────────

class ResumeUpload(Base):
    __tablename__ = "resume_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("upload_batches.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id", ondelete="SET NULL"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job_openings.id", ondelete="SET NULL"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict | None] = mapped_column(JSONB)   # ParsedResume as JSON

    batch: Mapped[UploadBatch] = relationship("UploadBatch", back_populates="uploads")
    candidate: Mapped["Candidate | None"] = relationship("Candidate", foreign_keys=[candidate_id])


# ── Candidates ────────────────────────────────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False, index=True)
    applied_job_id: Mapped[str | None] = mapped_column(ForeignKey("job_openings.id", ondelete="SET NULL"), index=True)
    resume_upload_id: Mapped[str] = mapped_column(ForeignKey("resume_uploads.id", ondelete="RESTRICT"), nullable=False)
    parsed_resume: Mapped[dict] = mapped_column(JSONB, default=dict)
    score: Mapped[dict | None] = mapped_column(JSONB)          # CandidateScore as JSON
    tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    applied_job: Mapped[JobOpening | None] = relationship("JobOpening", back_populates="candidates")
    notes: Mapped[list["RecruiterNote"]] = relationship(
        "RecruiterNote", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    assessment_results: Mapped[list["AssessmentAssignment"]] = relationship(
        "AssessmentAssignment", back_populates="candidate", lazy="selectin"
    )


# ── Recruiter Notes ───────────────────────────────────────────────────────────

class RecruiterNote(Base):
    __tablename__ = "recruiter_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="notes")
    author: Mapped[User] = relationship("User", back_populates="notes")


# ── Assessments ───────────────────────────────────────────────────────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    total_questions: Mapped[int] = mapped_column(Integer, default=10)
    max_score: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignments: Mapped[list["AssessmentAssignment"]] = relationship(
        "AssessmentAssignment", back_populates="assessment", lazy="selectin"
    )


# ── Assessment Assignments ────────────────────────────────────────────────────

class AssessmentAssignment(Base):
    __tablename__ = "assessment_assignments"
    __table_args__ = (
        UniqueConstraint("assessment_id", "candidate_id", name="uq_assessment_candidate"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="sent", index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)         # AssessmentResult as JSON

    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="assignments")
    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="assessment_results")
