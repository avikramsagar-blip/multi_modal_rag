"""
core/preflight.py

Runtime checks for required local dependencies.
"""

from __future__ import annotations

import importlib.util
import os
import shutil

_WIN_TESSERACT = r"C:\Users\saandugula\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"


def run_preflight_checks() -> list[str]:
    """Return warnings for non-fatal startup issues."""
    warnings: list[str] = []

    if shutil.which("ffmpeg") is None:
        warnings.append("FFmpeg binary not found on PATH. Video/audio extraction may fail.")

    if shutil.which("ffprobe") is None:
        warnings.append("ffprobe binary not found on PATH. Video duration checks may fail.")

    if shutil.which("tesseract") is None and not os.path.isfile(_WIN_TESSERACT):
        warnings.append("Tesseract binary not found on PATH. OCR will fail. Install via: winget install UB-Mannheim.TesseractOCR")

    required_modules = [
        "chromadb",
        "sentence_transformers",
        "open_clip",
        "pytesseract",
        "faster_whisper",
    ]
    for module_name in required_modules:
        if importlib.util.find_spec(module_name) is None:
            warnings.append(f"Python package '{module_name}' is not installed.")

    return warnings
