"""
ingestion/chunking.py

Sentence-boundary-aware text chunking with token-count enforcement.
Uses tiktoken for token counting (cl100k_base encoding — same as GPT-4).
"""

from __future__ import annotations

import re

import tiktoken

from core.limits import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS, MIN_CHUNK_TOKENS

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences on '.', '!', '?', '\n\n' boundaries.
    Returns a list of non-empty stripped sentence strings.
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split on sentence-ending punctuation followed by whitespace or newline
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
    min_size: int = MIN_CHUNK_TOKENS,
) -> list[str]:
    """
    Split text into overlapping chunks bounded by token count.

    Strategy:
    1. Split into sentences.
    2. Greedily accumulate sentences until chunk_size tokens is reached.
    3. Start next chunk from overlap sentences back (approximate token overlap).
    4. Merge any trailing chunk below min_size into the previous chunk.

    Returns:
        List of chunk strings. Empty input returns [].
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    i = 0
    while i < len(sentences):
        sent = sentences[i]
        sent_tokens = _token_count(sent)

        # Single sentence larger than chunk_size — force it as its own chunk
        if sent_tokens >= chunk_size:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
            chunks.append(sent)
            i += 1
            continue

        if current_tokens + sent_tokens > chunk_size and current:
            chunks.append(" ".join(current))
            # Rewind by overlap: drop sentences from the front until we are
            # within overlap tokens from the end
            overlap_budget = overlap
            overlap_start = len(current)
            for j in range(len(current) - 1, -1, -1):
                t = _token_count(current[j])
                if overlap_budget - t >= 0:
                    overlap_budget -= t
                    overlap_start = j
                else:
                    break
            current = current[overlap_start:]
            current_tokens = sum(_token_count(s) for s in current)

        current.append(sent)
        current_tokens += sent_tokens
        i += 1

    if current:
        chunks.append(" ".join(current))

    # Merge undersized trailing chunk into the previous one
    if len(chunks) > 1 and _token_count(chunks[-1]) < min_size:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return chunks
