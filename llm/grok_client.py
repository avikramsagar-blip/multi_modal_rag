"""
llm/grok_client.py

Grok API client using the OpenAI-compatible Groq endpoint.
Wraps all API errors — never crashes the app.
"""

from __future__ import annotations

import uuid

import httpx

from core.config import settings
from core.limits import MAX_CONTEXT_TOKENS
from core.logging_config import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based strictly on the provided context. "
    "If the context does not contain enough information to answer, say so clearly. "
    "Do not invent facts or citations."
)


def ask_grok(query: str, context: str) -> tuple[str, str]:
    """
    Send context + query to the Grok API and return (answer, grok_request_id).
    On any error, returns a user-facing error message and an empty request id.
    """
    if not context.strip():
        logger.warning("ask_grok called with empty context")
        return "No relevant content was found in your uploaded documents for this question.", ""

    grok_request_id = uuid.uuid4().hex
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]

    logger.info("Sending request to Grok | model=%s | grok_request_id=%s", settings.grok_model, grok_request_id)

    try:
        response = httpx.post(
            f"{settings.grok_api_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.grok_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.grok_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        logger.info("Grok response received | grok_request_id=%s | length=%d", grok_request_id, len(answer))
        return answer, grok_request_id

    except httpx.HTTPStatusError as exc:
        logger.error("Grok API HTTP error | status=%d | grok_request_id=%s", exc.response.status_code, grok_request_id)
        return f"Grok API returned an error (HTTP {exc.response.status_code}). Please try again.", ""

    except httpx.TimeoutException:
        logger.error("Grok API request timed out | grok_request_id=%s", grok_request_id)
        return "The request to Grok timed out. Please try again.", ""

    except Exception:
        logger.exception("Unexpected Grok API error | grok_request_id=%s", grok_request_id)
        return "An unexpected error occurred while contacting Grok. Please try again.", ""
