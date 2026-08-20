"""Tenant-scoped knowledge-base health summary (feature
010-knowledge-base-admin, US1, FR-028-FR-030).

`chunks` and `last_indexed_at` are scoped to the tenant's currently
`ready`, non-deleted documents — i.e., chunks that actually participate in
retrieval right now (contracts/documents-api-delta.md).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shiruno.persistence.models import DocumentChunk, DocumentStatus, KnowledgeDocument


@dataclass
class KnowledgeHealth:
    total: int
    ready: int
    processing: int
    failed: int
    chunks: int
    ready_for_chat: bool
    last_indexed_at: datetime | None


def get_knowledge_health(session: Session, *, tenant_id: uuid.UUID) -> KnowledgeHealth:
    rows = session.execute(
        select(KnowledgeDocument.status, func.count())
        .where(KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.deleted_at.is_(None))
        .group_by(KnowledgeDocument.status)
    ).all()
    counts = dict.fromkeys(DocumentStatus, 0)
    for document_status, count in rows:
        counts[document_status] = count
    ready = counts[DocumentStatus.ready]

    chunks = session.execute(
        select(func.count())
        .select_from(DocumentChunk)
        .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
        .where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.deleted_at.is_(None),
            KnowledgeDocument.status == DocumentStatus.ready,
        )
    ).scalar_one()

    last_indexed_at = session.execute(
        select(func.max(KnowledgeDocument.indexed_at)).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.deleted_at.is_(None),
            KnowledgeDocument.status == DocumentStatus.ready,
        )
    ).scalar_one()

    return KnowledgeHealth(
        total=sum(counts.values()),
        ready=ready,
        processing=counts[DocumentStatus.processing],
        failed=counts[DocumentStatus.failed],
        chunks=chunks,
        ready_for_chat=ready > 0,
        last_indexed_at=last_indexed_at,
    )
