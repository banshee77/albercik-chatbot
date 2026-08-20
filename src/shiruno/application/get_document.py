"""Single tenant-scoped document fetch (feature 010-knowledge-base-admin,
US1, research.md §5). A missing, foreign-tenant, or soft-deleted/retired
document all raise the identical `NotFoundAppError` — same pattern as
`delete_document.py` (feature 009).
"""

import uuid

from sqlalchemy.orm import Session

from shiruno.api.errors import NotFoundAppError
from shiruno.persistence.models import KnowledgeDocument


def get_document(
    document_id: uuid.UUID, *, session: Session, tenant_id: uuid.UUID
) -> KnowledgeDocument:
    document = session.get(KnowledgeDocument, document_id)
    if document is None or document.deleted_at is not None or document.tenant_id != tenant_id:
        raise NotFoundAppError("Document not found.")
    return document
