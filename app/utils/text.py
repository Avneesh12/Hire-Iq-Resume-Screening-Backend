import re


def clean_text(text: str) -> str:
    """
    Normalise resume text for ML inference:
      - Lowercase
      - Strip special chars (keep alphanumeric, +, #)
      - Collapse whitespace
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\+\#]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
