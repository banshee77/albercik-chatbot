"""Per-aggregate repository functions (T036).

`search_similar_chunks` is US1's retrieval query: `pgvector` cosine
distance (`<=>`, via `Vector.cosine_distance`), a configurable Top-K
(FR-025), and exclusion of soft-deleted documents/chunks (data-model.md
"Soft-deleted documents/chunks are excluded from retrieval"). Relevance-
threshold filtering itself is a domain decision (domain/retrieval.py,
FR-026), not this query's job.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.domain.retrieval import RetrievedChunk
from shiruno.persistence.models import DocumentChunk, DocumentStatus, KnowledgeDocument


def search_similar_chunks(
    session: Session, query_embedding: list[float], *, top_k: int
) -> list[RetrievedChunk]:
    """Top-`top_k` chunks nearest `query_embedding` by cosine similarity,
    most similar first, excluding chunks belonging to a soft-deleted
    document. `pgvector`'s `cosine_distance` returns `1 - cosine_similarity`
    for the normalized vectors both providers produce, so similarity is
    recovered as `1 - distance`.
    """
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(DocumentChunk, KnowledgeDocument, distance.label("distance"))
        .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
        .where(
            KnowledgeDocument.deleted_at.is_(None),
            KnowledgeDocument.status == DocumentStatus.ready,
        )
        .order_by(distance)
        .limit(top_k)
    )
    rows = session.execute(stmt).all()
    return [
        RetrievedChunk(
            document_id=document.id,
            document_label=document.original_filename,
            content=chunk.content,
            similarity=1.0 - distance_value,
        )
        for chunk, document, distance_value in rows
    ]
