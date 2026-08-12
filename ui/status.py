"""
ui/status.py

Status display helpers and ingestion dashboard.
"""

from __future__ import annotations

import streamlit as st


def show_ready(filename: str) -> None:
    st.success(
        f"✅ **{filename}** — ready to chat",
        icon="💬",
    )


def show_error(filename: str, message: str) -> None:
    st.error(
        f"❌ **{filename}** — {message}"
    )


def show_duplicate(filename: str) -> None:
    st.warning(
        f"⚠️ **{filename}** was already uploaded this session. Skipped."
    )


def render_ingestion_dashboard() -> None:
    """
    Display ingestion statistics
    for the current session.
    """

    ingestion_status = st.session_state.get(
        "ingestion_status",
        {},
    )

    if not ingestion_status:
        return

    complete_count = sum(
        1
        for s in ingestion_status.values()
        if s == "complete"
    )

    failed_count = sum(
        1
        for s in ingestion_status.values()
        if s == "failed"
    )

    duplicate_count = sum(
        1
        for s in ingestion_status.values()
        if s == "duplicate"
    )

    total_count = len(ingestion_status)

    st.markdown("---")
    st.subheader("📊 Ingestion Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Files",
        total_count,
    )

    col2.metric(
        "Completed",
        complete_count,
    )

    col3.metric(
        "Failed",
        failed_count,
    )

    col4.metric(
        "Duplicates",
        duplicate_count,
    )

    st.markdown("### File Status")

    for filename, status in ingestion_status.items():

        if status == "complete":
            st.success(
                f"{filename} → COMPLETE"
            )

        elif status == "failed":
            st.error(
                f"{filename} → FAILED"
            )

        elif status == "duplicate":
            st.warning(
                f"{filename} → DUPLICATE"
            )

        else:
            st.info(
                f"{filename} → {status}"
            )