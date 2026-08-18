"""EmbeddingProvider Protocol (Principle VI, FR-024, FR-034).

Core retrieval logic (`domain/`, `application/`, `persistence/`) depends
only on this Protocol — never on `sentence_transformers` or any other
embedding vendor/library directly. Every implementation MUST return
`EMBEDDING_DIMENSIONS`-length vectors (384, matching the `pgvector`
`vector(384)` column and `intfloat/multilingual-e5-small` — research.md
§4) so stored chunk embeddings and query-time question embeddings are
always dimensionally compatible (FR-024).

The Protocol distinguishes *query* embedding (a visitor's question, at
retrieval time) from *passage* embedding (document chunks, at ingestion
time) as two explicit methods, rather than one generic `embed(text)`. This
is deliberately model-agnostic: many embedding models (e.g. the E5 family)
are trained asymmetrically and expect queries and passages to be prepared
differently to get good retrieval quality, but nothing here says *how* —
that's entirely up to each concrete implementation
(`LocalSentenceTransformerEmbeddingProvider` owns the E5-specific
`"query: "`/`"passage: "` prefixing; `domain/`/`application/` code only
ever calls these two methods and never knows the concrete model is E5,
or that prefixing exists at all).
"""

from collections.abc import Sequence
from typing import Protocol

EMBEDDING_DIMENSIONS = 384


class EmbeddingProvider(Protocol):
    def embed_query(self, text: str) -> list[float]:
        """Returns a single `EMBEDDING_DIMENSIONS`-length vector for a
        query (a visitor's question, at retrieval time) — FR-022."""
        ...

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Batch form for passages (document chunks, at ingestion time),
        in input order. Implementations MAY batch for efficiency; callers
        MUST NOT assume any particular batching strategy."""
        ...
