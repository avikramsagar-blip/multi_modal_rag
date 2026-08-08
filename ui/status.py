"""
ui/status.py

Status display helpers for the ingestion pipeline.
"""

from __future__ import annotations

import streamlit as st


def show_ready(filename: str) -> None:
    st.success(f"✅ **{filename}** — ready to chat", icon="💬")


def show_error(filename: str, message: str) -> None:
    st.error(f"❌ **{filename}** — {message}")


def show_duplicate(filename: str) -> None:
    st.warning(f"⚠️ **{filename}** was already uploaded this session. Skipped.")
