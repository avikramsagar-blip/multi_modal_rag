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
from ui.status import show_duplicate, show_error, show_ready
from core.limits import MAX_FILES_PER_BATCH

logger = get_logger(__name__)


def render_upload_ui() -> None:
    st.header("📂 Upload Documents")
    st.caption(
        f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}  •  "
        f"Max {MAX_FILES_PER_BATCH} files per batch"
    )

    current_session_id = st.session_state["session_id"]
    st.info(f"Current session: {current_session_id}")
    if st.button("Start new session", type="secondary"):
        new_id = start_new_session()
        logger.info("Started new session | old_session_id=%s | new_session_id=%s", current_session_id, new_id)
        st.success(f"New session started: {new_id}")
        st.rerun()

    uploaded_files = st.file_uploader(
        label="Choose files",
        type=SUPPORTED_EXTENSIONS,
        accept_multiple_files=True,
        key="file_uploader",
    )

    if not uploaded_files:
        return

    if st.button(
        "▶️ Ingest files",
        type="primary",
        disabled=st.session_state.get("is_ingestion_running", False),
    ):
        _run_ingestion(uploaded_files)


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
