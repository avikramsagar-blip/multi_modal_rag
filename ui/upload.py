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

import streamlit as st

from ingestion.router import route_file
from ingestion.validators import (
    SUPPORTED_EXTENSIONS,
    compute_hash,
    validate_all,
)
from storage.file_store import delete_staged_file, sanitize_filename, stage_file
from ui.status import show_duplicate, show_error, show_ready
from core.limits import MAX_FILES_PER_BATCH


def render_upload_ui() -> None:
    st.header("📂 Upload Documents")
    st.caption(
        f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}  •  "
        f"Max {MAX_FILES_PER_BATCH} files per batch"
    )

    uploaded_files = st.file_uploader(
        label="Choose files",
        type=SUPPORTED_EXTENSIONS,
        accept_multiple_files=True,
        key="file_uploader",
    )

    if not uploaded_files:
        return

    if st.button("▶️ Ingest files", type="primary"):
        _run_ingestion(uploaded_files)


def _run_ingestion(uploaded_files) -> None:
    session_id: str = st.session_state["session_id"]
    ingested_hashes: set = st.session_state["ingested_hashes"]
    chroma = st.session_state["chroma_client"]

    # Enforce batch limit
    files = list(uploaded_files)[: MAX_FILES_PER_BATCH]
    if len(uploaded_files) > MAX_FILES_PER_BATCH:
        st.warning(
            f"Only the first {MAX_FILES_PER_BATCH} files will be processed."
        )

    for uploaded_file in files:
        filename = sanitize_filename(uploaded_file.name)
        file_bytes = uploaded_file.read()

        # ── Validation ────────────────────────────────────────────────
        try:
            file_type = validate_all(file_bytes, filename)
        except ValueError as exc:
            show_error(filename, str(exc))
            continue

        # ── Duplicate check ───────────────────────────────────────────
        file_hash = compute_hash(file_bytes)
        if file_hash in ingested_hashes:
            show_duplicate(filename)
            continue

        # ── Stage + ingest ────────────────────────────────────────────
        staged_path = stage_file(file_bytes, filename)
        try:
            with st.spinner(f"Processing **{filename}**…"):
                chunks = route_file(file_bytes, filename, session_id, file_type)

            # Check for parser-level error marker
            if chunks and chunks[0].get("error"):
                show_error(filename, chunks[0]["message"])
                continue

            if not chunks:
                show_error(filename, "No content could be extracted from this file.")
                continue

            with st.spinner(f"Writing **{filename}** to Chroma…"):
                chroma.write_chunks(chunks)

            ingested_hashes.add(file_hash)
            st.session_state["ingestion_status"][filename] = "complete"
            show_ready(filename)

        except Exception as exc:
            show_error(filename, str(exc))
        finally:
            delete_staged_file(staged_path)
