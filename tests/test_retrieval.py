"""Tests for in-memory retrieval.

Embedding calls are mocked the same way the LLM and network calls are mocked
elsewhere, so these tests run fully offline with no API key.
"""

import numpy as np
import pytest

from src import retrieval


def test_chunk_text_produces_overlapping_chunks():
    text = "\n\n".join(f"Paragraph {i} about youth arts programs." for i in range(20))
    chunks = retrieval.chunk_text(text, chunk_size=120, overlap=40)
    assert len(chunks) > 1
    # Every chunk stays near the target size.
    assert all(len(c) <= 160 for c in chunks)
    # Consecutive chunks share some trailing/leading text (overlap).
    first_words = set(chunks[0].split())
    second_words = set(chunks[1].split())
    assert first_words & second_words


def test_chunk_text_short_input_single_chunk():
    assert retrieval.chunk_text("Short text.", chunk_size=1000, overlap=200) == [
        "Short text."
    ]


def test_chunk_text_empty_input():
    assert retrieval.chunk_text("", chunk_size=1000, overlap=200) == []


def test_retrieve_returns_most_relevant_chunk(monkeypatch):
    chunks = [
        "youth art programs in under-resourced schools",
        "annual operating budget and financial statements",
        "board governance and bylaws",
    ]
    vectors = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    index = retrieval.EmbeddingIndex(chunks, vectors)

    # Query vector points closest to the first chunk.
    monkeypatch.setattr(
        retrieval,
        "embed_texts",
        lambda texts: np.array([[0.9, 0.1, 0.0]], dtype=np.float32),
    )

    top_one = index.retrieve("tell me about the art programs", top_k=1)
    assert top_one == ["youth art programs in under-resourced schools"]


def test_retrieve_orders_by_similarity(monkeypatch):
    chunks = ["alpha", "beta", "gamma"]
    vectors = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    index = retrieval.EmbeddingIndex(chunks, vectors)

    # Closest to gamma, then beta, then alpha.
    monkeypatch.setattr(
        retrieval,
        "embed_texts",
        lambda texts: np.array([[0.1, 0.3, 0.9]], dtype=np.float32),
    )

    assert index.retrieve("q", top_k=2) == ["gamma", "beta"]


def test_embed_texts_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(retrieval.EmbeddingError):
        retrieval.embed_texts(["anything"])


def test_try_build_index_falls_back_when_too_few_chunks(capsys):
    # A tiny input yields a single chunk, fewer than top_k, so fall back.
    index = retrieval.try_build_index("One small proposal.", top_k=5)
    assert index is None
    assert "fewer than top_k" in capsys.readouterr().err


def test_try_build_index_falls_back_on_embedding_error(monkeypatch, capsys):
    def boom(texts):
        raise retrieval.EmbeddingError("no key")

    monkeypatch.setattr(retrieval, "embed_texts", boom)
    text = "\n\n".join(f"Paragraph {i} of proposal text." for i in range(20))

    index = retrieval.try_build_index(text, top_k=3, chunk_size=80, overlap=20)
    assert index is None
    assert "Could not embed example chunks" in capsys.readouterr().err


def test_try_build_index_builds_when_enough_chunks(monkeypatch):
    def fake_embed(texts):
        # One deterministic vector per chunk, no network.
        return np.array([[float(len(t)), 1.0] for t in texts], dtype=np.float32)

    monkeypatch.setattr(retrieval, "embed_texts", fake_embed)
    text = "\n\n".join(f"Paragraph {i} of proposal text." for i in range(20))

    index = retrieval.try_build_index(text, top_k=3, chunk_size=80, overlap=20)
    assert index is not None
    assert len(index.chunks) >= 3
    assert index.vectors.shape[0] == len(index.chunks)
