"""Tenant-scoped analytics: summary aggregates (US3), knowledge gaps
(US4), and most-common-questions (US5) — feature 011-conversations-analytics,
research.md §6, §7, §9, §10; contracts/analytics-api.md. Kept in one
cohesive module since all three share date-range-bounding logic and read
only `ConversationRecord`'s own columns — no join to `UsageRecord` or
`KnowledgeDocument`, no current-provider-configuration lookup
(research.md §2a).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shiruno.persistence.models import ConversationOutcome, ConversationRecord


@dataclass
class OutcomeStats:
    count: int
    rate: float


@dataclass
class ProviderUsage:
    provider_name: str
    provider_model: str
    request_count: int
    input_tokens: int
    output_tokens: int


@dataclass
class AnalyticsSummary:
    total_requests: int
    outcomes: dict[ConversationOutcome, OutcomeStats]
    latency_average: float | None
    latency_p50: float | None
    latency_p95: float | None
    input_tokens_total: int
    output_tokens_total: int
    providers: list[ProviderUsage]


@dataclass
class QuestionFrequency:
    normalized_question: str
    example_question: str
    count: int
    last_seen_at: datetime


def get_analytics_summary(
    session: Session, *, tenant_id: uuid.UUID, start: datetime, end: datetime
) -> AnalyticsSummary:
    date_filter = (
        ConversationRecord.tenant_id == tenant_id,
        ConversationRecord.created_at >= start,
        ConversationRecord.created_at <= end,
    )

    total_requests = session.execute(
        select(func.count()).select_from(ConversationRecord).where(*date_filter)
    ).scalar_one()

    outcome_rows = session.execute(
        select(ConversationRecord.outcome, func.count())
        .where(*date_filter)
        .group_by(ConversationRecord.outcome)
    ).all()
    counts = dict.fromkeys(ConversationOutcome, 0)
    for outcome, count in outcome_rows:
        counts[outcome] = count
    outcomes = {
        outcome: OutcomeStats(
            count=counts[outcome],
            rate=(counts[outcome] / total_requests) if total_requests else 0.0,
        )
        for outcome in ConversationOutcome
    }

    latency_average, latency_p50, latency_p95 = session.execute(
        select(
            func.avg(ConversationRecord.latency_ms),
            func.percentile_cont(0.5).within_group(ConversationRecord.latency_ms),
            func.percentile_cont(0.95).within_group(ConversationRecord.latency_ms),
        ).where(*date_filter)
    ).one()

    input_tokens_total, output_tokens_total = session.execute(
        select(
            func.coalesce(func.sum(ConversationRecord.input_tokens), 0),
            func.coalesce(func.sum(ConversationRecord.output_tokens), 0),
        ).where(*date_filter)
    ).one()

    provider_rows = session.execute(
        select(
            ConversationRecord.provider_name,
            ConversationRecord.provider_model,
            func.count(),
            func.coalesce(func.sum(ConversationRecord.input_tokens), 0),
            func.coalesce(func.sum(ConversationRecord.output_tokens), 0),
        )
        .where(*date_filter, ConversationRecord.provider_name.is_not(None))
        .group_by(ConversationRecord.provider_name, ConversationRecord.provider_model)
    ).all()
    providers = [
        ProviderUsage(
            provider_name=row_provider_name.value,
            provider_model=row_provider_model,
            request_count=row_request_count,
            input_tokens=row_input_tokens,
            output_tokens=row_output_tokens,
        )
        for (
            row_provider_name,
            row_provider_model,
            row_request_count,
            row_input_tokens,
            row_output_tokens,
        ) in provider_rows
    ]

    return AnalyticsSummary(
        total_requests=total_requests,
        outcomes=outcomes,
        latency_average=float(latency_average) if latency_average is not None else None,
        latency_p50=float(latency_p50) if latency_p50 is not None else None,
        latency_p95=float(latency_p95) if latency_p95 is not None else None,
        input_tokens_total=input_tokens_total,
        output_tokens_total=output_tokens_total,
        providers=providers,
    )


def _grouped_question_frequency(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    start: datetime,
    end: datetime,
    outcome: ConversationOutcome | None,
    limit: int,
) -> list[QuestionFrequency]:
    """Deterministic exact/normalized-text grouping (research.md §6,
    FR-028) — no semantic similarity of any kind. `example_question` is the
    raw `question` text of the most-recently-seen row in each normalized
    group, picked via `ROW_NUMBER()` rather than a second query per group.
    """
    date_filter = [
        ConversationRecord.tenant_id == tenant_id,
        ConversationRecord.created_at >= start,
        ConversationRecord.created_at <= end,
    ]
    if outcome is not None:
        date_filter.append(ConversationRecord.outcome == outcome)

    ranked = (
        select(
            ConversationRecord.normalized_question.label("normalized_question"),
            ConversationRecord.question.label("question"),
            ConversationRecord.created_at.label("created_at"),
            func.count()
            .over(partition_by=ConversationRecord.normalized_question)
            .label("group_count"),
            func.row_number()
            .over(
                partition_by=ConversationRecord.normalized_question,
                order_by=ConversationRecord.created_at.desc(),
            )
            .label("rn"),
        )
        .where(*date_filter)
        .subquery()
    )

    stmt = (
        select(
            ranked.c.normalized_question,
            ranked.c.question,
            ranked.c.created_at,
            ranked.c.group_count,
        )
        .where(ranked.c.rn == 1)
        .order_by(ranked.c.group_count.desc(), ranked.c.created_at.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [
        QuestionFrequency(
            normalized_question=normalized_question,
            example_question=question,
            count=group_count,
            last_seen_at=created_at,
        )
        for normalized_question, question, created_at, group_count in rows
    ]


def get_knowledge_gaps(
    session: Session, *, tenant_id: uuid.UUID, start: datetime, end: datetime, limit: int
) -> list[QuestionFrequency]:
    """Only `insufficient_information` conversations contribute (FR-029) —
    the primary signal for what the assistant repeatedly fails to answer."""
    return _grouped_question_frequency(
        session,
        tenant_id=tenant_id,
        start=start,
        end=end,
        outcome=ConversationOutcome.insufficient_information,
        limit=limit,
    )


def get_common_questions(
    session: Session, *, tenant_id: uuid.UUID, start: datetime, end: datetime, limit: int
) -> list[QuestionFrequency]:
    """Same grouping/ranking mechanics as `get_knowledge_gaps`, across
    **all** outcomes (FR-030) — general usage-pattern visibility, not only
    failures."""
    return _grouped_question_frequency(
        session, tenant_id=tenant_id, start=start, end=end, outcome=None, limit=limit
    )
