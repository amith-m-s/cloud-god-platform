from __future__ import annotations

import io
from app.services.parser_service import extract_text_from_blob

def test_parse_plain_text():
    content = "Hello, this is a plain text file."
    blob = content.encode("utf-8")
    text = extract_text_from_blob(blob, "test.txt")
    assert text == content

    # Test other encoding
    blob_latin1 = content.encode("latin-1")
    text_latin1 = extract_text_from_blob(blob_latin1, "test.txt")
    assert text_latin1 == content


def test_parse_fallback_binary():
    # If the file has no specific type or extension, fallback should still successfully parse as plain utf-8
    blob = b"some random bytes"
    text = extract_text_from_blob(blob, "unknown_file")
    assert text == "some random bytes"


def test_parse_empty():
    assert extract_text_from_blob(b"", "doc.pdf") == ""
    assert extract_text_from_blob(b"", "doc.txt") == ""
