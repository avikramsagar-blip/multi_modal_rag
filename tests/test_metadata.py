from ingestion.metadata import build_metadata


def test_build_metadata_has_required_fields() -> None:
    meta = build_metadata(
        document_id="doc1",
        chunk_id="chunk1",
        source_file_name="sample.pdf",
        source_type="pdf",
        modality="text",
        session_id="session1",
    )

    assert meta["document_id"] == "doc1"
    assert meta["chunk_id"] == "chunk1"
    assert meta["source_file_name"] == "sample.pdf"
    assert meta["modality"] == "text"
    assert meta["ingestion_status"] == "pending"


def test_build_metadata_rounds_ocr_confidence() -> None:
    meta = build_metadata(
        document_id="doc1",
        chunk_id="chunk1",
        source_file_name="scan.pdf",
        source_type="pdf",
        modality="ocr",
        session_id="session1",
        ocr_confidence=0.987654,
    )
    assert meta["ocr_confidence"] == 0.9877
