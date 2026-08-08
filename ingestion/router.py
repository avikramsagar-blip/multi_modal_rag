"""
ingestion/router.py

Routes an uploaded file to the correct parser based on MIME type group.
Wraps each parser call in error handling — never crashes the app.
"""

from __future__ import annotations

import uuid
from pathlib import Path


def route_file(
    file_bytes: bytes,
    filename: str,
    session_id: str,
    file_type: str,
) -> list[dict]:
    """
    Dispatch file_bytes to the correct parser.

    Args:
        file_bytes:  raw file content
        filename:    original (sanitized) filename
        session_id:  current Streamlit session ID
        file_type:   canonical type group returned by validators.validate_all()
                     one of: 'txt', 'pdf', 'image', 'audio', 'video'

    Returns:
        List of chunk dicts ready for chroma_client.write_chunks().
        On parser error, returns a single error-marker dict (no Chroma write).
    """
    document_id = uuid.uuid4().hex

    try:
        if file_type == "txt":
            from ingestion.text_parser import parse_text_file
            return parse_text_file(file_bytes, filename, session_id, document_id)

        if file_type == "pdf":
            from ingestion.pdf_parser import parse_pdf
            return parse_pdf(file_bytes, filename, session_id, document_id)

        if file_type == "image":
            from ingestion.image_parser import parse_image
            return parse_image(file_bytes, filename, session_id, document_id)

        if file_type == "audio":
            from ingestion.audio_parser import parse_audio
            return parse_audio(file_bytes, filename, session_id, document_id)

        if file_type == "video":
            from ingestion.video_parser import parse_video
            return parse_video(file_bytes, filename, session_id, document_id)

        raise ValueError(f"Unsupported file type: '{file_type}'")

    except Exception as exc:
        # Return an error marker instead of raising — lets the UI report it cleanly
        return [{"error": True, "message": str(exc), "filename": filename}]
