"""Safe document replacement (feature 010-knowledge-base-admin, US3,
research.md §3, data-model.md "Concurrency invariant").

Creates a new successor document up front and runs it through the same
validate/chunk/embed/persist path as a new upload (`_ingest_content`) —
*without* holding any lock on the predecessor during that potentially slow
work, so the predecessor keeps serving retrieval the entire time. Only
once ingestion succeeds does this acquire a row-level lock
(`SELECT ... FOR UPDATE`) on the predecessor and, under that lock,
authoritatively decide whether this request may retire the predecessor and
activate its successor. Of any number of concurrent replace requests for
the same predecessor, exactly one observes `deleted_at IS NULL` under the
lock and wins; every other loses and its successor is marked `failed` with
a specific, safe race-loss message — never activated, never retiring the
predecessor.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.api.errors import NotFoundAppError
from shiruno.application._ingest_content import ingest_content
from shiruno.persistence.models import Administrator, DocumentStatus, KnowledgeDocument
from shiruno.providers.embedding.protocol import EmbeddingProvider

RACE_LOSS_MESSAGE = "This document was already replaced by another request."


def replace_document(
    predecessor_id: uuid.UUID,
    *,
    filename: str,
    content_bytes: bytes,
    session: Session,
    embedding_provider: EmbeddingProvider,
    uploaded_by: Administrator,
    tenant_id: uuid.UUID,
    max_upload_size_bytes: int,
    chunk_size_chars: int,
    chunk_overlap_chars: int,
    embedding_model_name: str,
) -> KnowledgeDocument:
    predecessor = session.get(KnowledgeDocument, predecessor_id)
    if (
        predecessor is None
        or predecessor.deleted_at is not None
        or predecessor.tenant_id != tenant_id
    ):
        raise NotFoundAppError("Document not found.")

    # replaces_document_id is deliberately NOT set here: inserting a row
    # with a foreign key already takes an implicit FOR KEY SHARE lock on
    # the referenced (predecessor) row, which would race against this same
    # function's later FOR UPDATE upgrade under real concurrency — two
    # concurrent replace requests both inserting a successor FK'd to the
    # same predecessor deadlock on that lock-upgrade. Set only once this
    # request already holds the FOR UPDATE lock below and has won.
    successor = ingest_content(
        filename=filename,
        content_bytes=content_bytes,
        tenant_id=tenant_id,
        uploaded_by_admin_id=uploaded_by.id,
        replaces_document_id=None,
        session=session,
        embedding_provider=embedding_provider,
        max_upload_size_bytes=max_upload_size_bytes,
        chunk_size_chars=chunk_size_chars,
        chunk_overlap_chars=chunk_overlap_chars,
        embedding_model_name=embedding_model_name,
    )

    if successor.status != DocumentStatus.ready:
        # Ingestion itself failed — the predecessor was never touched, no
        # lock is needed (FR-017).
        return successor

    # Ingestion succeeded. This is the ONLY part of replace that holds a
    # row lock, and it holds it only until this request's transaction
    # commits at the end of the request — never spanning the embedding
    # call above (research.md §3).
    # populate_existing=True: `predecessor` (looked up above) is already in
    # this session's identity map. Without this, SQLAlchemy would silently
    # reuse that already-loaded Python object's stale `deleted_at` instead
    # of refreshing it from the row this locked SELECT just (re-)fetched —
    # the lock itself would block correctly at the database level, but the
    # ORM-side value read afterward would still be wrong.
    locked_predecessor = session.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.id == predecessor.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()

    if locked_predecessor.deleted_at is not None:
        # Lost the race: another request already retired this predecessor.
        # This successor must NOT become active retrieval knowledge.
        successor.status = DocumentStatus.failed
        successor.safe_error_message = RACE_LOSS_MESSAGE
        session.flush()
        return successor

    locked_predecessor.deleted_at = datetime.now(UTC)
    successor.replaces_document_id = predecessor.id
    session.flush()
    return successor
