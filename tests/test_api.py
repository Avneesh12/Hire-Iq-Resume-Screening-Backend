"""
Tests for the Resume Screening API.

Run with:
    pytest tests/ -v
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_RESUME = (
    "Experienced machine learning engineer with 5 years of hands-on experience "
    "in Python, TensorFlow, scikit-learn, and AWS. Built and deployed deep learning "
    "models for NLP and computer vision tasks. Strong background in MLOps, Docker, "
    "Kubernetes, and CI/CD pipelines. MS in Computer Science."
)


def _make_mock_models() -> dict:
    """Return a fake models dict that mimics predict() output."""
    le = MagicMock()
    le.inverse_transform = lambda idxs: ["machine_learning_engineer"] * len(idxs)

    tfidf = MagicMock()
    num_classes = 5
    tfidf.predict_proba.return_value = np.array(
        [[0.1, 0.05, 0.7, 0.1, 0.05]]
    )

    return {"le": le, "tfidf": tfidf}


@pytest.fixture()
def client():
    """TestClient with mocked ML models."""
    mock_models = _make_mock_models()
    with patch("app.api.dependencies.models.get_models", return_value=mock_models):
        with TestClient(app) as c:
            yield c


# ── Health check ──────────────────────────────────────────────────────────────

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── /screen ───────────────────────────────────────────────────────────────────

def test_screen_resume_success(client):
    response = client.post("/api/v1/resume/screen", json={"text": SAMPLE_RESUME})
    assert response.status_code == 200
    data = response.json()
    assert "predicted_role" in data
    assert "confidence" in data
    assert "top_matches" in data
    assert isinstance(data["top_matches"], list)
    assert "extracted_skills" in data
    assert "match_score" in data


def test_screen_resume_empty_text(client):
    response = client.post("/api/v1/resume/screen", json={"text": "   "})
    assert response.status_code == 422


def test_screen_resume_too_short(client):
    response = client.post("/api/v1/resume/screen", json={"text": "short"})
    assert response.status_code == 422


def test_screen_resume_too_long(client):
    response = client.post("/api/v1/resume/screen", json={"text": "a" * 10_001})
    assert response.status_code == 422


# ── Skill extractor ───────────────────────────────────────────────────────────

def test_extract_skills():
    from app.services.skill_extractor import extract_skills

    text = "Proficient in Python, TensorFlow, Docker, and AWS."
    skills = extract_skills(text)
    assert "python" in skills
    assert "tensorflow" in skills
    assert "docker" in skills
    assert "aws" in skills


def test_extract_skills_empty():
    from app.services.skill_extractor import extract_skills

    assert extract_skills("") == []


# ── Matcher ───────────────────────────────────────────────────────────────────

def test_match_score_with_required():
    from app.services.matcher import match_score

    score = match_score(["python", "tensorflow"], required_skills=["python", "tensorflow", "docker"])
    assert score == pytest.approx(2 / 3, rel=1e-3)


def test_match_score_no_skills():
    from app.services.matcher import match_score

    assert match_score([]) == 0.0


# ── Text cleaner ──────────────────────────────────────────────────────────────

def test_clean_text():
    from app.utils.text import clean_text

    result = clean_text("  Hello, World! C++ & Python3  ")
    assert result == "hello world c++ python3"
    assert result == result.strip()


def test_clean_text_preserves_plus_hash():
    from app.utils.text import clean_text

    result = clean_text("C++ C# skills")
    assert "c++" in result
    assert "c#" in result
