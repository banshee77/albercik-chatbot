"""Unit tests for the LLM budget check + kill switch (T055; research.md
§3, FR-045; Design Constraint 3). Uses the real `db_session` fixture for
the cases that need real `usage_records` rows; the DB-failure case uses a
stub session so it needs no database at all.
"""

import uuid
from datetime import UTC, datetime

from albercik_chatbot.infra.budget import check_llm_budget
from albercik_chatbot.persistence.models import ProviderKind, UsageRecord


class _RaisingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated database failure")


def test_kill_switch_off_blocks_regardless_of_usage(db_session) -> None:
    result = check_llm_budget(
        db_session, llm_enabled=False, max_requests_per_hour=200, now=datetime.now(UTC)
    )
    assert result.allowed is False


def test_allowed_when_under_the_configured_limit(db_session) -> None:
    result = check_llm_budget(
        db_session, llm_enabled=True, max_requests_per_hour=200, now=datetime.now(UTC)
    )
    assert result.allowed is True


def test_blocked_once_the_hourly_llm_limit_is_reached(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(3):
        db_session.add(
            UsageRecord(
                request_id=uuid.uuid4(),
                provider_kind=ProviderKind.llm,
                provider_model="claude-sonnet-4-5",
                input_tokens=10,
                output_tokens=5,
                success=True,
                latency_ms=100,
            )
        )
    db_session.flush()

    result = check_llm_budget(db_session, llm_enabled=True, max_requests_per_hour=3, now=now)
    assert result.allowed is False


def test_embedding_usage_never_counts_toward_the_llm_budget(db_session) -> None:
    now = datetime.now(UTC)
    for _ in range(50):
        db_session.add(
            UsageRecord(
                request_id=uuid.uuid4(),
                provider_kind=ProviderKind.embedding,
                provider_model="intfloat/multilingual-e5-small",
                input_tokens=None,
                output_tokens=None,
                success=True,
                latency_ms=5,
            )
        )
    db_session.flush()

    result = check_llm_budget(db_session, llm_enabled=True, max_requests_per_hour=3, now=now)
    assert result.allowed is True


def test_fails_closed_when_the_budget_query_itself_raises() -> None:
    result = check_llm_budget(
        _RaisingSession(),  # type: ignore[arg-type]
        llm_enabled=True,
        max_requests_per_hour=200,
        now=datetime.now(UTC),
    )
    assert result.allowed is False
