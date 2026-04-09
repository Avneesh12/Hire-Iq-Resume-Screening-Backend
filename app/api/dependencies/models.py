from ml.loader import get_models


def models_dependency() -> dict:
    """FastAPI dependency — provides loaded ML models to route handlers."""
    return get_models()
