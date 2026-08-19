"""List active (non-deleted) knowledge documents (T050, FR-014).

Tenant-scoped (feature 009-admin-platform-foundation, FR-015): only the
calling administrator's own tenant's documents are ever returned.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.persistence.models import KnowledgeDocument


def list_documents(session: Session, *, tenant_id: uuid.UUID) -> list[KnowledgeDocument]:
    stmt = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.deleted_at.is_(None), KnowledgeDocument.tenant_id == tenant_id)
        .order_by(KnowledgeDocument.uploaded_at.desc())
    )
    return list(session.execute(stmt).scalars().all())
