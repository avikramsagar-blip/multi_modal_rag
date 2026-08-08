"""
core/limits.py

Hard operational limits for MVP.
All ingestion code must import and check these before processing.
Values can be overridden via environment variables.
"""

from __future__ import annotations

import os


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


# Maximum upload file size in megabytes
MAX_UPLOAD_MB: int = _int_env("MAX_UPLOAD_MB", 50)

# Maximum number of pages to process from a single PDF
MAX_PDF_PAGES: int = _int_env("MAX_PDF_PAGES", 100)

# Maximum image dimension (width or height) in pixels before resizing
MAX_IMAGE_PX: int = _int_env("MAX_IMAGE_PX", 4096)

# Maximum audio duration in seconds
MAX_AUDIO_SEC: int = _int_env("MAX_AUDIO_SEC", 600)  # 10 minutes

# Maximum video duration in seconds
MAX_VIDEO_SEC: int = _int_env("MAX_VIDEO_SEC", 300)  # 5 minutes

# Maximum number of files accepted in a single upload batch
MAX_FILES_PER_BATCH: int = _int_env("MAX_FILES_PER_BATCH", 5)

# Minimum character count for a page to be classified as digital_text_page
PDF_TEXT_THRESHOLD: int = _int_env("PDF_TEXT_THRESHOLD", 50)

# Minimum image resolution to attempt OCR (width * height in pixels)
MIN_OCR_RESOLUTION: int = _int_env("MIN_OCR_RESOLUTION", 10_000)  # 100x100

# Chunking defaults
CHUNK_SIZE_TOKENS: int = _int_env("CHUNK_SIZE_TOKENS", 300)
CHUNK_OVERLAP_TOKENS: int = _int_env("CHUNK_OVERLAP_TOKENS", 50)
MIN_CHUNK_TOKENS: int = _int_env("MIN_CHUNK_TOKENS", 30)

# Maximum context tokens sent to Grok per query
MAX_CONTEXT_TOKENS: int = _int_env("MAX_CONTEXT_TOKENS", 6000)

# Keyframe extraction interval for video (seconds between captured frames)
KEYFRAME_INTERVAL_SEC: int = _int_env("KEYFRAME_INTERVAL_SEC", 10)

# Maximum number of keyframes extracted from one video
MAX_KEYFRAMES: int = _int_env("MAX_KEYFRAMES", 30)

# Minimum OCR confidence to retain a chunk (0.0 – 1.0)
MIN_OCR_CONFIDENCE: float = float(os.getenv("MIN_OCR_CONFIDENCE", "0.3"))

# Minimum transcript word count to retain an audio/video transcript
MIN_TRANSCRIPT_WORDS: int = _int_env("MIN_TRANSCRIPT_WORDS", 5)
