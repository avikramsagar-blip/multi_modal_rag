"""
app.py — Multimodal RAG Streamlit application entry point.

Flow 1 (ingestion) is wired here.
Flow 2 (chat/retrieval) will be added in a later phase.
"""

import streamlit as st

from core.config import settings
from core.state import init_session_state
from embeddings.text_embedder import get_text_embedder
from embeddings.image_embedder import get_image_embedder
from vectorstore.chroma_client import get_chroma_client
from ui.upload import render_upload_ui


def main() -> None:
    st.set_page_config(
        page_title="Multimodal RAG",
        page_icon="🧠",
        layout="wide",
    )
    st.title("🧠 Multimodal RAG")

    # Initialise session state keys on first run
    init_session_state()

    # Load embedding models once per session (cached in st.session_state)
    if "text_embedder" not in st.session_state:
        with st.spinner("Loading text embedding model…"):
            st.session_state["text_embedder"] = get_text_embedder()

    if "image_embedder" not in st.session_state:
        with st.spinner("Loading image embedding model…"):
            st.session_state["image_embedder"] = get_image_embedder()

    # Initialise Chroma client and collections once per session
    if "chroma_client" not in st.session_state:
        with st.spinner("Connecting to Chroma Cloud…"):
            st.session_state["chroma_client"] = get_chroma_client()

    # Flow 1 — upload and ingestion UI
    render_upload_ui()


if __name__ == "__main__":
    main()
