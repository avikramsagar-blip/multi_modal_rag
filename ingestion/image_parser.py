"""
ingestion/image_parser.py

Parses uploaded image files (jpg, png, tiff, webp, gif).
Produces:
  - OCR text chunk  → ocr_chunks   (if text is detected above confidence threshold)
  - Image embedding → image_chunks (always)
Both records are linked by document_id.
"""

from __future__ import annotations

import io

import streamlit as st
from PIL import Image

from core.limits import MAX_IMAGE_PX, MIN_OCR_CONFIDENCE, MIN_OCR_RESOLUTION
from core.logging_config import get_logger
from ingestion.metadata import build_metadata
from utils.ocr import run_ocr

logger = get_logger(__name__)


def _load_and_normalize(file_bytes: bytes) -> Image.Image:
    """Open image, convert RGBA→RGB, resize if over MAX_IMAGE_PX."""
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > MAX_IMAGE_PX:
        scale = MAX_IMAGE_PX / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    return img


def parse_image(
    file_bytes: bytes,
    filename: str,
    session_id: str,
    document_id: str,
) -> list[dict]:
    """
    Parse an image file and return chunk dicts.

    For multi-frame files (e.g. TIFF), each frame is processed independently.
    """
    text_embedder = st.session_state["text_embedder"]
    image_embedder = st.session_state["image_embedder"]

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "img"
    logger.info("Parsing image | file=%s", filename)

    # Handle multi-frame images (TIFF, animated GIF)
    raw = Image.open(io.BytesIO(file_bytes))
    frames: list[Image.Image] = []
    try:
        while True:
            frame = raw.copy()
            if frame.mode != "RGB":
                frame = frame.convert("RGB")
            frames.append(frame)
            raw.seek(raw.tell() + 1)
    except EOFError:
        pass

    if not frames:
        frames = [_load_and_normalize(file_bytes)]

    results: list[dict] = []

    for frame_idx, pil_img in enumerate(frames):
        # Resize if needed
        w, h = pil_img.size
        if max(w, h) > MAX_IMAGE_PX:
            scale = MAX_IMAGE_PX / max(w, h)
            pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        frame_tag = f"_f{frame_idx}" if len(frames) > 1 else ""

        # ── OCR path ────────────────────────────────────────────────────
        pixel_count = pil_img.size[0] * pil_img.size[1]
        if pixel_count >= MIN_OCR_RESOLUTION:
            ocr_text, confidence = run_ocr(pil_img)
            if ocr_text:
                if confidence < MIN_OCR_CONFIDENCE:
                    logger.warning(
                        "Low OCR confidence retained | file=%s | frame=%d | confidence=%.3f",
                        filename,
                        frame_idx,
                        confidence,
                    )
                chunk_id = f"{document_id}{frame_tag}_ocr"
                [embedding] = text_embedder.embed([ocr_text])
                meta = build_metadata(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_file_name=filename,
                    source_type=ext,
                    modality="ocr",
                    session_id=session_id,
                    page_number=frame_idx if len(frames) > 1 else None,
                    parser_used="paddleocr",
                    ocr_confidence=confidence,
                )
                results.append(
                    {"chunk_id": chunk_id, "embedding": embedding, "text": ocr_text, "metadata": meta}
                )
        else:
            logger.warning(
                "OCR skipped due to low resolution | file=%s | frame=%d | pixels=%d",
                filename,
                frame_idx,
                pixel_count,
            )

        # ── Image embedding path ─────────────────────────────────────────
        chunk_id = f"{document_id}{frame_tag}_img"
        [img_embedding] = image_embedder.embed_images([pil_img])
        meta = build_metadata(
            document_id=document_id,
            chunk_id=chunk_id,
            source_file_name=filename,
            source_type=ext,
            modality="image",
            session_id=session_id,
            page_number=frame_idx if len(frames) > 1 else None,
            parser_used="openclip",
        )
        results.append(
            {"chunk_id": chunk_id, "embedding": img_embedding, "text": "", "metadata": meta}
        )

    logger.info("Image parsed | file=%s | chunks=%d", filename, len(results))
    return results
