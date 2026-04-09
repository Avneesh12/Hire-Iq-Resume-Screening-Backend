from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("file_handler")


async def validate_upload(file: UploadFile) -> bytes:
    """
    Read and validate an uploaded file.
    Returns raw bytes on success.
    Raises HTTPException 400 / 413 on validation failure.
    """
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            ),
        )

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)

    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File '{filename}' is {size_mb:.1f} MB — "
                f"maximum allowed is {settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )

    logger.info("Validated upload: %s (%.2f MB)", filename, size_mb)
    return file_bytes


# Keep original name for backwards compat with resume route
async def read_upload_bytes(file: UploadFile) -> tuple[bytes, str]:
    filename = file.filename or "unknown"
    file_bytes = await validate_upload(file)
    return file_bytes, filename
