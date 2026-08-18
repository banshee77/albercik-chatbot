"""Deterministic, paragraph-aware character chunker (T032; research.md §5;
FR-018-FR-021). Plain Python string splitting — no framework — so the same
input always produces the same chunks.
"""

import re

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def chunk_text(text: str, *, chunk_size_chars: int, chunk_overlap_chars: int) -> list[str]:
    """Splits `text` into paragraphs on blank lines, then greedily packs
    paragraphs into chunks up to `chunk_size_chars`, carrying up to
    `chunk_overlap_chars` trailing characters of each chunk into the start
    of the next (FR-019). A paragraph longer than `chunk_size_chars` on its
    own is hard-split. Empty/whitespace-only chunks are never returned
    (FR-021); chunk order matches document order (FR-020, positions are
    assigned by the caller from list order).
    """
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be positive")
    if not (0 <= chunk_overlap_chars < chunk_size_chars):
        raise ValueError("chunk_overlap_chars must be in [0, chunk_size_chars)")

    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        stripped = current.strip()
        if stripped:
            chunks.append(stripped)
        current = current[-chunk_overlap_chars:].lstrip() if chunk_overlap_chars else ""

    for paragraph in paragraphs:
        remainder = paragraph
        while remainder:
            separator = "\n\n" if current else ""
            room = chunk_size_chars - len(current) - len(separator)
            if room <= 0:
                flush()
                separator = "\n\n" if current else ""
                room = chunk_size_chars - len(current) - len(separator)
            # Guarantees forward progress even in a pathological
            # near-boundary config (chunk_overlap_chars close to
            # chunk_size_chars): always consume at least one character
            # rather than flushing the same unchanged overlap forever.
            room = max(room, 1)

            take, remainder = remainder[:room], remainder[room:]
            current = f"{current}{separator}{take}"

    if current.strip():
        chunks.append(current.strip())

    return chunks
