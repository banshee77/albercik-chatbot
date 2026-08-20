"""User Story 2 upload use case (T049).

Thin wrapper around the shared `_ingest_content.ingest_content()` helper
(feature 010-knowledge-base-admin, research.md §10) — upload's own
validate/chunk/embed/persist/status-transition behavior is unchanged,
only relocated so `replace_document()` can reuse it exactly.

The uploaded filename is stored only as a display label
(`KnowledgeDocument.original_filename`) and is never used to construct a
filesystem path — there is no filesystem storage anywhere in this design
(data-model.md); document content lives only as TEXT/`vector` columns in
Postgres. Path traversal therefore has no code path to exploit regardless
of what filename is supplied (FR-012, FR-013): a `../../etc/passwd.txt`
filename is accepted like any other and stored under a system-generated
UUID, exactly like spec.md's own Edge Cases require.
"""

import uuid

from sqlalchemy.orm import Session

from shiruno.application._ingest_content import ingest_content
from shiruno.persistence.models import Administrator, KnowledgeDocument
from shiruno.providers.embedding.protocol import EmbeddingProvider


def upload_document(
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
    return ingest_content(
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
