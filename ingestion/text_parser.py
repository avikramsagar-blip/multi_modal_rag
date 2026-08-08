"""
ingestion/text_parser.py

Parses plain text files: txt, md, csv, json.
Produces chunk dicts for the text_chunks Chroma collection.
"""

from __future__ import annotations

import uuid

import streamlit as st

from ingestion.chunking import chunk_text
from ingestion.metadata import build_metadata


def parse_text_file(
    file_bytes: bytes,
    filename: str,
    session_id: str,
    document_id: str,
) -> list[dict]:
    """
    Parse a plain text file and return a list of chunk dicts.

    Each dict contains:
        chunk_id   str
        embedding  list[float]   — populated by embedder
        text       str
        metadata   dict
    """
    # Decode — try UTF-8, fall back to latin-1
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    text = text.strip()
    if not text:
        return []

    chunks = chunk_text(text)
    if not chunks:
        return []

    # Retrieve embedder from session state
    embedder = st.session_state["text_embedder"]
    embeddings = embedder.embed(chunks)

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    source_type = "txt"  # all text-family files go to text_chunks

    results: list[dict] = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{document_id}_text_{i}"
        meta = build_metadata(
            document_id=document_id,
            chunk_id=chunk_id,
            source_file_name=filename,
            source_type=ext,
            modality="text",
            session_id=session_id,
            parser_used="text_parser",
        )
        results.append(
            {
                "chunk_id": chunk_id,
                "embedding": embedding,
                "text": chunk,
                "metadata": meta,
            }
        )

    return results
