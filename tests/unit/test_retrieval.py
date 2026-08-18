"""T028 — unit tests for relevance-threshold / insufficient-context
decision logic (domain/retrieval.py, FR-026, FR-027b). No DB, no
providers — operates on plain `RetrievedChunk` values.
"""

import uuid

from albercik_chatbot.domain.retrieval import (
    RetrievedChunk,
    has_sufficient_context,
    limit_context_chars,
    select_sufficient_chunks,
)


def _chunk(similarity: float, label: str = "doc.txt") -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        document_label=label,
        content=f"content at similarity {similarity}",
        similarity=similarity,
    )


def test_filters_out_chunks_below_threshold() -> None:
    chunks = [_chunk(0.9), _chunk(0.5), _chunk(0.3)]

    result = select_sufficient_chunks(chunks, relevance_threshold=0.75)

    assert result == [chunks[0]]


def test_boundary_similarity_equal_to_threshold_is_included() -> None:
    chunks = [_chunk(0.75)]

    result = select_sufficient_chunks(chunks, relevance_threshold=0.75)

    assert result == chunks


def test_empty_chunk_list_returns_empty() -> None:
    assert select_sufficient_chunks([], relevance_threshold=0.75) == []


def test_preserves_input_order_of_qualifying_chunks() -> None:
    chunks = [_chunk(0.99, "a.txt"), _chunk(0.8, "b.txt"), _chunk(0.76, "c.txt")]

    result = select_sufficient_chunks(chunks, relevance_threshold=0.75)

    assert [c.document_label for c in result] == ["a.txt", "b.txt", "c.txt"]


def test_has_sufficient_context_true_when_any_chunk_qualifies() -> None:
    assert has_sufficient_context([_chunk(0.8)], relevance_threshold=0.75) is True


def test_has_sufficient_context_false_when_none_qualify() -> None:
    assert has_sufficient_context([_chunk(0.5)], relevance_threshold=0.75) is False


def test_has_sufficient_context_false_for_empty_input() -> None:
    assert has_sufficient_context([], relevance_threshold=0.75) is False


def _chunk_with_content(content: str, label: str = "doc.txt") -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(), document_label=label, content=content, similarity=0.9
    )


def test_limit_context_chars_includes_everything_under_the_cap() -> None:
    chunks = [_chunk_with_content("a" * 100), _chunk_with_content("b" * 100)]

    result = limit_context_chars(chunks, max_context_chars=1000)

    assert result == chunks


def test_limit_context_chars_drops_chunks_once_the_cap_would_be_exceeded() -> None:
    chunks = [
        _chunk_with_content("a" * 100, "a.txt"),
        _chunk_with_content("b" * 100, "b.txt"),
        _chunk_with_content("c" * 100, "c.txt"),
    ]

    result = limit_context_chars(chunks, max_context_chars=150)

    assert [c.document_label for c in result] == ["a.txt"]


def test_limit_context_chars_always_includes_at_least_the_first_chunk() -> None:
    chunks = [_chunk_with_content("a" * 5000, "a.txt")]

    result = limit_context_chars(chunks, max_context_chars=10)

    assert result == chunks


def test_limit_context_chars_empty_input_returns_empty() -> None:
    assert limit_context_chars([], max_context_chars=1000) == []
