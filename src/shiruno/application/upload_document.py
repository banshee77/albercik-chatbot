"""User Story 2 upload use case (T049).

Validates before any processing (FR-009-FR-013), chunks via
`domain/chunking.py`, embeds every chunk via the injected
`EmbeddingProvider.embed_passages(...)` — never `embed_query(...)`, which
is reserved for questions at retrieval time (providers/embedding/
protocol.py) — and stores `KnowledgeDocument` + `DocumentChunk` rows.

The uploaded filename is stored only as a display label
(`KnowledgeDocument.original_filename`) and is never used to construct a
filesystem path — there is no filesystem storage anywhere in this design
(data-model.md); document content lives only as TEXT/`vector` columns in
Postgres. Path traversal therefore has no code path to exploit regardless
of what filename is supplied (FR-012, FR-013): a `../../etc/passwd.txt`
filename is accepted like any other and stored under a system-generated
UUID, exactly like spec.md's own Edge Cases require.
"""

import time
import uuid

from sqlalchemy.orm import Session

from shiruno.api.errors import PayloadTooLargeError, ValidationAppError
from shiruno.domain.chunking import chunk_text
from shiruno.infra.logging import get_logger
from shiruno.persistence.models import (
    Administrator,
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


def upload_document(
    *,
    filename: str,
    content_bytes: bytes,
    session: Session,
    embedding_provider: EmbeddingProvider,
    uploaded_by: Administrator,
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
        uploaded_by_admin_id=uploaded_by.id,
        status=DocumentStatus.processing,
    )
    session.add(document)
    session.flush()

    try:
        embed_start = time.monotonic()
        embeddings = embedding_provider.embed_passages(chunks)
        embed_latency_ms = int((time.monotonic() - embed_start) * 1000)
        # One row for this batched passage-embedding call (T065) —
        # operational visibility only (Design Constraint 3): local
        # embedding calls have no per-call provider cost and MUST NEVER be
        # counted toward, or reduce, the LLM budget (infra/budget.py only
        # ever queries provider_kind='llm' rows).
        session.add(
            UsageRecord(
                request_id=uuid.uuid4(),
                provider_kind=ProviderKind.embedding,
                # Always the local sentence-transformers model — ingestion
                # embedding is unaffected by LLM_PROVIDER (Design
                # Constraint 3; feature 002-add-ollama-provider).
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
    except Exception:
        # No chunks were added() above if embed_passages itself raised, so
        # nothing partial is stored either way (data-model.md "no chunks
        # are stored" on failure). Logged server-side only — the client
        # sees this document's status, never exception detail (FR-050).
        logger.exception("Document ingestion failed", extra={"document_id": str(document.id)})
        document.status = DocumentStatus.failed
    finally:
        session.flush()

    return document
