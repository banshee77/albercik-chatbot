"""LLM budget check + kill switch (research.md §3; tasks.md T063).

Budget accounting reuses `usage_records` (FR-047) rather than a second
counter table (YAGNI/DRY) — the check queries a `COUNT(*)` of
`provider_kind == 'llm' AND provider_name == 'anthropic'` rows created
within the current rolling window, compared against the configured hourly
limit. `provider_kind == 'llm'` alone is no longer sufficient (feature
002-add-ollama-provider): a local-model (`provider_name == 'ollama'`) row
is also `llm`-kind, so the additional `provider_name` filter is what keeps
both local embedding activity *and* local-LLM activity from ever reducing
or exhausting this budget (data-model.md, research.md §4) — an
`embedding` row or an `ollama` row is simply invisible to this query.

`LLM_ENABLED=false` is checked first and is a pure config read, no DB
round trip at all — the cheapest possible reject, satisfying "reject as
early and as cheaply as possible." It applies to every backend alike —
the kill switch is not a monetary control.

The Anthropic *monetary* budget itself, by contrast, is scoped to the
Anthropic backend only (budget-correction addendum, feature
002-add-ollama-provider): the caller passes in `llm_provider_name`, the
already-selected backend identity threaded down from the composition
boundary (never branched on here based on anything but that one string),
and a non-Anthropic backend skips the count query entirely and is always
`allowed=True` at this stage — Anthropic exhaustion must never block a
backend that costs nothing to run. This keeps the branching in
infrastructure policy, not in `domain/`/`application/ask_question.py`.

Fail-closed: if the budget query itself raises (DB unavailable/error),
this returns `allowed=False` rather than letting the exception propagate
— an application that cannot verify it is under budget must assume it
might not be (Principle X, FR-045). This only applies to the Anthropic
path, since that's the only path that ever queries the database.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shiruno.infra.logging import get_logger
from shiruno.persistence.models import ProviderKind, ProviderName, UsageRecord

logger = get_logger(__name__)

_BUDGET_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class BudgetCheckResult:
    allowed: bool


def check_llm_budget(
    session: Session,
    *,
    llm_enabled: bool,
    llm_provider_name: str,
    max_requests_per_hour: int,
    now: datetime | None = None,
) -> BudgetCheckResult:
    if not llm_enabled:
        return BudgetCheckResult(allowed=False)

    if ProviderName(llm_provider_name) != ProviderName.anthropic:
        return BudgetCheckResult(allowed=True)

    current_time = now or datetime.now(UTC)
    window_start = current_time - _BUDGET_WINDOW
    try:
        count = session.execute(
            select(func.count())
            .select_from(UsageRecord)
            .where(UsageRecord.provider_kind == ProviderKind.llm)
            .where(UsageRecord.provider_name == ProviderName.anthropic)
            .where(UsageRecord.created_at >= window_start)
        ).scalar_one()
    except Exception:
        logger.exception("LLM budget check failed; failing closed")
        return BudgetCheckResult(allowed=False)

    return BudgetCheckResult(allowed=count < max_requests_per_hour)
