"""
storage/file_store.py

Temporary file staging for uploaded files.
Files are written to a local temp directory before parsing.
The caller is responsible for deleting staged files after ingestion.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from pathlib import Path

# Staging directory — created on first use
_STAGING_DIR = Path(tempfile.gettempdir()) / "multimodal_rag_uploads"


def _ensure_staging_dir() -> Path:
    _STAGING_DIR.mkdir(parents=True, exist_ok=True)
    return _STAGING_DIR


def sanitize_filename(filename: str) -> str:
    """
    Remove path separators, null bytes, and other dangerous characters.
    Preserve the file extension.
    """
    # Keep only alphanumeric, dash, underscore, dot
    name = re.sub(r"[^\w.\-]", "_", filename)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    return name.strip("_") or "upload"


def stage_file(file_bytes: bytes, filename: str) -> Path:
    """
    Write file_bytes to a unique path in the staging directory.
    Returns the absolute Path to the staged file.
    """
    staging_dir = _ensure_staging_dir()
    safe_name = sanitize_filename(filename)
    # Prefix with a UUID so concurrent uploads never collide
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest = staging_dir / unique_name
    dest.write_bytes(file_bytes)
    return dest


def delete_staged_file(path: Path | str) -> None:
    """Remove a staged file. Silent if already gone."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def compute_hash(file_bytes: bytes) -> str:
    """Return SHA-256 hex digest — same as validators.compute_hash."""
    return hashlib.sha256(file_bytes).hexdigest()
