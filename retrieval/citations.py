"""
retrieval/citations.py

Builds citation objects from retrieved chunk metadata.
Only chunks actually sent to Grok are cited.
"""

from __future__ import annotations


def build_citations(
    text_results: list[dict],
    image_results: list[dict],
) -> list[dict]:
    """
    Build a deduplicated list of citation dicts.

    Includes:
        source_file_name
        modality
        page_number
        start_time
        end_time
        ocr_confidence
        chunk_id
        similarity_score
        collection
    """

    citations: list[dict] = []
    seen_chunks: set[str] = set()

    for result in text_results + image_results:

        chunk_id = result["chunk_id"]

        if chunk_id in seen_chunks:
            continue

        seen_chunks.add(chunk_id)

        meta = result.get("metadata", {})

        citation = {
            "source_file_name": meta.get(
                "source_file_name",
                "unknown",
            ),
            "modality": meta.get("modality", ""),
            "chunk_id": chunk_id,
            "similarity_score": round(
                float(result.get("score", 0)),
                3,
            ),
            "collection": result.get("collection", ""),
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


def format_citations_markdown(
    citations: list[dict],
) -> str:
    """
    Render citations in a reviewer-friendly format.
    """

    if not citations:
        return ""

    lines = ["### Sources"]

    for i, c in enumerate(citations, start=1):

        lines.append(
            f"\n**{i}. {c['source_file_name']}**"
        )

        lines.append(
            f"- Chunk ID: `{c['chunk_id']}`"
        )

        lines.append(
            f"- Similarity Score: `{c['similarity_score']}`"
        )

        if c.get("collection"):
            lines.append(
                f"- Collection: `{c['collection']}`"
            )

        if c.get("page_number"):
            lines.append(
                f"- Page: {c['page_number']}"
            )

        if c.get("start_time") is not None:
            end_time = c.get(
                "end_time",
                c["start_time"],
            )

            lines.append(
                f"- Time Range: "
                f"{c['start_time']:.1f}s → {end_time:.1f}s"
            )

        if c.get("modality"):
            lines.append(
                f"- Modality: {c['modality']}"
            )

        if c.get("ocr_confidence") is not None:
            lines.append(
                f"- OCR Confidence: "
                f"{float(c['ocr_confidence']):.2f}"
            )

    return "\n".join(lines)