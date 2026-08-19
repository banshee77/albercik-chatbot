"""Soft-delete a knowledge document (T051, FR-015, FR-016).

Immediate exclusion from retrieval is guaranteed by
`persistence/repositories.py`'s `search_similar_chunks`, which already
filters on `KnowledgeDocument.deleted_at IS NULL` (T036) — deleting here
requires no separate re-indexing, cache invalidation, or app restart
(SC-007). Deleting an already-deleted or unknown document is rejected the
same safe way (spec.md Edge Cases): a generic not-found, no further detail.

Tenant-scoped (feature 009-admin-platform-foundation, FR-015, FR-018,
FR-024): a document belonging to a different tenant is treated exactly
like a nonexistent one — same branch, same exception, same message — so a
cross-tenant delete attempt cannot distinguish "not found" from "not
yours."
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from shiruno.api.errors import NotFoundAppError
from shiruno.persistence.models import KnowledgeDocument


def delete_document(document_id: uuid.UUID, *, session: Session, tenant_id: uuid.UUID) -> None:
    document = session.get(KnowledgeDocument, document_id)
    if document is None or document.deleted_at is not None or document.tenant_id != tenant_id:
        raise NotFoundAppError("Document not found.")

    document.deleted_at = datetime.now(UTC)
    session.flush()
