from pydantic import BaseModel, Field, field_validator


class ResumeRequest(BaseModel):
    """Request body for the text-based screening endpoint."""

    text: str = Field(
        ...,
        min_length=20,
        max_length=10_000,
        description="Raw resume text to screen.",
        examples=["Experienced ML engineer with 5 years in Python, TensorFlow and AWS..."],
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Resume text cannot be blank.")
        return v.strip()


class ResumeResponse(BaseModel):
    """Prediction result returned by the screening endpoint."""

    predicted_role: str = Field(
        ...,
        description="Most suitable job role predicted by the ensemble model.",
        examples=["Machine Learning Engineer"],
    )
    confidence: str = Field(
        ...,
        description="Ensemble confidence expressed as a percentage.",
        examples=["94%"],
    )
    top_matches: list[str] = Field(
        ...,
        description="Top-3 predicted roles ranked by probability.",
        examples=[["Machine Learning Engineer", "Data Scientist", "Backend Engineer"]],
    )
    extracted_skills: list[str] = Field(
        default_factory=list,
        description="Skills identified in the resume text.",
    )
    match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Skill coverage score between 0.0 and 1.0.",
    )
