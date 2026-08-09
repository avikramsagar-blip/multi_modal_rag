"""
ui/chat.py

Streamlit chat UI for Flow 2.
Retrieves from Chroma, assembles context, calls Grok, shows citations.
"""

from __future__ import annotations

import uuid

import streamlit as st

from core.logging_config import get_logger
from llm.grok_client import ask_grok
from retrieval.citations import build_citations, format_citations_markdown
from retrieval.merge import assemble_context, merge_results
from retrieval.router import route_query
from retrieval.search import search
from storage.sqlite_chat import get_session_messages, save_message

logger = get_logger(__name__)


def render_chat_ui() -> None:
    st.header("💬 Chat with your documents")

    session_id: str = st.session_state["session_id"]
    ingestion_status: dict = st.session_state.get("ingestion_status", {})

    # Guard — no documents indexed yet
    completed = [f for f, s in ingestion_status.items() if s == "complete"]
    if not completed:
        st.info("Upload and ingest documents first before chatting.")
        return

    st.caption(f"Session: {session_id}  •  Documents: {', '.join(completed)}")

    # Ensure conversation_id is stable within session
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = uuid.uuid4().hex
    conversation_id: str = st.session_state["conversation_id"]

    # Container holds all messages so chat_input stays below everything
    messages_container = st.container()

    # Chat input must be declared outside the container to stay at the bottom
    user_query = st.chat_input("Ask a question about your documents…")

    with messages_container:
        # Load and display conversation history
        history = get_session_messages(session_id)
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["message_text"])

        if not user_query:
            return

        # Show user message inside the same container
        with st.chat_message("user"):
            st.markdown(user_query)
        save_message(session_id, conversation_id, "user", user_query)

        with st.chat_message("assistant"):
            with st.spinner("Searching documents…"):
                collections, needs_text, needs_image = route_query(user_query)
                logger.info("Chat query | session_id=%s | query_preview=%.60s", session_id, user_query)

                raw_results = search(user_query, collections, session_id, needs_text, needs_image)

                if not raw_results:
                    answer = "No documents have been indexed in this session yet, or no relevant content was found."
                    st.markdown(answer)
                    save_message(session_id, conversation_id, "assistant", answer)
                    return

                text_results, image_results = merge_results(raw_results)
                context = assemble_context(text_results, image_results)

            with st.spinner("Generating answer…"):
                answer, grok_request_id = ask_grok(user_query, context)

            st.markdown(answer)

            citations = build_citations(text_results, image_results)
            citation_md = format_citations_markdown(citations)
            if citation_md:
                st.markdown("---")
                st.markdown(citation_md)

            document_scope = ", ".join(completed)
            full_response = answer + ("\n\n" + citation_md if citation_md else "")
            save_message(
                session_id,
                conversation_id,
                "assistant",
                full_response,
                document_scope=document_scope,
                grok_request_id=grok_request_id,
            )

    logger.info("Chat turn complete | session_id=%s | grok_request_id=%s", session_id, grok_request_id)
