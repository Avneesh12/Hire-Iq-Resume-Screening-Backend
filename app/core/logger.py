import logging

from app.core.config import settings


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format=settings.LOG_FORMAT,
    )
    return logging.getLogger(name)
