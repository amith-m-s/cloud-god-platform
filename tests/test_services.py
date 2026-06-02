from __future__ import annotations

from app.services.embedding_service import EmbeddingService


def test_embedding_returns_correct_dimension():
    svc = EmbeddingService()
    result = svc.embed("hello world", dimension=128)
    assert len(result.vector) == 128
    assert all(0.0 <= v <= 1.0 for v in result.vector)


def test_embedding_deterministic():
    svc = EmbeddingService()
    a = svc.embed("same text")
    b = svc.embed("same text")
    assert a.vector == b.vector


def test_embedding_batch():
    svc = EmbeddingService()
    results = svc.embed_batch(["hello", "world"])
    assert len(results) == 2
    assert results[0].vector != results[1].vector


def test_split_text():
    from app.services.document_service import _split_text
    chunks = _split_text("word " * 500, chunk_size=100)
    assert len(chunks) > 1
    # Each chunk should be at most chunk_size
    for c in chunks:
        assert len(c) <= 100


def test_split_text_empty():
    from app.services.document_service import _split_text
    assert _split_text("") == []
    assert _split_text("   ") == []
