"""
retrieval/merge.py

Merges retrieval results from multiple collections and assembles
the final context string for the Grok prompt.

Text-family and image-family results are kept as separate labeled blocks
because their cosine scores are not directly comparable.
"""

from __future__ import annotations

import tiktoken

from core.limits import MAX_CONTEXT_TOKENS
from core.logging_config import get_logger

logger = get_logger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def deduplicate(results: list[dict]) -> list[dict]:
    """Remove duplicate chunk_ids, keeping first occurrence."""
    seen: set[str] = set()
    unique: list[dict] = []
    for r in results:
        if r["chunk_id"] not in seen:
            seen.add(r["chunk_id"])
            unique.append(r)
    return unique


def merge_results(results: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split deduplicated results into text-family and image-family buckets.
    Drops any chunks with ingestion_status != complete.
    """
    results = deduplicate(results)
    results = [r for r in results if r.get("metadata", {}).get("ingestion_status") == "complete"]

    text_results = [r for r in results if r["embedding_family"] == "text"]
    image_results = [r for r in results if r["embedding_family"] == "image"]

    # Sort each family by score descending
    text_results.sort(key=lambda r: r["score"], reverse=True)
    image_results.sort(key=lambda r: r["score"], reverse=True)

    return text_results, image_results


def assemble_context(text_results: list[dict], image_results: list[dict]) -> str:
    """
    Build the context string sent to Grok.
    Text and image families are labeled as separate blocks.
    Truncates to MAX_CONTEXT_TOKENS.
    """
    sections: list[str] = []
    total_tokens = 0

    if text_results:
        sections.append("### Retrieved Text Content\n")
        total_tokens += _token_count(sections[-1])
        for r in text_results:
            meta = r.get("metadata", {})
            label = _chunk_label(meta)
            chunk_text = f"{label}\n{r['text']}\n"
            chunk_tokens = _token_count(chunk_text)
            if total_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                logger.warning("Context token limit reached; truncating text results")
                break
            sections.append(chunk_text)
            total_tokens += chunk_tokens

    if image_results:
        sections.append("\n### Retrieved Visual Content (image embeddings)\n")
        total_tokens += _token_count(sections[-1])
        for r in image_results:
            meta = r.get("metadata", {})
            label = _chunk_label(meta)
            desc = r.get("text") or "[image — no text description available]"
            chunk_text = f"{label}\n{desc}\n"
            chunk_tokens = _token_count(chunk_text)
            if total_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
                logger.warning("Context token limit reached; truncating image results")
                break
            sections.append(chunk_text)
            total_tokens += chunk_tokens

    context = "\n".join(sections).strip()
    logger.info("Context assembled | tokens=%d | text_chunks=%d | image_chunks=%d",
                total_tokens, len(text_results), len(image_results))
    return context


def _chunk_label(meta: dict) -> str:
    parts = [f"[Source: {meta.get('source_file_name', 'unknown')}"]
    if meta.get("page_number"):
        parts.append(f"page {meta['page_number']}")
    if meta.get("start_time") is not None:
        parts.append(f"{meta['start_time']:.1f}s–{meta.get('end_time', meta['start_time']):.1f}s")
    modality = meta.get("modality", "")
    if modality:
        parts.append(f"modality: {modality}")
    if meta.get("ocr_confidence") and float(meta["ocr_confidence"]) < 0.5:
        parts.append("low-confidence OCR")
    return ", ".join(parts) + "]"
