"""
In-memory data store — replace with SQLAlchemy + PostgreSQL in production.
All data is dict-based so it's easy to swap out with real DB calls.
"""
from typing import Any
from collections import defaultdict

# ── Keyed stores ──────────────────────────────────────────────────────────────
users: dict[str, dict] = {}          # keyed by user_id
users_by_email: dict[str, str] = {}  # email -> user_id

candidates: dict[str, dict] = {}
uploads: dict[str, dict] = {}        # batch_id -> UploadBatch
resume_uploads: dict[str, dict] = {} # upload_id -> ResumeUpload
jobs: dict[str, dict] = {}
assessments: dict[str, dict] = {}
assignments: dict[str, dict] = {}

# notes[candidate_id] = [note, ...]
notes: dict[str, list[dict]] = defaultdict(list)
