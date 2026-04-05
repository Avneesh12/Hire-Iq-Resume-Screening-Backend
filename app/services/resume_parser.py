from io import BytesIO
from pathlib import Path

import fitz  # PyMuPDF

from app.core.logger import get_logger

logger = get_logger("resume_parser")


def parse_resume(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from an uploaded resume file.

    Supports:
        .pdf  — extracted via PyMuPDF (fitz)
        .txt  — decoded as UTF-8
        .docx — basic text extraction via python-docx

    Returns:
        Extracted text string.

    Raises:
        ValueError for unsupported formats.
        RuntimeError if extraction yields no content.
    """
    ext = Path(filename).suffix.lower()
    logger.info("Parsing resume: %s (ext=%s, size=%d bytes)", filename, ext, len(file_bytes))

    if ext == ".pdf":
        text = _parse_pdf(file_bytes)
    elif ext == ".txt":
        text = _parse_txt(file_bytes)
    elif ext == ".docx":
        text = _parse_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: '{ext}'")

    text = text.strip()
    if not text:
        raise RuntimeError(f"No text could be extracted from '{filename}'.")

    logger.info("Extracted %d characters from %s", len(text), filename)
    return text


# ── Private helpers ────────────────────────────────────────────────────────────

def _parse_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def _parse_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def _parse_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document  # python-docx
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is required to parse .docx files. "
            "Install it with: pip install python-docx"
        ) from exc

    doc = Document(BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs)
