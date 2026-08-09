from ingestion.validators import validate_all


def test_validate_all_rejects_empty_file() -> None:
    try:
        validate_all(b"", "empty.txt")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty file")


def test_validate_all_rejects_extension_mismatch() -> None:
    # Minimal PDF-like header bytes with wrong extension.
    pdf_like = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
    try:
        validate_all(pdf_like, "renamed.jpg")
    except ValueError as exc:
        assert "mismatch" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for extension/content mismatch")


def test_validate_all_accepts_text_fallback() -> None:
    kind = validate_all(b"hello world", "note.txt")
    assert kind == "txt"
