from app.api.routes.auth import router as auth_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.resume import router as resume_router

__all__ = [
    "auth_router",
    "candidates_router",
    "uploads_router",
    "jobs_router",
    "assessments_router",
    "analytics_router",
    "resume_router",
]
