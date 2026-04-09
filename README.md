# HireIQ Backend — Fixed & Production-Ready

FastAPI + PostgreSQL + Redis resume screening API.
All routes are aligned to the frontend's `lib/api.ts` contract.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 7+

Or just use Docker Compose (recommended):

```bash
docker compose up -d db redis
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, REDIS_URL, and SECRET_KEY at minimum
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn main:app --reload --port 8000
```

API is live at `http://localhost:8000`.  
Swagger docs at `http://localhost:8000/docs`.

### 6. (Optional) Start Celery worker for background resume processing

Without Celery, resumes are processed inline (synchronous) — fine for dev.  
For production, run the worker:

```bash
celery -A app.workers.resume_processor worker --loglevel=info --concurrency=4
```

---

## Full Docker Compose (API + DB + Redis + Worker)

```bash
docker compose up --build
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://hireiq:hireiq_pass@localhost:5432/hireiq` | Async PostgreSQL URL |
| `SYNC_DATABASE_URL` | `postgresql://hireiq:hireiq_pass@localhost:5432/hireiq` | Sync URL for Alembic |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `SECRET_KEY` | *(required)* | JWT signing key — use a long random string |
| `ENV` | `development` | Set to `production` to tighten CORS + hide docs |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT expiry |
| `MAX_UPLOAD_SIZE_MB` | `10` | Per-file upload limit |
| `MAX_BATCH_FILES` | `50` | Max files per upload batch |

---

## API Routes

All routes are under `/api/v1`.

### Auth
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login → JWT token |
| `GET` | `/auth/me` | Current user |
| `PATCH` | `/auth/me` | Update name/email |
| `POST` | `/auth/change-password` | Change password |
| `POST` | `/auth/logout` | Logout |
| `POST` | `/auth/forgot-password` | Request reset link |

### Candidates
| Method | Path | Description |
|---|---|---|
| `GET` | `/candidates` | List with filters: `search`, `status`, `job_id`, `min_score`, `max_score`, `sort_by`, `sort_order`, `page`, `page_size` |
| `GET` | `/candidates/:id` | Get single candidate |
| `PATCH` | `/candidates/:id/status` | Update status |
| `POST` | `/candidates/:id/notes` | Add recruiter note |
| `GET` | `/candidates/:id/score` | Get ML score |
| `PATCH` | `/candidates/bulk-status` | Bulk status update |

### Resumes / Uploads
| Method | Path | Description |
|---|---|---|
| `POST` | `/resumes/upload` | Upload resume files (multipart: `files[]`, optional `job_id`) |
| `GET` | `/resumes/batches` | List upload batches |
| `GET` | `/resumes/batches/:id` | Get single batch |
| `POST` | `/resumes/:id/retry` | Retry failed upload |
| `DELETE` | `/resumes/:id` | Delete upload |

### Resume Screening
| Method | Path | Description |
|---|---|---|
| `POST` | `/resume/screen` | Match parsed resume against a job's skill requirements |

Request body:
```json
{
  "job_id": "uuid",
  "resume_text": "...",
  "parsed_resume": { "skills": [...], "totalExperienceYears": 3 }
}
```

Response matches `ResumeScreeningResult` type in frontend:
```json
{
  "matchScore": 0.73,
  "matchPercentage": 73.0,
  "recommendation": "match",
  "matchedSkills": ["python", "fastapi"],
  "missingSkills": ["kubernetes"],
  "experienceMatch": true,
  "strengths": ["Matches 2/3 required skills"],
  "gaps": [],
  "summary": "Candidate matches 2/3 required skills (73% match). Recommendation: Match."
}
```

### Jobs
| Method | Path | Description |
|---|---|---|
| `GET` | `/jobs` | List all jobs |
| `GET` | `/jobs/:id` | Get single job |
| `POST` | `/jobs` | Create job |
| `PATCH` | `/jobs/:id` | Update job |
| `DELETE` | `/jobs/:id` | Delete job |
| `GET` | `/jobs/:id/candidates` | Candidates for a job |

### Assessments
| Method | Path | Description |
|---|---|---|
| `GET` | `/assessments` | List assessments |
| `GET` | `/assessments/:id` | Get single assessment |
| `POST` | `/assessments` | Create assessment |
| `DELETE` | `/assessments/:id` | Delete assessment |
| `POST` | `/assessments/assign` | Assign to candidates |
| `GET` | `/assessments/assignments` | List assignments (filter by `candidate_id`, `assessment_id`) |

### Analytics
| Method | Path | Description |
|---|---|---|
| `GET` | `/analytics/metrics` | Dashboard KPIs |
| `GET` | `/analytics/upload-trends?days=30` | Daily upload trend |
| `GET` | `/analytics/score-distribution` | Score histogram |
| `GET` | `/analytics/skills?limit=20` | Top skill frequencies |
| `GET` | `/analytics/funnel` | Hiring funnel stages |

---

## What was Fixed

| Area | Issue | Fix |
|---|---|---|
| Upload URLs | `/upload/resumes`, `/uploads` | Renamed to `/resumes/upload`, `/resumes/batches` |
| Batch list URL | `/uploads` (no batches) | `/resumes/batches` |
| Retry/delete URLs | `/uploads/:id/retry` | `/resumes/:id/retry`, `/resumes/:id` |
| Query params | camelCase (`sortBy`, `jobId`, `minScore`, `pageSize`) | snake_case (`sort_by`, `job_id`, `min_score`, `page_size`) to match frontend |
| Pagination response keys | `pageSize`/`totalPages` | `page_size`/`total_pages` (frontend `adaptPaginated()` handles both) |
| `PATCH /auth/me` | Missing | Added — updates name/email |
| `POST /auth/change-password` | Missing | Added — verifies current password, hashes new one |
| `DELETE /assessments/:id` | Missing | Added |
| `/resume/screen` response shape | Wrong shape (`predicted_role`, `confidence`, ...) | Returns `ResumeScreeningResult` shape (`matchScore`, `matchPercentage`, `matchedSkills`, etc.) |
| Resume screening logic | No job context | Now loads job's `required_skills`/`preferred_skills`/`min_experience_years` from DB for real matching |
| `assessmentResults` in candidate | Missing from serializer | Added as `[]` (populated via assessment assignments) |
| `argon2-cffi` missing | `security.py` uses argon2 but it wasn't in `requirements.txt` | Added |
| `psycopg2-binary` missing | Needed by Alembic sync driver | Added |
