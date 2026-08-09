"""
core/state.py

Streamlit session state initialisation.
Call init_session_state() once at app startup.
"""

from __future__ import annotations

import streamlit as st


def init_session_state() -> None:
    """Initialise all required session_state keys if not already set."""
    defaults: dict = {
        # Embedding models (loaded once)
        "text_embedder": None,
        "image_embedder": None,
        # Chroma client (initialised once)
        "chroma_client": None,
        # Set of file hashes already ingested this session (duplicate guard)
        "ingested_hashes": set(),
        # Map of filename -> ingestion_status for UI display
        "ingestion_status": {},
        # Enforce one ingestion job at a time per session
        "is_ingestion_running": False,
        # Active session identifier
        "session_id": _generate_session_id(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_new_session() -> str:
    """
    Rotate to a brand-new logical session for document isolation.

    Keeps shared heavy objects (models, chroma client) but resets
    per-session upload tracking state.
    """
    new_session_id = _generate_session_id()
    st.session_state["session_id"] = new_session_id
    st.session_state["ingested_hashes"] = set()
    st.session_state["ingestion_status"] = {}
    st.session_state["is_ingestion_running"] = False
    return new_session_id


def _generate_session_id() -> str:
    import uuid
    return str(uuid.uuid4())
