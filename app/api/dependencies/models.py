from ml.loader import get_models


def models_dependency() -> dict:
    """
    FastAPI dependency that provides loaded ML models to route handlers.
    Models are loaded once at startup and reused across all requests.
    """
    return get_models()
