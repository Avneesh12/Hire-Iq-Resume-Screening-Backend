"""
Seed script — creates an admin user and sample jobs.
Run once after migrations:
    python scripts/seed.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.security import hash_password
from app.db.models import Assessment, JobOpening, User
from app.db.session import AsyncSessionLocal


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Admin user ────────────────────────────────────────────────────────
        from sqlalchemy import select
        existing = await db.scalar(select(User).where(User.email == "admin@hireiq.dev"))
        if not existing:
            admin = User(
                name="Admin User",
                email="admin@hireiq.dev",
                hashed_password=hash_password("admin1234"),
                role="admin",
                organization="HireIQ",
            )
            db.add(admin)
            await db.flush()
            print(f"Created admin: admin@hireiq.dev / admin1234 (id={admin.id})")
        else:
            print("Admin already exists, skipping.")
            admin = existing

        # ── Sample jobs ───────────────────────────────────────────────────────
        jobs_data = [
            {
                "title": "Senior Backend Engineer",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "full_time",
                "status": "active",
                "description": "Build and scale our core API services.",
                "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "preferred_skills": ["Redis", "Kubernetes", "AWS"],
                "min_experience_years": 4,
            },
            {
                "title": "ML Engineer",
                "department": "Data Science",
                "location": "Hybrid — Bengaluru",
                "job_type": "full_time",
                "status": "active",
                "description": "Design and deploy NLP models for resume intelligence.",
                "required_skills": ["Python", "PyTorch", "scikit-learn", "NLP"],
                "preferred_skills": ["TensorFlow", "MLOps", "AWS SageMaker"],
                "min_experience_years": 3,
            },
            {
                "title": "Frontend Engineer",
                "department": "Engineering",
                "location": "Remote",
                "job_type": "full_time",
                "status": "active",
                "description": "Own the HireIQ dashboard experience.",
                "required_skills": ["TypeScript", "React", "Next.js"],
                "preferred_skills": ["Tailwind CSS", "Framer Motion"],
                "min_experience_years": 2,
            },
        ]

        for jd in jobs_data:
            job = JobOpening(**jd, hiring_manager_id=admin.id)
            db.add(job)

        # ── Sample assessments ────────────────────────────────────────────────
        assessments_data = [
            {
                "title": "Python Backend Assessment",
                "assessment_type": "technical",
                "description": "Core Python, SQL, and system design questions.",
                "duration_minutes": 60,
                "total_questions": 20,
                "max_score": 100,
                "status": "active",
            },
            {
                "title": "Behavioural Interview",
                "assessment_type": "behavioral",
                "description": "STAR-method behavioural scenarios.",
                "duration_minutes": 45,
                "total_questions": 10,
                "max_score": 100,
                "status": "active",
            },
        ]
        for ad in assessments_data:
            db.add(Assessment(**ad))

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
