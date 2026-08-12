"""
storage/sqlite_chat.py

SQLite-backed chat history persistence.
DB and tables are created on first call — no manual setup required.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger(__name__)

_DB_PATH = Path("chat_history.db")
_MAX_MESSAGES_PER_SESSION = 200


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create DB and schema on first run. Safe to call on every startup."""
    with _get_connection() as conn:

        # Chat messages table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id       TEXT PRIMARY KEY,
            conversation_id  TEXT NOT NULL,
            session_id       TEXT NOT NULL,
            role             TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            message_text     TEXT NOT NULL,
            created_at       TEXT NOT NULL,
            document_scope   TEXT,
            grok_request_id  TEXT
        )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id)"
        )

        # Human review table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            review_id        TEXT PRIMARY KEY,
            conversation_id  TEXT NOT NULL,
            session_id       TEXT NOT NULL,
            query_text       TEXT NOT NULL,
            response_text    TEXT NOT NULL,
            decision         TEXT NOT NULL,
            reviewer_note    TEXT,
            created_at       TEXT NOT NULL
        )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_session ON reviews(session_id)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_conversation ON reviews(conversation_id)"
        )

        conn.commit()

    logger.info("SQLite chat DB initialized at %s", _DB_PATH.resolve())


def save_message(
    session_id: str,
    conversation_id: str,
    role: str,
    message_text: str,
    document_scope: str | None = None,
    grok_request_id: str | None = None,
) -> str:
    """Persist one message. Returns the new message_id."""

    message_id = uuid.uuid4().hex
    created_at = datetime.utcnow().isoformat()

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages
                (
                    message_id,
                    conversation_id,
                    session_id,
                    role,
                    message_text,
                    created_at,
                    document_scope,
                    grok_request_id
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                session_id,
                role,
                message_text,
                created_at,
                document_scope,
                grok_request_id,
            ),
        )

        _enforce_session_limit(conn, session_id)

        conn.commit()

    logger.info(
        "Saved message | session_id=%s | role=%s | message_id=%s",
        session_id,
        role,
        message_id,
    )

    return message_id


def get_session_messages(session_id: str) -> list[dict]:
    """Return all messages for a session ordered by creation time."""

    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def save_review(
    session_id: str,
    conversation_id: str,
    query_text: str,
    response_text: str,
    decision: str,
    reviewer_note: str | None = None,
) -> str:
    """
    Save human review of an AI-generated response.
    """

    review_id = uuid.uuid4().hex
    created_at = datetime.utcnow().isoformat()

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reviews
            (
                review_id,
                conversation_id,
                session_id,
                query_text,
                response_text,
                decision,
                reviewer_note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                conversation_id,
                session_id,
                query_text,
                response_text,
                decision,
                reviewer_note,
                created_at,
            ),
        )

        conn.commit()

    logger.info(
        "Saved review | session_id=%s | decision=%s | review_id=%s",
        session_id,
        decision,
        review_id,
    )

    return review_id


def get_reviews(session_id: str) -> list[dict]:
    """
    Return reviews for a session.
    """

    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM reviews
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def _enforce_session_limit(
    conn: sqlite3.Connection,
    session_id: str,
) -> None:
    """Delete oldest messages if session exceeds the max count."""

    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]

    if count > _MAX_MESSAGES_PER_SESSION:

        excess = count - _MAX_MESSAGES_PER_SESSION

        conn.execute(
            """
            DELETE FROM messages
            WHERE message_id IN (
                SELECT message_id
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (session_id, excess),
        )

        logger.warning(
            "Session message limit reached; pruned %d old messages | session_id=%s",
            excess,
            session_id,
        )