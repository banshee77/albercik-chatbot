"""Tenant-scoped, filterable, bounded-pagination conversation list (feature
011-conversations-analytics, US1, research.md §7, §8; contracts/
conversations-api.md).

Newest-first (`created_at` descending, `id` descending tiebreak) for a
fully deterministic order regardless of how many rows share the same
`created_at` value. `limit`/`offset` are trusted as already clamped by the
caller (`api/routers/conversations.py`) — this function only applies them.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shiruno.persistence.models import ConversationOutcome, ConversationRecord


def list_conversations(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    outcome: ConversationOutcome | None,
    start_date: datetime | None,
    end_date: datetime | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[ConversationRecord], int]:
    filters = [ConversationRecord.tenant_id == tenant_id]
    if outcome is not None:
        filters.append(ConversationRecord.outcome == outcome)
    if start_date is not None:
        filters.append(ConversationRecord.created_at >= start_date)
    if end_date is not None:
        filters.append(ConversationRecord.created_at <= end_date)
    if search:
        filters.append(ConversationRecord.question.ilike(f"%{search}%"))

    total = session.execute(
        select(func.count()).select_from(ConversationRecord).where(*filters)
    ).scalar_one()

    stmt = (
        select(ConversationRecord)
        .where(*filters)
        .order_by(ConversationRecord.created_at.desc(), ConversationRecord.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(session.execute(stmt).scalars().all())
    return items, total
