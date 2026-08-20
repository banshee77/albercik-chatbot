"""Shared validate/chunk/embed/persist/status-transition helper, extracted
from `upload_document.py` (feature 010-knowledge-base-admin, research.md
§10) so `upload_document()` and `replace_document()` cannot silently drift
apart on this safety-critical behavior.

Validation (extension, size, UTF-8, empty-content, empty-chunks) happens
*before* any `KnowledgeDocument` row is created — invalid content leaves
nothing stored, for both upload and replace alike (FR-009, FR-015).
A *processing* failure (the embedding call itself), by contrast, does
create a `status=failed` row — the caller decides what a failed row means
for its own operation.

`safe_error_message` is always one of a small, fixed set of generic,
developer-authored strings (research.md §10a) — never derived from, or
containing any part of, the raw exception's message, type, or `str(exc)`.
The raw exception is still logged server-side only, via `logger.exception`.
"""

import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from shiruno.api.errors import PayloadTooLargeError, ValidationAppError
from shiruno.domain.chunking import chunk_text
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

_ALLOWED_EXTENSION = ".txt"

# Fixed, generic, developer-authored — never derived from a raw exception
# (research.md §10a). This is the string every embedding-failure path
# (upload, replace, re-index) uses.
INGESTION_FAILURE_MESSAGE = "Embedding generation failed. Retry indexing or replace the document."


def ingest_content(
    *,
    filename: str,
    content_bytes: bytes,
    tenant_id: uuid.UUID,
    uploaded_by_admin_id: uuid.UUID,
    replaces_document_id: uuid.UUID | None,
    session: Session,
    embedding_provider: EmbeddingProvider,
    max_upload_size_bytes: int,
    chunk_size_chars: int,
    chunk_overlap_chars: int,
    embedding_model_name: str,
) -> KnowledgeDocument:
    # Filename/MIME are signals, never trusted alone (FR-012): the
    # extension check below is combined with real content-based validation
    # (UTF-8 decoding, non-empty) — a client-supplied Content-Type header
    # is never consulted at all.
    if not filename.lower().endswith(_ALLOWED_EXTENSION):
        raise ValidationAppError("Only .txt files are accepted.")

    if len(content_bytes) > max_upload_size_bytes:
        raise PayloadTooLargeError("File exceeds the configured maximum size.")

    if len(content_bytes) == 0:
        raise ValidationAppError("File is empty.")

    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationAppError("File is not valid UTF-8.") from exc

    if not text.strip():
        raise ValidationAppError("File has no meaningful content.")

    chunks = chunk_text(
        text, chunk_size_chars=chunk_size_chars, chunk_overlap_chars=chunk_overlap_chars
    )
    if not chunks:
        raise ValidationAppError("File has no meaningful content.")

    document = KnowledgeDocument(
        original_filename=filename,
        uploaded_by_admin_id=uploaded_by_admin_id,
        tenant_id=tenant_id,
        replaces_document_id=replaces_document_id,
        status=DocumentStatus.processing,
    )
    session.add(document)
    session.flush()

    try:
        embed_start = time.monotonic()
        embeddings = embedding_provider.embed_passages(chunks)
        embed_latency_ms = int((time.monotonic() - embed_start) * 1000)
        # One row for this batched passage-embedding call — operational
        # visibility only (Design Constraint 3): local embedding calls have
        # no per-call provider cost and MUST NEVER be counted toward, or
        # reduce, the LLM budget (infra/budget.py only ever queries
        # provider_kind='llm' rows).
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
        for position, (chunk_content, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    position=position,
                    content=chunk_content,
                    embedding=embedding,
                )
            )
        document.status = DocumentStatus.ready
        document.indexed_at = datetime.now(UTC)
        document.safe_error_message = None
    except Exception:
        # No chunks were added() above if embed_passages itself raised, so
        # nothing partial is stored either way. Logged server-side only —
        # the client sees this document's status and a fixed generic
        # message, never exception detail (FR-013, research.md §10a).
        logger.exception("Document ingestion failed", extra={"document_id": str(document.id)})
        document.status = DocumentStatus.failed
        document.safe_error_message = INGESTION_FAILURE_MESSAGE
    finally:
        session.flush()

    return document
