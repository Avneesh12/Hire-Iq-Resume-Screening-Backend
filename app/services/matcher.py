"""
Simple skill-match scorer.

Given an extracted skill list and an optional required-skills list,
returns a 0.0–1.0 score representing coverage.
"""


def match_score(
    candidate_skills: list[str],
    required_skills: list[str] | None = None,
) -> float:
    """
    Compute a match score between 0.0 and 1.0.

    - If *required_skills* is provided: ratio of required skills covered.
    - Otherwise: a normalised count-based heuristic (max 20 skills = 1.0).

    Args:
        candidate_skills: Skills extracted from a resume.
        required_skills:  Skills required by the job posting (optional).

    Returns:
        Float in [0.0, 1.0].
    """
    if not candidate_skills:
        return 0.0

    if required_skills:
        if not required_skills:
            return 0.0
        matched = len(set(candidate_skills) & set(s.lower() for s in required_skills))
        return round(min(matched / len(required_skills), 1.0), 4)

    return round(min(len(candidate_skills) / 20.0, 1.0), 4)
