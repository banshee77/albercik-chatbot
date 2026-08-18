"""T026 — unit tests for the deterministic paragraph-aware chunker
(domain/chunking.py, FR-018-FR-021). No DB, no network, no providers.
"""

import pytest

from albercik_chatbot.domain.chunking import chunk_text


def test_same_input_always_produces_same_chunks() -> None:
    text = "Pierwszy akapit.\n\nDrugi akapit z dłuższym tekstem opisowym.\n\nTrzeci akapit."

    first = chunk_text(text, chunk_size_chars=40, chunk_overlap_chars=10)
    second = chunk_text(text, chunk_size_chars=40, chunk_overlap_chars=10)

    assert first == second


def test_no_chunk_exceeds_configured_size() -> None:
    text = "Akapit jeden. " * 50 + "\n\n" + "Akapit dwa. " * 50

    chunks = chunk_text(text, chunk_size_chars=100, chunk_overlap_chars=20)

    assert all(len(chunk) <= 100 for chunk in chunks)


def test_no_empty_or_whitespace_only_chunks() -> None:
    text = "Akapit pierwszy.\n\n\n\n   \n\n\nAkapit drugi."

    chunks = chunk_text(text, chunk_size_chars=1000, chunk_overlap_chars=100)

    assert all(chunk.strip() for chunk in chunks)


def test_empty_input_returns_empty_list() -> None:
    assert chunk_text("", chunk_size_chars=100, chunk_overlap_chars=10) == []
    assert chunk_text("   \n\n  ", chunk_size_chars=100, chunk_overlap_chars=10) == []


def test_paragraphs_that_fit_are_not_split() -> None:
    text = "Krótki akapit jeden.\n\nKrótki akapit dwa."

    chunks = chunk_text(text, chunk_size_chars=1000, chunk_overlap_chars=100)

    assert len(chunks) == 1
    assert "Krótki akapit jeden." in chunks[0]
    assert "Krótki akapit dwa." in chunks[0]


def test_long_paragraph_is_hard_split_with_overlap() -> None:
    text = "A" * 50 + "B" * 50  # single paragraph, no blank lines, 100 chars

    chunks = chunk_text(text, chunk_size_chars=60, chunk_overlap_chars=15)

    assert len(chunks) >= 2
    # the tail of the first chunk reappears at the start of the second
    overlap_tail = chunks[0][-15:]
    assert chunks[1].startswith(overlap_tail)


def test_chunks_preserve_document_order() -> None:
    text = "Alfa akapit.\n\nBeta akapit.\n\nGamma akapit."

    chunks = chunk_text(text, chunk_size_chars=20, chunk_overlap_chars=0)

    joined = " ".join(chunks)
    assert joined.index("Alfa") < joined.index("Beta") < joined.index("Gamma")


@pytest.mark.parametrize(
    "chunk_size_chars,chunk_overlap_chars",
    [(0, 0), (-1, 0), (100, 100), (100, 150), (100, -1)],
)
def test_invalid_configuration_raises(chunk_size_chars: int, chunk_overlap_chars: int) -> None:
    with pytest.raises(ValueError):
        chunk_text(
            "some text",
            chunk_size_chars=chunk_size_chars,
            chunk_overlap_chars=chunk_overlap_chars,
        )
