"""`/api/v1/admin/analytics` — tenant-scoped analytics summary (US3),
knowledge gaps (US4), and most-common-questions (US5) — feature
011-conversations-analytics. Shares `admin.py`'s `/api/v1/admin` prefix
(research.md §10). Every route depends on `get_current_administrator` +
`get_current_tenant` (FR-034).

All routes accept optional `start_date`/`end_date`; when either is
omitted, both default to `[now - ANALYTICS_DEFAULT_LOOKBACK_DAYS, now]`
(contracts/analytics-api.md). An inverted range (`end_date` before
`start_date`) is rejected with `400`.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from shiruno.api.deps import get_current_administrator, get_current_tenant
from shiruno.api.errors import ValidationAppError
from shiruno.api.schemas import (
    AnalyticsSummaryResponse,
    DateRangeOut,
    KnowledgeGapsResponse,
    LatencyStatsOut,
    OutcomeBreakdownOut,
    OutcomeStatsOut,
    ProviderUsageOut,
    QuestionFrequencyItem,
    TokenTotalsOut,
)
from shiruno.application.conversation_analytics import (
    get_analytics_summary,
    get_common_questions,
    get_knowledge_gaps,
)
from shiruno.config import get_settings
from shiruno.persistence.database import get_session
from shiruno.persistence.models import Administrator, Tenant

router = APIRouter(prefix="/api/v1/admin", tags=["analytics"])


def _resolve_date_range(
    start_date: datetime | None, end_date: datetime | None
) -> tuple[datetime, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    resolved_start = start_date or (now - timedelta(days=settings.ANALYTICS_DEFAULT_LOOKBACK_DAYS))
    resolved_end = end_date or now
    if resolved_end < resolved_start:
        raise ValidationAppError("end_date must not be before start_date.")
    return resolved_start, resolved_end


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary_route(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> AnalyticsSummaryResponse:
    resolved_start, resolved_end = _resolve_date_range(start_date, end_date)

    summary = get_analytics_summary(
        session, tenant_id=current_tenant.id, start=resolved_start, end=resolved_end
    )

    return AnalyticsSummaryResponse(
        range=DateRangeOut(start=resolved_start, end=resolved_end),
        total_requests=summary.total_requests,
        outcomes=OutcomeBreakdownOut(
            **{
                outcome.value: OutcomeStatsOut(count=stats.count, rate=stats.rate)
                for outcome, stats in summary.outcomes.items()
            }
        ),
        latency_ms=LatencyStatsOut(
            average=summary.latency_average, p50=summary.latency_p50, p95=summary.latency_p95
        ),
        tokens=TokenTotalsOut(
            input_total=summary.input_tokens_total, output_total=summary.output_tokens_total
        ),
        providers=[
            ProviderUsageOut(
                provider_name=provider.provider_name,
                provider_model=provider.provider_model,
                request_count=provider.request_count,
                input_tokens=provider.input_tokens,
                output_tokens=provider.output_tokens,
            )
            for provider in summary.providers
        ],
    )


@router.get("/analytics/knowledge-gaps", response_model=KnowledgeGapsResponse)
def get_knowledge_gaps_route(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> KnowledgeGapsResponse:
    settings = get_settings()
    resolved_start, resolved_end = _resolve_date_range(start_date, end_date)
    effective_limit = limit if limit is not None else settings.CONVERSATION_LIST_DEFAULT_PAGE_SIZE
    effective_limit = max(1, min(effective_limit, settings.CONVERSATION_LIST_MAX_PAGE_SIZE))

    items = get_knowledge_gaps(
        session,
        tenant_id=current_tenant.id,
        start=resolved_start,
        end=resolved_end,
        limit=effective_limit,
    )
    return KnowledgeGapsResponse(
        range=DateRangeOut(start=resolved_start, end=resolved_end),
        items=[
            QuestionFrequencyItem(
                normalized_question=item.normalized_question,
                example_question=item.example_question,
                count=item.count,
                last_seen_at=item.last_seen_at,
            )
            for item in items
        ],
    )


@router.get("/analytics/questions", response_model=KnowledgeGapsResponse)
def get_common_questions_route(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_admin: Administrator = Depends(get_current_administrator),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> KnowledgeGapsResponse:
    settings = get_settings()
    resolved_start, resolved_end = _resolve_date_range(start_date, end_date)
    effective_limit = limit if limit is not None else settings.CONVERSATION_LIST_DEFAULT_PAGE_SIZE
    effective_limit = max(1, min(effective_limit, settings.CONVERSATION_LIST_MAX_PAGE_SIZE))

    items = get_common_questions(
        session,
        tenant_id=current_tenant.id,
        start=resolved_start,
        end=resolved_end,
        limit=effective_limit,
    )
    return KnowledgeGapsResponse(
        range=DateRangeOut(start=resolved_start, end=resolved_end),
        items=[
            QuestionFrequencyItem(
                normalized_question=item.normalized_question,
                example_question=item.example_question,
                count=item.count,
                last_seen_at=item.last_seen_at,
            )
            for item in items
        ],
    )
