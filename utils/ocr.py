"""
utils/ocr.py

OCR utility using pytesseract (Tesseract backend).
Tesseract must be installed as a system binary.
Windows: winget install UB-Mannheim.TesseractOCR
Streamlit Cloud / Linux: apt package "tesseract-ocr" (see packages.txt)
"""

from __future__ import annotations

import os

import pytesseract
from PIL import Image

from core.logging_config import get_logger

logger = get_logger(__name__)

# Tesseract installs to AppData on Windows via winget; set path explicitly
_WIN_TESSERACT = r"C:\Users\saandugula\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
if os.path.isfile(_WIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = _WIN_TESSERACT


def run_ocr(pil_image: Image.Image) -> tuple[str, float]:
    """
    Run OCR on a PIL Image.

    Returns:
        (extracted_text, avg_confidence)
        extracted_text is an empty string if nothing is detected OR if OCR fails.
        avg_confidence is 0.0 if no text is detected OR if OCR fails.

    This function never raises. Any failure in the Tesseract call (binary not
    found, corrupt image, unsupported mode, etc.) is logged and treated as
    "no text found" so a single bad upload can't crash the ingestion pipeline.
    """
    try:
        data = pytesseract.image_to_data(
            pil_image.convert("RGB"),
            output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract binary not found — OCR skipped. "
            "Confirm tesseract-ocr is installed (see packages.txt on Streamlit Cloud, "
            "or the Windows install path in this module)."
        )
        return "", 0.0
    except Exception:
        logger.exception("OCR failed unexpectedly — skipping this image.")
        return "", 0.0

    texts: list[str] = []
    confidences: list[float] = []

    for i, text in enumerate(data["text"]):
        conf = int(data["conf"][i])
        # conf == -1 means layout element with no text (block/line/word boundary)
        if conf > 0 and text.strip():
            texts.append(text.strip())
            confidences.append(conf / 100.0)

    if not texts:
        return "", 0.0

    full_text = " ".join(texts)
    avg_confidence = sum(confidences) / len(confidences)
    return full_text, avg_confidence