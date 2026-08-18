"""Relevance-threshold evaluation and insufficient-context decision (T034;
FR-026, FR-027b). Top-K limiting itself happens at query time
(persistence/repositories.py, FR-025) against pgvector — this module's only
job is deciding whether chunks that came back are relevant enough to
ground an answer.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID
    document_label: str
    content: str
    similarity: float


def select_sufficient_chunks(
    chunks: list[RetrievedChunk], *, relevance_threshold: float
) -> list[RetrievedChunk]:
    """Returns only the chunks meeting `relevance_threshold`, in the order
    given (callers should pass chunks already ordered by similarity, most
    relevant first). An empty result means "insufficient information"
    (FR-026, FR-027b) — the caller decides the outcome, this only filters.

    KNOWN MVP RAG-QUALITY RISK (Phase 3 calibration checkpoint,
    2026-08-17, research.md §6 addendum): `relevance_threshold` is a
    retrieval-quality / defense-in-depth filter, NOT proof that a chunk
    clearing it actually answers the question. Calibration against a
    synthetic fixture set showed genuinely answerable questions and
    Albertos-related-but-unsupported questions can score nearly
    identically — this function cannot, and is not intended to, tell them
    apart. Deliberately not "fixed" here by raising the threshold further,
    keyword heuristics, more scope regexes, an LLM classifier, a
    reranker/cross-encoder, or hybrid search — those are all explicitly
    deferred; see research.md §6 addendum for the reasoning. Re-evaluate
    answerability once Phase 4 allows real Albertos content to be
    uploaded and calibrated against.
    """
    return [chunk for chunk in chunks if chunk.similarity >= relevance_threshold]


def has_sufficient_context(chunks: list[RetrievedChunk], *, relevance_threshold: float) -> bool:
    return len(select_sufficient_chunks(chunks, relevance_threshold=relevance_threshold)) > 0


def limit_context_chars(
    chunks: list[RetrievedChunk], *, max_context_chars: int
) -> list[RetrievedChunk]:
    """Greedily keeps chunks in the given order (most relevant first) until
    adding the next one would exceed `max_context_chars` of total chunk
    content — the context-size cap from Phase 5's cost/token limits
    (`settings.MAX_CONTEXT_CHARS`), applied after relevance filtering and
    before prompt assembly so the LLM call is always bounded regardless of
    how many/how large the chunks that cleared the relevance threshold
    turned out to be. Chunk *count* is separately capped upstream at query
    time via `RETRIEVAL_TOP_K` (persistence/repositories.py) — this only
    bounds total characters.

    Always includes at least the first (most relevant) chunk, even if it
    alone exceeds `max_context_chars` — answering from one oversized chunk
    is safer than silently answering with zero context because a limit was
    configured too low relative to real chunk sizes.
    """
    if not chunks:
        return []

    limited = [chunks[0]]
    total_chars = len(chunks[0].content)
    for chunk in chunks[1:]:
        next_total = total_chars + len(chunk.content)
        if next_total > max_context_chars:
            break
        limited.append(chunk)
        total_chars = next_total
    return limited
