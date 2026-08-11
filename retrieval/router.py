"""
retrieval/router.py

Deterministic keyword-based query router.
Inspects the query for modality signal keywords and returns
the Chroma collections to search plus the embedding families required.
"""

from __future__ import annotations

from core.logging_config import get_logger

logger = get_logger(__name__)

# Maps signal name → (trigger keywords, collections to add)
_SIGNAL_RULES: list[tuple[str, list[str], list[str]]] = [
    (
        "ocr",
        ["scanned", "scan", "handwritten", "ocr", "printed text", "text in image",
         "screenshot", "document", "invoice", "receipt", "form", "letter", "read"],
        ["ocr_chunks"],
    ),
    (
        "image",
        ["image", "chart", "diagram", "figure", "graph", "screenshot", "photo", "visual", "depicted"],
        ["image_chunks", "video_keyframe_chunks", "ocr_chunks"],  # screenshots/photos often contain text too
    ),
    
]

# "transcript" alone is ambiguous — triggers both audio and video families
_TRANSCRIPT_KEYWORD = "transcript"

TEXT_FAMILY = frozenset(["text_chunks", "ocr_chunks", "audio_transcript_chunks", "video_transcript_chunks"])
IMAGE_FAMILY = frozenset(["image_chunks", "video_keyframe_chunks"])


def route_query(query: str) -> tuple[list[str], bool, bool]:
    """
    Determine which Chroma collections to search for a given query.

    Returns:
        collections    list of collection names to query
        needs_text_embed  whether BGE embedding is needed
        needs_image_embed whether OpenCLIP embedding is needed
    """
    query_lower = query.lower()
    # Default to text-only retrieval; OCR chunks are searched only when OCR intent is detected.
    collections: set[str] = {"text_chunks"}
    triggered: list[str] = []

    for signal_name, keywords, extra_collections in _SIGNAL_RULES:
        if any(kw in query_lower for kw in keywords):
            collections.update(extra_collections)
            triggered.append(signal_name)

    # "transcript" alone triggers both audio and video families
    if _TRANSCRIPT_KEYWORD in query_lower and not any(s in triggered for s in ("audio", "video")):
        collections.add("audio_transcript_chunks")
        collections.add("video_transcript_chunks")
        triggered.append("transcript_ambiguous")

    col_list = sorted(collections)
    needs_text = bool(collections & TEXT_FAMILY)
    needs_image = bool(collections & IMAGE_FAMILY)

    if triggered:
        logger.info("Query routed | signals=%s | collections=%s", triggered, col_list)
    else:
        logger.info("Query routed | signals=none (default) | collections=%s", col_list)

    return col_list, needs_text, needs_image
