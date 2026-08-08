"""
ingestion/validators.py

All file validation before any parsing begins.
Each function raises ValueError with a clear message on failure.
"""

from __future__ import annotations

import hashlib

import filetype

from core.limits import MAX_UPLOAD_MB

# Supported MIME types mapped to their canonical extension group
SUPPORTED_MIME_TYPES: dict[str, str] = {
    # Text
    "text/plain": "txt",
    "text/markdown": "txt",
    "text/csv": "txt",
    "application/json": "txt",
    # PDF
    "application/pdf": "pdf",
    # Images
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/tiff": "image",
    "image/gif": "image",
    # Audio
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/mp4": "audio",
    "audio/flac": "audio",
    "audio/ogg": "audio",
    # Video
    "video/mp4": "video",
    "video/x-matroska": "video",
    "video/x-msvideo": "video",
    "video/quicktime": "video",
    "video/webm": "video",
}

# Extensions we accept from the uploader widget (for Streamlit accept filter)
SUPPORTED_EXTENSIONS: list[str] = [
    "txt", "md", "csv", "json",
    "pdf",
    "jpg", "jpeg", "png", "webp", "tiff", "gif",
    "mp3", "wav", "m4a", "flac", "ogg",
    "mp4", "mkv", "avi", "mov", "webm",
]


def validate_not_empty(file_bytes: bytes) -> None:
    """Reject zero-byte files."""
    if not file_bytes:
        raise ValueError("Uploaded file is empty (0 bytes).")


def validate_size(file_bytes: bytes, max_mb: int = MAX_UPLOAD_MB) -> None:
    """Reject files exceeding the configured size limit."""
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(
            f"File size {size_mb:.1f} MB exceeds the {max_mb} MB limit."
        )


def validate_mime(file_bytes: bytes, filename: str) -> str:
    """
    Detect the true MIME type from magic bytes.
    Returns the canonical type group: 'txt', 'pdf', 'image', 'audio', 'video'.
    Raises ValueError if the type is not supported.
    """
    detected = filetype.guess(file_bytes)

    # filetype cannot detect plain text — fall back to extension
    if detected is None:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        text_extensions = {"txt", "md", "csv", "json"}
        if ext in text_extensions:
            return "txt"
        raise ValueError(
            f"Cannot determine file type for '{filename}'. "
            f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    mime = detected.mime
    if mime not in SUPPORTED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type '{mime}' for '{filename}'. "
            f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    return SUPPORTED_MIME_TYPES[mime]


def compute_hash(file_bytes: bytes) -> str:
    """Return SHA-256 hex digest of file bytes for duplicate detection."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_all(file_bytes: bytes, filename: str) -> str:
    """
    Run all validation checks in order.
    Returns the canonical type group on success.
    Raises ValueError with a user-facing message on any failure.
    """
    validate_not_empty(file_bytes)
    validate_size(file_bytes)
    return validate_mime(file_bytes, filename)
