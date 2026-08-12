"""
ui/upload.py

Streamlit upload UI and Flow 1 ingestion trigger.

On file submit:
  1. Validate each file (size, MIME, empty, duplicate)
  2. Stage to temp disk location
  3. Route through ingestion router
  4. Write chunks to Chroma
  5. Show status per file
"""

from __future__ import annotations

import time

import streamlit as st

from core.logging_config import get_logger
from core.state import start_new_session
from ingestion.router import route_file
from ingestion.validators import (
    SUPPORTED_EXTENSIONS,
    compute_hash,
    validate_all,
)
from storage.file_store import delete_staged_file, sanitize_filename, stage_file
from ui.status import (
    show_duplicate,
    show_error,
    show_ready,
    render_ingestion_dashboard,
)
from core.limits import MAX_FILES_PER_BATCH

logger = get_logger(__name__)


def render_upload_ui() -> None:
    # Top header with custom styling container
    st.markdown("""
        <div style="background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 20px;">
            <h3 style="margin: 0; color: #58a6ff;">📂 Multimodal Document Ingestion</h3>
            <p style="margin: 5px 0 0 0; color: #8b949e; font-size: 14px;">
                Upload documents, text, images, audio, or video files to embed them into your active Chroma Cloud collection.
            </p>
        </div>
    """, unsafe_allow_html=True)

    current_session_id = st.session_state["session_id"]
    
    # Session Management Layout Columns
    col_sess_info, col_sess_btn = st.columns([3, 1])
    with col_sess_info:
        st.caption(f"🔒 Active Session ID: `{current_session_id}`")
    with col_sess_btn:
        if st.button("🔄 New Session", type="secondary", use_container_width=True):
            new_id = start_new_session()
            logger.info("Started new session | old_session_id=%s | new_session_id=%s", current_session_id, new_id)
            st.success(f"Started: {new_id}")
            st.rerun()

    st.markdown("---")

    # File uploader with descriptive text
    uploaded_files = st.file_uploader(
        label=f"Drag and drop files here (Max {MAX_FILES_PER_BATCH} files per batch)",
        type=SUPPORTED_EXTENSIONS,
        accept_multiple_files=True,
        key="file_uploader",
    )

    if not uploaded_files:
        # Show an empty state card to guide the user
        st.info("👆 Select or drop files above to begin the multi-modal pipeline execution.")
        return

    # Display a quick file summary queue before triggering ingestion
    st.markdown("#### 📋 Staged Queue Overview")
    for idx, f in enumerate(uploaded_files[:MAX_FILES_PER_BATCH]):
        st.markdown(f"`{idx + 1}.` **{f.name}** ({len(f.getvalue()) / 1024:.1f} KB)")

    st.markdown("")

    # Primary action button with clear styling state
    is_running = st.session_state.get("is_ingestion_running", False)
    if st.button(
        "▶️ Execute Ingestion Pipeline",
        type="primary",
        disabled=is_running,
        use_container_width=True,
    ):
        _run_ingestion(uploaded_files)

    if st.button(
        "▶️ Ingest files",
        type="primary",
        disabled=st.session_state.get("is_ingestion_running", False),
    ):
        _run_ingestion(uploaded_files)
    render_ingestion_dashboard()


def _run_ingestion(uploaded_files) -> None:
    session_id: str = st.session_state["session_id"]
    ingested_hashes: set = st.session_state["ingested_hashes"]
    chroma = st.session_state["chroma_client"]

    if st.session_state.get("is_ingestion_running", False):
        st.warning("An ingestion job is already running for this session.")
        logger.warning("Ingestion blocked because another job is running | session_id=%s", session_id)
        return

    st.session_state["is_ingestion_running"] = True
    logger.info("Ingestion started | session_id=%s | files_selected=%d", session_id, len(uploaded_files))

    # Enforce batch limit
    files = list(uploaded_files)[: MAX_FILES_PER_BATCH]
    if len(uploaded_files) > MAX_FILES_PER_BATCH:
        st.warning(
            f"Only the first {MAX_FILES_PER_BATCH} files will be processed."
        )

    try:
        for uploaded_file in files:
            file_start = time.perf_counter()
            filename = sanitize_filename(uploaded_file.name)
            file_bytes = uploaded_file.read()
            logger.info(
                "Processing upload | session_id=%s | file=%s | size_bytes=%d",
                session_id,
                filename,
                len(file_bytes),
            )

            # ── Validation ────────────────────────────────────────────────
            try:
                file_type = validate_all(file_bytes, filename)
                logger.info(
                    "Validation passed | session_id=%s | file=%s | file_type=%s",
                    session_id,
                    filename,
                    file_type,
                )
            except ValueError as exc:
                logger.warning(
                    "Validation failed | session_id=%s | file=%s | error=%s",
                    session_id,
                    filename,
                    str(exc),
                )
                show_error(filename, str(exc))
                st.session_state["ingestion_status"][filename] = "failed"
                continue

            # ── Duplicate check ───────────────────────────────────────────
            file_hash = compute_hash(file_bytes)
            if file_hash in ingested_hashes:
                logger.warning(
                    "Duplicate file skipped | session_id=%s | file=%s",
                    session_id,
                    filename,
                )
                show_duplicate(filename)
                st.session_state["ingestion_status"][filename] = "duplicate"
                continue

            # ── Stage + ingest ────────────────────────────────────────────
            staged_path = stage_file(file_bytes, filename)
            logger.info("Staged file | session_id=%s | file=%s | path=%s", session_id, filename, staged_path)
            try:
                with st.spinner(f"Processing **{filename}**…"):
                    chunks = route_file(file_bytes, filename, session_id, file_type)

                # Check for parser-level error marker
                if chunks and chunks[0].get("error"):
                    message = chunks[0]["message"]
                    logger.error(
                        "Parser failed | session_id=%s | file=%s | error=%s",
                        session_id,
                        filename,
                        message,
                    )
                    show_error(filename, message)
                    st.session_state["ingestion_status"][filename] = "failed"
                    continue

                if not chunks:
                    logger.warning(
                        "No chunks extracted | session_id=%s | file=%s",
                        session_id,
                        filename,
                    )
                    show_error(filename, "No content could be extracted from this file.")
                    st.session_state["ingestion_status"][filename] = "failed"
                    continue

                logger.info(
                    "Parsed file | session_id=%s | file=%s | chunk_count=%d",
                    session_id,
                    filename,
                    len(chunks),
                )
                with st.spinner(f"Writing **{filename}** to Chroma…"):
                    chroma.write_chunks(chunks)

                ingested_hashes.add(file_hash)
                st.session_state["ingestion_status"][filename] = "complete"
                show_ready(filename)
                elapsed = time.perf_counter() - file_start
                logger.info(
                    "Ingestion complete | session_id=%s | file=%s | seconds=%.2f",
                    session_id,
                    filename,
                    elapsed,
                )

            except Exception as exc:
                logger.exception(
                    "Ingestion failed | session_id=%s | file=%s",
                    session_id,
                    filename,
                )
                st.session_state["ingestion_status"][filename] = "failed"
                show_error(filename, str(exc))
            finally:
                delete_staged_file(staged_path)
                logger.info("Deleted staged file | session_id=%s | file=%s", session_id, filename)
    finally:
        st.session_state["is_ingestion_running"] = False
        logger.info("Ingestion ended | session_id=%s", session_id)
