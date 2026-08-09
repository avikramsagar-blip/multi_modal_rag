"""
app.py — Multimodal RAG Streamlit application entry point.

Flow 1 (ingestion) is wired here.
Flow 2 (chat/retrieval) will be added in a later phase.
"""
from dotenv import load_dotenv
load_dotenv()
import streamlit as st

from core.logging_config import configure_logging, get_logger
from core.preflight import run_preflight_checks
from core.state import init_session_state
from embeddings.text_embedder import get_text_embedder
from embeddings.image_embedder import get_image_embedder
from vectorstore.chroma_client import get_chroma_client
from storage.sqlite_chat import init_db
from ui.upload import render_upload_ui
from ui.chat import render_chat_ui

logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    st.set_page_config(
        page_title="Multimodal RAG",
        page_icon="🧠",
        layout="wide",
    )
    st.title("🧠 Multimodal RAG")
    logger.info("Application startup")

    preflight_warnings = run_preflight_checks()
    for warning in preflight_warnings:
        st.sidebar.warning(warning)
        logger.warning(warning)

    # Initialize SQLite chat DB on every startup (idempotent)
    init_db()

    # Initialise session state keys on first run
    init_session_state()

    # Load embedding models once per session (cached in st.session_state)
    if st.session_state.get("text_embedder") is None:
        with st.spinner("Loading text embedding model…"):
            st.session_state["text_embedder"] = get_text_embedder()
            logger.info("Text embedder initialized")

    if st.session_state.get("image_embedder") is None:
        with st.spinner("Loading image embedding model…"):
            st.session_state["image_embedder"] = get_image_embedder()
            logger.info("Image embedder initialized")

    # Initialise Chroma client and collections once per session
    if st.session_state.get("chroma_client") is None:
        try:
            with st.spinner("Connecting to Chroma Cloud…"):
                st.session_state["chroma_client"] = get_chroma_client()
                collections = st.session_state["chroma_client"].list_collection_names()
                logger.info("Chroma initialized with collections: %s", ", ".join(collections))
        except Exception:
            logger.exception("Failed to initialize Chroma Cloud client")
            st.error("Failed to initialize Chroma Cloud. Check API key, tenant, and database values.")
            return

    chroma = st.session_state.get("chroma_client")
    if chroma is not None:
        collections = chroma.list_collection_names()
        st.sidebar.caption("Chroma collections")
        st.sidebar.write("\n".join(f"- {name}" for name in collections))

    # Flow 1 + Flow 2 — tabbed UI
    tab_upload, tab_chat = st.tabs(["📂 Upload", "💬 Chat"])
    with tab_upload:
        render_upload_ui()
    with tab_chat:
        render_chat_ui()


if __name__ == "__main__":
    main()
