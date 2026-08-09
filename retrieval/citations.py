"""
retrieval/citations.py

Builds citation objects from retrieved chunk metadata.
Only chunks actually sent to Grok are cited — never invented.
"""

from __future__ import annotations


def build_citations(text_results: list[dict], image_results: list[dict]) -> list[dict]:
    """
    Build a deduplicated list of citation dicts from results passed to Grok.

    Each citation contains:
        source_file_name, modality, page_number (optional),
        start_time (optional), end_time (optional), ocr_confidence (optional)
    """
    citations: list[dict] = []
    seen_chunks: set[str] = set()

    for result in text_results + image_results:
        chunk_id = result["chunk_id"]
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)

        meta = result.get("metadata", {})
        citation: dict = {
            "source_file_name": meta.get("source_file_name", "unknown"),
            "modality": meta.get("modality", ""),
        }
        if meta.get("page_number"):
            citation["page_number"] = meta["page_number"]
        if meta.get("start_time") is not None:
            citation["start_time"] = meta["start_time"]
            citation["end_time"] = meta.get("end_time")
        if meta.get("ocr_confidence") is not None:
            citation["ocr_confidence"] = meta["ocr_confidence"]

        citations.append(citation)

    return citations


def format_citations_markdown(citations: list[dict]) -> str:
    """Return a markdown-formatted citation block."""
    if not citations:
        return ""

    lines = ["**Sources:**"]
    for i, c in enumerate(citations, 1):
        parts = [f"{i}. **{c['source_file_name']}**"]
        if c.get("page_number"):
            parts.append(f"page {c['page_number']}")
        if c.get("start_time") is not None:
            end = c.get("end_time") or c["start_time"]
            parts.append(f"{c['start_time']:.1f}s – {end:.1f}s")
        if c.get("modality"):
            parts.append(f"({c['modality']})")
        if c.get("ocr_confidence") and float(c["ocr_confidence"]) < 0.5:
            parts.append("⚠️ low-confidence OCR")
        lines.append(" · ".join(parts))

    return "\n".join(lines)
