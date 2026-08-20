"""Honest re-index: regenerate embeddings for a document's already-stored
chunk text (feature 010-knowledge-base-admin, US5, research.md §4).

Never recomputes chunk boundaries — the full original source text is not
retained separately from its already-chunked pieces (see
`_ingest_content.py`'s docstring for why upload/replace *do* have that
text and re-index doesn't). Never regresses a document that was already
working: a failed re-index of an already-`ready` document leaves `status`
and every chunk's `embedding` completely unchanged; a failed re-index of
an already-`failed` document simply stays `failed` with an updated
message. `safe_error_message` is always the fixed generic string used
everywhere else in this feature — never the raw exception's text
(research.md §10a).
"""

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.api.errors import ConflictError, NotFoundAppError
from shiruno.application._ingest_content import INGESTION_FAILURE_MESSAGE
from shiruno.infra.logging import get_logger
from shiruno.persistence.models import (
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    ProviderKind,
    ProviderName,
    UsageRecord,
)
from shiruno.providers.embedding.protocol import EmbeddingProvider

logger = get_logger(__name__)

# A document with zero stored chunks (e.g. a document that failed *before*
# any chunk was ever persisted) has no real content to regenerate
# embeddings from — reporting success here would fabricate a ready
# document with nothing retrievable behind it (FR-027). Same fixed-string
# discipline as every other failure message in this feature.
NO_CONTENT_MESSAGE = "No stored content available to re-index. Replace the document instead."


def reindex_document(
    document_id: uuid.UUID,
    *,
    session: Session,
    embedding_provider: EmbeddingProvider,
    tenant_id: uuid.UUID,
    embedding_model_name: str,
) -> KnowledgeDocument:
    document = session.get(KnowledgeDocument, document_id)
    if document is None or document.deleted_at is not None or document.tenant_id != tenant_id:
        raise NotFoundAppError("Document not found.")
    if document.status == DocumentStatus.processing:
        raise ConflictError("Document is currently processing.")

    chunks = list(
        session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.position)
        )
        .scalars()
        .all()
    )

    if not chunks:
        document.safe_error_message = NO_CONTENT_MESSAGE
        session.flush()
        return document

    try:
        embed_start = time.monotonic()
        embeddings = embedding_provider.embed_passages([chunk.content for chunk in chunks])
        embed_latency_ms = int((time.monotonic() - embed_start) * 1000)
        session.add(
            UsageRecord(
                request_id=uuid.uuid4(),
                provider_kind=ProviderKind.embedding,
                provider_name=ProviderName.local_sentence_transformer,
                provider_model=embedding_model_name,
                input_tokens=None,
                output_tokens=None,
                success=True,
                latency_ms=embed_latency_ms,
            )
        )
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"{type(embedding_provider).__name__} returned {len(embeddings)} vectors "
                f"for {len(chunks)} chunks"
            )
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding = embedding
        document.status = DocumentStatus.ready
        document.indexed_at = datetime.now(UTC)
        document.safe_error_message = None
    except Exception:
        # Existing chunk embeddings are untouched above — nothing was
        # mutated before this except block runs. Logged server-side only.
        logger.exception("Re-index failed", extra={"document_id": str(document.id)})
        document.safe_error_message = INGESTION_FAILURE_MESSAGE
        # status intentionally left unchanged (research.md §4): an
        # already-ready document keeps serving its old embeddings; an
        # already-failed document simply stays failed.
    finally:
        session.flush()

    return document
