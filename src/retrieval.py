"""In-memory retrieval over example proposal text for GrantSmith.

This module turns the concatenated example proposals into overlapping text
chunks, embeds each chunk with OpenAI embeddings, holds the vectors in memory
with numpy, and retrieves the most relevant chunks for a question by cosine
similarity. There is no external vector database. Everything lives in memory
for the duration of a single run.

Configuration is read from environment variables, all optional:

    EMBEDDING_MODEL   OpenAI embedding model id (default text-embedding-3-small)
    RAG_TOP_K         Chunks to retrieve per question (default 5)
    CHUNK_SIZE        Target chunk size in characters (default 1000)
    CHUNK_OVERLAP     Overlap between chunks in characters (default 200)
"""

import os
import re
import sys

import numpy as np

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 5
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


class EmbeddingError(Exception):
    """Raised when embeddings cannot be produced."""


def get_embedding_model() -> str:
    value = os.getenv("EMBEDDING_MODEL", "").strip()
    return value or DEFAULT_EMBEDDING_MODEL


def get_top_k() -> int:
    return _int_env("RAG_TOP_K", DEFAULT_TOP_K)


def get_chunk_size() -> int:
    return _int_env("CHUNK_SIZE", DEFAULT_CHUNK_SIZE)


def get_chunk_overlap() -> int:
    return _int_env("CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP)


def _int_env(name: str, default: int) -> int:
    """Read a positive integer env var, falling back to default if unusable."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks of about chunk_size characters.

    Text is first broken on paragraph boundaries, then on sentence boundaries,
    then on word boundaries, so a chunk never splits in the middle of a word.
    Consecutive chunks share about overlap characters of trailing context.
    """
    text = (text or "").strip()
    if not text:
        return []

    units = _split_units(text, chunk_size)
    if not units:
        return []

    chunks: list[str] = []
    current: list[str] = []

    def current_length() -> int:
        if not current:
            return 0
        return sum(len(u) for u in current) + (len(current) - 1)

    for unit in units:
        addition = len(unit) + (1 if current else 0)
        if current and current_length() + addition > chunk_size:
            chunks.append(" ".join(current))
            current = _overlap_tail(current, overlap)
        current.append(unit)

    if current:
        chunks.append(" ".join(current))
    return chunks


def _split_units(text: str, chunk_size: int) -> list[str]:
    """Break text into units no larger than chunk_size.

    Paragraphs are kept whole when they fit. Oversized paragraphs are split on
    sentences, oversized sentences on words, and an oversized word is hard
    split on characters as a last resort.
    """
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= chunk_size:
                units.append(sentence)
                continue
            units.extend(_split_words(sentence, chunk_size))
    return units


def _split_words(sentence: str, chunk_size: int) -> list[str]:
    """Pack words into units no larger than chunk_size."""
    units: list[str] = []
    buffer = ""
    for word in sentence.split():
        if len(word) > chunk_size:
            if buffer:
                units.append(buffer)
                buffer = ""
            for start in range(0, len(word), chunk_size):
                units.append(word[start:start + chunk_size])
            continue
        candidate = f"{buffer} {word}".strip()
        if buffer and len(candidate) > chunk_size:
            units.append(buffer)
            buffer = word
        else:
            buffer = candidate
    if buffer:
        units.append(buffer)
    return units


def _overlap_tail(units: list[str], overlap: int) -> list[str]:
    """Return trailing units covering about overlap characters."""
    if overlap <= 0:
        return []
    tail: list[str] = []
    length = 0
    for unit in reversed(units):
        addition = len(unit) + (1 if tail else 0)
        if tail and length + addition > overlap:
            break
        tail.insert(0, unit)
        length += addition
    return tail


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts with OpenAI, returning a (n, dim) float array.

    Reads OPENAI_API_KEY from the environment. Raises EmbeddingError on a
    missing key or any embedding API failure.
    """
    import openai

    if not os.getenv("OPENAI_API_KEY"):
        raise EmbeddingError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = openai.OpenAI()
    try:
        response = client.embeddings.create(
            model=get_embedding_model(),
            input=list(texts),
        )
    except openai.OpenAIError as exc:
        raise EmbeddingError(f"Embedding request failed: {exc}") from exc

    vectors = [item.embedding for item in response.data]
    if not vectors:
        raise EmbeddingError("Embedding API returned no vectors.")
    return np.array(vectors, dtype=np.float32)


class EmbeddingIndex:
    """An in-memory index of text chunks and their embedding vectors."""

    def __init__(self, chunks: list[str], vectors: np.ndarray):
        self.chunks = chunks
        self.vectors = vectors

    def retrieve(self, question: str, top_k: int) -> list[str]:
        """Return the top_k chunks most similar to the question.

        The question is embedded (one embedding call) and scored against the
        stored chunk vectors by cosine similarity. Raises EmbeddingError if the
        question cannot be embedded.
        """
        if not self.chunks:
            return []
        query = embed_texts([question])[0]
        scores = _cosine_scores(query, self.vectors)
        order = np.argsort(scores)[::-1]
        limit = max(1, min(top_k, len(self.chunks)))
        return [self.chunks[i] for i in order[:limit]]


def _cosine_scores(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between one query vector and each row of a matrix."""
    query_norm = np.linalg.norm(query)
    row_norms = np.linalg.norm(matrix, axis=1)
    denom = row_norms * query_norm
    denom[denom == 0] = 1e-10
    return (matrix @ query) / denom


def try_build_index(
    text: str,
    top_k: int,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> EmbeddingIndex | None:
    """Build an index from example text, or return None to signal fallback.

    Returns None (and prints a clear warning) when there are fewer chunks than
    top_k or when embeddings cannot be produced. In both cases the caller is
    expected to fall back to the full example text.
    """
    chunks = chunk_text(
        text,
        chunk_size if chunk_size is not None else get_chunk_size(),
        overlap if overlap is not None else get_chunk_overlap(),
    )

    if len(chunks) < top_k:
        print(
            f"  Only {len(chunks)} example chunk(s) available, fewer than "
            f"top_k={top_k}. Using the full example text without retrieval.",
            file=sys.stderr,
        )
        return None

    try:
        vectors = embed_texts(chunks)
    except EmbeddingError as exc:
        print(
            f"  Could not embed example chunks ({exc}). Using the full example "
            "text without retrieval.",
            file=sys.stderr,
        )
        return None

    return EmbeddingIndex(chunks, vectors)
