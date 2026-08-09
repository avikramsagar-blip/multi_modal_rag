"""
retrieval/search.py

Session-scoped vector retrieval from Chroma Cloud.
Every query is filtered by session_id so users only see their own data.
"""

from __future__ import annotations

import streamlit as st

from core.logging_config import get_logger
from retrieval.router import IMAGE_FAMILY, TEXT_FAMILY

logger = get_logger(__name__)

_TOP_N = 5  # results per collection


def search(
    query: str,
    collections: list[str],
    session_id: str,
    needs_text_embed: bool,
    needs_image_embed: bool,
) -> list[dict]:
    """
    Query the given Chroma collections filtered by session_id.

    Returns a flat list of result dicts, each containing:
        chunk_id, text, metadata, score, collection, embedding_family
    """
    chroma = st.session_state["chroma_client"]
    text_embedder = st.session_state["text_embedder"]
    image_embedder = st.session_state["image_embedder"]

    # Build query vectors once per family
    text_vector: list[float] | None = None
    image_vector: list[float] | None = None

    if needs_text_embed:
        [text_vector] = text_embedder.embed([query])
    if needs_image_embed:
        [image_vector] = image_embedder.embed_text([query])

    results: list[dict] = []

    for col_name in collections:
        vector = image_vector if col_name in IMAGE_FAMILY else text_vector
        if vector is None:
            continue

        family = "image" if col_name in IMAGE_FAMILY else "text"

        try:
            response = chroma._get_collection(col_name).query(
                query_embeddings=[vector],
                n_results=_TOP_N,
                where={"session_id": session_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("Chroma query failed | collection=%s | session_id=%s", col_name, session_id)
            continue

        ids = response.get("ids", [[]])[0]
        docs = response.get("documents", [[]])[0]
        metas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances):
            results.append({
                "chunk_id": chunk_id,
                "text": doc,
                "metadata": meta,
                "score": 1.0 - dist,  # cosine distance → similarity
                "collection": col_name,
                "embedding_family": family,
            })

        logger.info("Collection queried | collection=%s | results=%d | session_id=%s", col_name, len(ids), session_id)

    return results
