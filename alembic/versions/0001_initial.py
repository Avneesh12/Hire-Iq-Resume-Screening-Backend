"""Initial schema — all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="recruiter"),
        sa.Column("organization", sa.String(200), nullable=False),
        sa.Column("avatar", sa.String(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── job_openings ──────────────────────────────────────────────────────────
    op.create_table(
        "job_openings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("job_type", sa.String(30), nullable=False, server_default="full_time"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("required_skills", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("preferred_skills", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("min_experience_years", sa.Integer(), server_default="0"),
        sa.Column("max_experience_years", sa.Integer()),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_max", sa.Integer()),
        sa.Column("currency", sa.String(10)),
        sa.Column("closing_date", sa.DateTime(timezone=True)),
        sa.Column("hiring_manager_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_job_openings_title", "job_openings", ["title"])
    op.create_index("ix_job_openings_status", "job_openings", ["status"])
    op.create_index("ix_job_openings_created_at", "job_openings", ["created_at"])

    # ── upload_batches ────────────────────────────────────────────────────────
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("job_openings.id", ondelete="SET NULL")),
        sa.Column("total_files", sa.Integer(), server_default="0"),
        sa.Column("processed_files", sa.Integer(), server_default="0"),
        sa.Column("failed_files", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="uploading"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_upload_batches_uploaded_by", "upload_batches", ["uploaded_by"])
    op.create_index("ix_upload_batches_status", "upload_batches", ["status"])
    op.create_index("ix_upload_batches_uploaded_at", "upload_batches", ["uploaded_at"])

    # ── candidates (created before resume_uploads — FK points both ways) ──────
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(50)),
        sa.Column("location", sa.String(200)),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("applied_job_id", sa.String(36), sa.ForeignKey("job_openings.id", ondelete="SET NULL")),
        sa.Column("resume_upload_id", sa.String(36), nullable=False),   # FK added after resume_uploads
        sa.Column("parsed_resume", postgresql.JSONB(), server_default="{}"),
        sa.Column("score", postgresql.JSONB()),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_candidates_name", "candidates", ["name"])
    op.create_index("ix_candidates_email", "candidates", ["email"])
    op.create_index("ix_candidates_status", "candidates", ["status"])
    op.create_index("ix_candidates_applied_job_id", "candidates", ["applied_job_id"])
    op.create_index("ix_candidates_created_at", "candidates", ["created_at"])
    # GIN index for fast JSONB skill queries
    op.execute("CREATE INDEX ix_candidates_score_gin ON candidates USING GIN (score)")
    op.execute("CREATE INDEX ix_candidates_parsed_resume_gin ON candidates USING GIN (parsed_resume)")

    # ── resume_uploads ────────────────────────────────────────────────────────
    op.create_table(
        "resume_uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), server_default="0"),
        sa.Column("mime_type", sa.String(100), server_default="application/octet-stream"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id", ondelete="SET NULL")),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("job_openings.id", ondelete="SET NULL")),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("parsed_data", postgresql.JSONB()),
    )
    op.create_index("ix_resume_uploads_batch_id", "resume_uploads", ["batch_id"])
    op.create_index("ix_resume_uploads_status", "resume_uploads", ["status"])

    # Now add the FK from candidates.resume_upload_id → resume_uploads.id
    op.create_foreign_key(
        "fk_candidates_resume_upload_id",
        "candidates", "resume_uploads",
        ["resume_upload_id"], ["id"],
        ondelete="RESTRICT",
    )

    # ── recruiter_notes ───────────────────────────────────────────────────────
    op.create_table(
        "recruiter_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_recruiter_notes_candidate_id", "recruiter_notes", ["candidate_id"])

    # ── assessments ───────────────────────────────────────────────────────────
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("assessment_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("duration_minutes", sa.Integer(), server_default="30"),
        sa.Column("total_questions", sa.Integer(), server_default="10"),
        sa.Column("max_score", sa.Integer(), server_default="100"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assessments_status", "assessments", ["status"])

    # ── assessment_assignments ────────────────────────────────────────────────
    op.create_table(
        "assessment_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="sent"),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("result", postgresql.JSONB()),
        sa.UniqueConstraint("assessment_id", "candidate_id", name="uq_assessment_candidate"),
    )
    op.create_index("ix_assessment_assignments_assessment_id", "assessment_assignments", ["assessment_id"])
    op.create_index("ix_assessment_assignments_candidate_id", "assessment_assignments", ["candidate_id"])
    op.create_index("ix_assessment_assignments_status", "assessment_assignments", ["status"])


def downgrade() -> None:
    op.drop_table("assessment_assignments")
    op.drop_table("assessments")
    op.drop_table("recruiter_notes")
    op.drop_constraint("fk_candidates_resume_upload_id", "candidates", type_="foreignkey")
    op.drop_table("resume_uploads")
    op.drop_table("candidates")
    op.drop_table("upload_batches")
    op.drop_table("job_openings")
    op.drop_table("users")
