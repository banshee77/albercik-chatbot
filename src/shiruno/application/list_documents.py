"""List active (non-deleted) knowledge documents (T050, FR-014)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.persistence.models import KnowledgeDocument


def list_documents(session: Session) -> list[KnowledgeDocument]:
    stmt = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.deleted_at.is_(None))
        .order_by(KnowledgeDocument.uploaded_at.desc())
    )
    return list(session.execute(stmt).scalars().all())
