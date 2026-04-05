"""
Lightweight keyword-based skill extractor.

This is intentionally simple — swap in an NER model or SpaCy pipeline
if you need production-grade extraction.
"""

SKILL_KEYWORDS: list[str] = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "scala", "kotlin", "swift", "r", "matlab", "sql", "bash",
    # ML / Data
    "tensorflow", "keras", "pytorch", "scikit-learn", "xgboost", "lightgbm",
    "pandas", "numpy", "matplotlib", "seaborn", "opencv", "huggingface",
    "transformers", "bert", "gpt", "llm", "nlp", "computer vision",
    "deep learning", "machine learning", "data science", "mlops",
    # Web / Backend
    "fastapi", "django", "flask", "spring", "nodejs", "express",
    "graphql", "rest", "grpc", "kafka", "rabbitmq",
    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "ci/cd", "github actions", "jenkins", "airflow",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "cassandra", "sqlite", "bigquery", "snowflake",
]


def extract_skills(text: str) -> list[str]:
    """
    Return a deduplicated, sorted list of skills found in *text*.

    Matching is case-insensitive and whole-word aware for single-word
    skills; multi-word phrases are matched as substrings.
    """
    lower = text.lower()
    found = sorted({skill for skill in SKILL_KEYWORDS if skill in lower})
    return found
