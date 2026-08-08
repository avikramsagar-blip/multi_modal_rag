"""
ingestion/metadata.py

Builds the metadata dict attached to every Chroma record.
All fields are defined here so the schema is consistent across parsers.
"""

from __future__ import annotations

from typing import Optional


def build_metadata(
    document_id: str,
    chunk_id: str,
    source_file_name: str,
    source_type: str,
    modality: str,
    session_id: str,
    *,
    page_number: Optional[int] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    parser_used: Optional[str] = None,
    ocr_confidence: Optional[float] = None,
    ingestion_status: str = "pending",
) -> dict:
    """
    Return a flat metadata dict suitable for Chroma record storage.

    Args:
        document_id:      unique id for the source document
        chunk_id:         unique id for this chunk
        source_file_name: original uploaded filename (sanitized)
        source_type:      file extension group: txt | pdf | image | audio | video
        modality:         text | ocr | image | audio | video_transcript | video_keyframe
        session_id:       Streamlit session identifier
        page_number:      for PDF and multi-page sources
        start_time:       segment start in seconds (audio/video)
        end_time:         segment end in seconds (audio/video)
        parser_used:      which parser produced this chunk
        ocr_confidence:   average OCR confidence score (0.0–1.0)
        ingestion_status: 'pending' until all chunks written; caller sets 'complete'
    """
    meta: dict = {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "source_file_name": source_file_name,
        "source_type": source_type,
        "modality": modality,
        "session_id": session_id,
        "ingestion_status": ingestion_status,
    }

    if page_number is not None:
        meta["page_number"] = page_number
    if start_time is not None:
        meta["start_time"] = start_time
    if end_time is not None:
        meta["end_time"] = end_time
    if parser_used is not None:
        meta["parser_used"] = parser_used
    if ocr_confidence is not None:
        meta["ocr_confidence"] = round(ocr_confidence, 4)

    return meta
