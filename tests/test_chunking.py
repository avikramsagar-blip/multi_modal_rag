from ingestion.chunking import chunk_text


def test_chunk_text_empty_input() -> None:
    assert chunk_text("") == []


def test_chunk_text_returns_non_empty_chunks() -> None:
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    chunks = chunk_text(text, chunk_size=12, overlap=2, min_size=1)
    assert len(chunks) >= 1
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_merges_small_trailing_chunk() -> None:
    text = "A long sentence for chunk one. Tiny."
    chunks = chunk_text(text, chunk_size=20, overlap=0, min_size=5)
    assert len(chunks) == 1
