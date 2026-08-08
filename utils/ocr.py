"""
utils/ocr.py

OCR utility using PaddleOCR.
PaddleOCR instance is cached at module level to avoid reload on every call.
"""

from __future__ import annotations

from PIL import Image

_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        # use_angle_cls=True handles rotated text
        # lang='en' for English; change as needed
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _ocr_instance


def run_ocr(pil_image: Image.Image) -> tuple[str, float]:
    """
    Run OCR on a PIL Image.

    Returns:
        (extracted_text, avg_confidence)
        extracted_text is an empty string if nothing is detected.
        avg_confidence is 0.0 if no text is detected.
    """
    import numpy as np

    ocr = _get_ocr()
    img_array = np.array(pil_image.convert("RGB"))
    result = ocr.ocr(img_array, cls=True)

    if not result or not result[0]:
        return "", 0.0

    lines: list[str] = []
    confidences: list[float] = []

    for line in result[0]:
        # line format: [[box_points], (text, confidence)]
        if line and len(line) >= 2:
            text_info = line[1]
            if text_info and len(text_info) >= 2:
                text = str(text_info[0]).strip()
                conf = float(text_info[1])
                if text:
                    lines.append(text)
                    confidences.append(conf)

    if not lines:
        return "", 0.0

    full_text = " ".join(lines)
    avg_confidence = sum(confidences) / len(confidences)
    return full_text, avg_confidence
