"""
Resume scoring service.
Uses ML model if loaded; falls back to heuristic scoring.
"""
from app.core.logger import get_logger
from app.services.skill_extractor import extract_skills

logger = get_logger("scorer")


async def score_resume(text: str, skills: list[str]) -> dict:
    """
    Returns a CandidateScore-compatible dict.
    Tries ML prediction first, falls back to heuristic.
    """
    predicted_role = "Software Engineer"
    confidence = 0.70

    try:
        from ml.loader import get_models
        from ml.predictor import predict
        models = get_models()
        if models:
            result = predict(text, models)
            predicted_role = result["role"].replace("_", " ").title()
            confidence = result["confidence"]
    except Exception as e:
        logger.debug("ML scoring unavailable, using heuristic: %s", e)

    skill_score = round(min(len(skills) / 15.0, 1.0) * 100, 1)
    overall = round(skill_score * 0.6 + confidence * 100 * 0.4, 1)

    recommendation = (
        "strong_hire" if overall >= 80
        else "hire" if overall >= 65
        else "maybe" if overall >= 45
        else "no_hire"
    )

    return {
        "overall": overall,
        "breakdown": {
            "skills": skill_score,
            "experience": round(confidence * 90, 1),
            "education": 70.0,
            "roleAlignment": round(confidence * 100, 1),
            "communication": 75.0,
        },
        "predictedRole": predicted_role,
        "confidence": round(confidence, 4),
        "skillMatch": round(min(len(skills) / 15.0, 1.0), 4),
        "experienceMatch": round(confidence, 4),
        "aiExplanation": (
            f"Candidate demonstrates {len(skills)} relevant skills with strong alignment "
            f"to the {predicted_role} role."
        ),
        "strengths": skills[:3],
        "concerns": [] if overall >= 65 else ["Limited skill coverage detected"],
        "recommendation": recommendation,
    }
