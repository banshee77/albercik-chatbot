"""Unit tests for the LLM budget check + kill switch (T055; research.md
§3, FR-045; Design Constraint 3). Uses the real `db_session` fixture for
the cases that need real `usage_records` rows; the DB-failure case uses a
stub session so it needs no database at all.

Extended by feature 002-add-ollama-provider (T008): the budget query now
filters on `provider_name='anthropic'` in addition to `provider_kind='llm'`
(data-model.md), so local-model (`provider_name='ollama'`) usage — even
`llm`-kind rows — must never count toward the Anthropic budget, exactly
like `embedding`-kind rows already didn't.

Further extended by the budget-behavior correction (feature
002-add-ollama-provider, post-US2): the Anthropic monetary budget must
apply *only* when the currently selected backend (`llm_provider_name`,
passed in by the caller — never inferred here from anything but that one
string) is Anthropic. A non-Anthropic backend now skips the count query
entirely and is unconditionally `allowed=True` at this stage, regardless
of how exhausted the Anthropic budget is — the kill switch (`llm_enabled`)
remains the only check that still applies to every backend alike.
"""

import uuid
from datetime import UTC, datetime

from shiruno.infra.budget import check_llm_budget
from shiruno.persistence.models import ProviderKind, ProviderName, UsageRecord


class _RaisingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated database failure")


def _add_usage_row(
    db_session,
    *,
    provider_kind: ProviderKind,
    provider_name: ProviderName,
    provider_model: str,
) -> None:
    db_session.add(
        UsageRecord(
            request_id=uuid.uuid4(),
            provider_kind=provider_kind,
            provider_name=provider_name,
            provider_model=provider_model,
            input_tokens=10 if provider_kind == ProviderKind.llm else None,
            output_tokens=5 if provider_kind == ProviderKind.llm else None,
            success=True,
            latency_ms=100,
        )
    )


def test_kill_switch_off_blocks_regardless_of_usage(db_session) -> None:
    result = check_llm_budget(
        db_session,
        llm_enabled=False,
        llm_provider_name="anthropic",
        max_requests_per_hour=200,
        now=datetime.now(UTC),
    )
    assert result.allowed is False


def test_allowed_when_under_the_configured_limit(db_session) -> None:
    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=200,
        now=datetime.now(UTC),
    )
    assert result.allowed is True


def test_blocked_once_the_hourly_llm_limit_is_reached(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(3):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.anthropic,
            provider_model="claude-sonnet-4-5",
        )
    db_session.flush()

    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=3,
        now=now,
    )
    assert result.allowed is False


def test_embedding_usage_never_counts_toward_the_llm_budget(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(50):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.embedding,
            provider_name=ProviderName.local_sentence_transformer,
            provider_model="intfloat/multilingual-e5-small",
        )
    db_session.flush()

    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=3,
        now=now,
    )
    assert result.allowed is True


def test_ollama_llm_usage_never_counts_toward_the_anthropic_budget(db_session) -> None:
    """The critical case this feature adds: an `llm`-kind row alone is no
    longer sufficient to count toward the Anthropic budget — it must also
    be `provider_name='anthropic'`. A large volume of Ollama-served `llm`
    rows must not exhaust it, even when the caller is still asking on
    behalf of the Anthropic backend."""
    now = datetime.now(UTC)
    for _ in range(50):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.ollama,
            provider_model="qwen3:4b",
        )
    db_session.flush()

    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=3,
        now=now,
    )
    assert result.allowed is True


def test_mixed_anthropic_and_ollama_usage_only_counts_anthropic_rows(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(2):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.anthropic,
            provider_model="claude-sonnet-4-5",
        )
    for _ in range(100):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.ollama,
            provider_model="qwen3:4b",
        )
    db_session.flush()

    # 2 real Anthropic rows, well under a limit of 3 — still allowed,
    # regardless of the 100 Ollama rows sitting alongside them.
    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=3,
        now=now,
    )
    assert result.allowed is True

    # Tightening the limit to 2 blocks it — proving the 2 Anthropic rows
    # really are being counted (not silently ignored too).
    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=2,
        now=now,
    )
    assert result.allowed is False


def test_fails_closed_when_the_budget_query_itself_raises() -> None:
    result = check_llm_budget(
        _RaisingSession(),  # type: ignore[arg-type]
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=200,
        now=datetime.now(UTC),
    )
    assert result.allowed is False


# --- Budget-behavior correction: Anthropic monetary budget applies only
# when the selected backend is Anthropic (post-US2 addendum) ---


def test_exhausted_anthropic_budget_blocks_the_anthropic_backend(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(3):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.anthropic,
            provider_model="claude-sonnet-4-5",
        )
    db_session.flush()

    result = check_llm_budget(
        db_session,
        llm_enabled=True,
        llm_provider_name="anthropic",
        max_requests_per_hour=3,
        now=now,
    )
    assert result.allowed is False


def test_exhausted_anthropic_budget_does_not_block_the_ollama_backend(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(3):
        _add_usage_row(
            db_session,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.anthropic,
            provider_model="claude-sonnet-4-5",
        )
    db_session.flush()

    # Same exhausted Anthropic usage, same tight limit — only the selected
    # backend differs, and that alone must be the difference between
    # blocked and allowed.
    result = check_llm_budget(
        db_session, llm_enabled=True, llm_provider_name="ollama", max_requests_per_hour=3, now=now
    )
    assert result.allowed is True


def test_ollama_backend_skips_the_budget_query_entirely_no_database_access(db_session) -> None:
    # A stub session that raises on `execute` proves the Ollama path
    # genuinely never queries the database at all — it isn't merely
    # "allowed because the query happens to return a low count."
    result = check_llm_budget(
        _RaisingSession(),  # type: ignore[arg-type]
        llm_enabled=True,
        llm_provider_name="ollama",
        max_requests_per_hour=3,
    )
    assert result.allowed is True


def test_kill_switch_still_blocks_the_ollama_backend(db_session) -> None:
    # The kill switch is not a monetary control — it must keep applying to
    # every backend alike, including one exempt from the Anthropic budget.
    result = check_llm_budget(
        db_session, llm_enabled=False, llm_provider_name="ollama", max_requests_per_hour=200
    )
    assert result.allowed is False
