"""`/api/v1/admin/conversations` — tenant-scoped conversation browsing
(feature 011-conversations-analytics, US1/US2). Shares `admin.py`'s
`/api/v1/admin` prefix (research.md §10). Every route depends on
`get_current_administrator` + `get_current_tenant` — resolved before any
route body executes, exactly like every other tenant-scoped admin route
(FR-034).

`GET /conversations` is registered before `GET /conversations/{conversation_id}`
is added in a later phase — no routing-order hazard here since `/conversations`
has no literal-path sibling that could collide with the `{conversation_id}`
pattern (contracts/conversations-api.md).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shiruno.api.deps import get_current_administrator, get_current_tenant
from shiruno.api.schemas import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    SourceSnapshotOut,
)
from shiruno.application.get_conversation import get_conversation
from shiruno.application.list_conversations import list_conversations
from shiruno.config import get_settings
from shiruno.persistence.database import get_session
from shiruno.persistence.models import (
    Administrator,
    ConversationOutcome,
    ConversationRecord,
    Tenant,
)

router = APIRouter(prefix="/api/v1/admin", tags=["conversations"])


@router.get("/conversations", response_model=ConversationListResponse)
def get_conversations(
    outcome: ConversationOutcome | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    q: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> ConversationListResponse:
    settings = get_settings()
    effective_limit = limit if limit is not None else settings.CONVERSATION_LIST_DEFAULT_PAGE_SIZE
    # Clamped, never rejected (FR-019, research.md §7) — a client cannot
    # request an unbounded result set regardless of what it asks for.
    effective_limit = max(1, min(effective_limit, settings.CONVERSATION_LIST_MAX_PAGE_SIZE))
    effective_offset = max(0, offset if offset is not None else 0)

    items, total = list_conversations(
        session,
        tenant_id=current_tenant.id,
        outcome=outcome,
        start_date=start_date,
        end_date=end_date,
        search=q,
        limit=effective_limit,
        offset=effective_offset,
    )
    return ConversationListResponse(
        items=[
            ConversationSummary(
                id=record.id,
                request_id=record.request_id,
                question=record.question,
                outcome=record.outcome.value,
                created_at=record.created_at,
                latency_ms=record.latency_ms,
            )
            for record in items
        ],
        total=total,
        limit=effective_limit,
        offset=effective_offset,
    )


def _to_detail(record: ConversationRecord) -> ConversationDetail:
    return ConversationDetail(
        id=record.id,
        request_id=record.request_id,
        question=record.question,
        answer=record.answer,
        outcome=record.outcome.value,
        created_at=record.created_at,
        latency_ms=record.latency_ms,
        sources=[
            SourceSnapshotOut(document_id=uuid.UUID(source["document_id"]), label=source["label"])
            for source in record.sources
        ]
        if record.sources is not None
        else None,
        provider_name=record.provider_name.value if record.provider_name is not None else None,
        provider_model=record.provider_model,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        provider_metrics=record.provider_metrics,
        safe_failure_category=record.safe_failure_category.value
        if record.safe_failure_category is not None
        else None,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation_route(
    conversation_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> ConversationDetail:
    record = get_conversation(conversation_id, session=session, tenant_id=current_tenant.id)
    return _to_detail(record)
