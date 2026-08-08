"""
ingestion/pdf_parser.py

Parses PDF files with per-page classification:
  - digital_text_page   → PyMuPDF text → text_chunks
  - scanned_page        → PaddleOCR    → ocr_chunks
  - mixed_text_image_page → PyMuPDF text + embedded image blocks
  - image_only_page     → PaddleOCR + OpenCLIP → ocr_chunks + image_chunks
  - table_heavy_page    → OCR fallback → ocr_chunks
"""

from __future__ import annotations

import io
from typing import Literal

import fitz  # PyMuPDF
import streamlit as st
from PIL import Image

from core.limits import MAX_PDF_PAGES, MIN_OCR_CONFIDENCE, PDF_TEXT_THRESHOLD
from ingestion.chunking import chunk_text
from ingestion.metadata import build_metadata
from utils.ocr import run_ocr

PageType = Literal[
    "digital_text_page",
    "scanned_page",
    "mixed_text_image_page",
    "image_only_page",
    "table_heavy_page",
]


def _classify_page(page: fitz.Page) -> PageType:
    """Classify a single PDF page by its content."""
    text = page.get_text("text").strip()
    char_count = len(text)
    image_list = page.get_images(full=True)
    has_images = len(image_list) > 0

    if char_count >= PDF_TEXT_THRESHOLD and has_images:
        return "mixed_text_image_page"
    if char_count >= PDF_TEXT_THRESHOLD:
        # Check for table-like structure (many short lines with similar length)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) > 5:
            lengths = [len(l) for l in lines]
            avg = sum(lengths) / len(lengths)
            variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
            if variance < 50:  # very uniform line lengths → likely a table
                return "table_heavy_page"
        return "digital_text_page"
    if has_images and char_count < PDF_TEXT_THRESHOLD:
        return "image_only_page"
    return "scanned_page"


def _page_to_pil(page: fitz.Page, dpi: int = 150) -> Image.Image:
    """Render a PDF page to a PIL Image."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _extract_embedded_images(
    page: fitz.Page, doc: fitz.Document
) -> list[Image.Image]:
    """Extract embedded image blocks from a PDF page as PIL Images."""
    images: list[Image.Image] = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            images.append(pil_img)
        except Exception:
            continue
    return images


def parse_pdf(
    file_bytes: bytes,
    filename: str,
    session_id: str,
    document_id: str,
) -> list[dict]:
    """
    Parse a PDF and return chunk dicts for all pages.
    Respects MAX_PDF_PAGES limit.
    """
    text_embedder = st.session_state["text_embedder"]
    image_embedder = st.session_state["image_embedder"]

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    total_pages = min(len(doc), MAX_PDF_PAGES)

    results: list[dict] = []

    for page_num in range(total_pages):
        page = doc[page_num]
        page_type = _classify_page(page)

        # ── Digital text page ──────────────────────────────────────────
        if page_type == "digital_text_page":
            text = page.get_text("text").strip()
            for i, chunk in enumerate(chunk_text(text)):
                chunk_id = f"{document_id}_p{page_num}_txt_{i}"
                [embedding] = text_embedder.embed([chunk])
                meta = build_metadata(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_file_name=filename,
                    source_type="pdf",
                    modality="text",
                    session_id=session_id,
                    page_number=page_num,
                    parser_used="pymupdf",
                )
                results.append({"chunk_id": chunk_id, "embedding": embedding, "text": chunk, "metadata": meta})

        # ── Scanned page ───────────────────────────────────────────────
        elif page_type == "scanned_page":
            pil_img = _page_to_pil(page)
            ocr_text, confidence = run_ocr(pil_img)
            if ocr_text and confidence >= MIN_OCR_CONFIDENCE:
                for i, chunk in enumerate(chunk_text(ocr_text)):
                    chunk_id = f"{document_id}_p{page_num}_ocr_{i}"
                    [embedding] = text_embedder.embed([chunk])
                    meta = build_metadata(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        source_file_name=filename,
                        source_type="pdf",
                        modality="ocr",
                        session_id=session_id,
                        page_number=page_num,
                        parser_used="paddleocr",
                        ocr_confidence=confidence,
                    )
                    results.append({"chunk_id": chunk_id, "embedding": embedding, "text": chunk, "metadata": meta})

        # ── Mixed text + image page ────────────────────────────────────
        elif page_type == "mixed_text_image_page":
            # Text portion
            text = page.get_text("text").strip()
            for i, chunk in enumerate(chunk_text(text)):
                chunk_id = f"{document_id}_p{page_num}_txt_{i}"
                [embedding] = text_embedder.embed([chunk])
                meta = build_metadata(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_file_name=filename,
                    source_type="pdf",
                    modality="text",
                    session_id=session_id,
                    page_number=page_num,
                    parser_used="pymupdf",
                )
                results.append({"chunk_id": chunk_id, "embedding": embedding, "text": chunk, "metadata": meta})

            # Image blocks
            embedded_imgs = _extract_embedded_images(page, doc)
            for img_idx, pil_img in enumerate(embedded_imgs):
                # OCR on embedded image
                ocr_text, confidence = run_ocr(pil_img)
                if ocr_text and confidence >= MIN_OCR_CONFIDENCE:
                    chunk_id = f"{document_id}_p{page_num}_img{img_idx}_ocr"
                    [embedding] = text_embedder.embed([ocr_text])
                    meta = build_metadata(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        source_file_name=filename,
                        source_type="pdf",
                        modality="ocr",
                        session_id=session_id,
                        page_number=page_num,
                        parser_used="paddleocr",
                        ocr_confidence=confidence,
                    )
                    results.append({"chunk_id": chunk_id, "embedding": embedding, "text": ocr_text, "metadata": meta})

                # Image embedding
                chunk_id = f"{document_id}_p{page_num}_img{img_idx}_emb"
                [img_embedding] = image_embedder.embed_images([pil_img])
                meta = build_metadata(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_file_name=filename,
                    source_type="pdf",
                    modality="image",
                    session_id=session_id,
                    page_number=page_num,
                    parser_used="openclip",
                )
                results.append({"chunk_id": chunk_id, "embedding": img_embedding, "text": "", "metadata": meta})

        # ── Image-only page ────────────────────────────────────────────
        elif page_type == "image_only_page":
            pil_img = _page_to_pil(page)

            # OCR
            ocr_text, confidence = run_ocr(pil_img)
            if ocr_text and confidence >= MIN_OCR_CONFIDENCE:
                chunk_id = f"{document_id}_p{page_num}_ocr_0"
                [embedding] = text_embedder.embed([ocr_text])
                meta = build_metadata(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    source_file_name=filename,
                    source_type="pdf",
                    modality="ocr",
                    session_id=session_id,
                    page_number=page_num,
                    parser_used="paddleocr",
                    ocr_confidence=confidence,
                )
                results.append({"chunk_id": chunk_id, "embedding": embedding, "text": ocr_text, "metadata": meta})

            # Image embedding
            chunk_id = f"{document_id}_p{page_num}_img_emb"
            [img_embedding] = image_embedder.embed_images([pil_img])
            meta = build_metadata(
                document_id=document_id,
                chunk_id=chunk_id,
                source_file_name=filename,
                source_type="pdf",
                modality="image",
                session_id=session_id,
                page_number=page_num,
                parser_used="openclip",
            )
            results.append({"chunk_id": chunk_id, "embedding": img_embedding, "text": "", "metadata": meta})

        # ── Table-heavy page — OCR fallback ────────────────────────────
        elif page_type == "table_heavy_page":
            text = page.get_text("text").strip()
            if len(text) >= PDF_TEXT_THRESHOLD:
                # Use direct text if available
                for i, chunk in enumerate(chunk_text(text)):
                    chunk_id = f"{document_id}_p{page_num}_tbl_{i}"
                    [embedding] = text_embedder.embed([chunk])
                    meta = build_metadata(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        source_file_name=filename,
                        source_type="pdf",
                        modality="text",
                        session_id=session_id,
                        page_number=page_num,
                        parser_used="pymupdf_table",
                    )
                    results.append({"chunk_id": chunk_id, "embedding": embedding, "text": chunk, "metadata": meta})
            else:
                # Fall back to OCR
                pil_img = _page_to_pil(page)
                ocr_text, confidence = run_ocr(pil_img)
                if ocr_text and confidence >= MIN_OCR_CONFIDENCE:
                    chunk_id = f"{document_id}_p{page_num}_tbl_ocr"
                    [embedding] = text_embedder.embed([ocr_text])
                    meta = build_metadata(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        source_file_name=filename,
                        source_type="pdf",
                        modality="ocr",
                        session_id=session_id,
                        page_number=page_num,
                        parser_used="paddleocr_table",
                        ocr_confidence=confidence,
                    )
                    results.append({"chunk_id": chunk_id, "embedding": embedding, "text": ocr_text, "metadata": meta})

    doc.close()
    return results
