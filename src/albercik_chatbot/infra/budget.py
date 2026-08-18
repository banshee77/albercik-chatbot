"""LLM budget check + kill switch (research.md §3; tasks.md T063).

Budget accounting reuses `usage_records` (FR-047) rather than a second
counter table (YAGNI/DRY) — the check queries a `COUNT(*)` of
`provider_kind == 'llm'` rows created within the current rolling window,
compared against the configured hourly limit. Filtering to
`provider_kind == 'llm'` is the entire mechanism that keeps local
embedding activity from ever reducing or exhausting this budget (Design
Constraint 3) — an `embedding` row is simply invisible to this query.

`LLM_ENABLED=false` is checked first and is a pure config read, no DB
round trip at all — the cheapest possible reject, satisfying "reject as
early and as cheaply as possible."

Fail-closed: if the budget query itself raises (DB unavailable/error),
this returns `allowed=False` rather than letting the exception propagate
— an application that cannot verify it is under budget must assume it
might not be (Principle X, FR-045).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from albercik_chatbot.infra.logging import get_logger
from albercik_chatbot.persistence.models import ProviderKind, UsageRecord

logger = get_logger(__name__)

_BUDGET_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class BudgetCheckResult:
    allowed: bool


def check_llm_budget(
    session: Session, *, llm_enabled: bool, max_requests_per_hour: int, now: datetime | None = None
) -> BudgetCheckResult:
    if not llm_enabled:
        return BudgetCheckResult(allowed=False)

    current_time = now or datetime.now(UTC)
    window_start = current_time - _BUDGET_WINDOW
    try:
        count = session.execute(
            select(func.count())
            .select_from(UsageRecord)
            .where(UsageRecord.provider_kind == ProviderKind.llm)
            .where(UsageRecord.created_at >= window_start)
        ).scalar_one()
    except Exception:
        logger.exception("LLM budget check failed; failing closed")
        return BudgetCheckResult(allowed=False)

    return BudgetCheckResult(allowed=count < max_requests_per_hour)
