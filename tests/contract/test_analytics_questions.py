"""T032 — contract test: `GET /api/v1/admin/analytics/questions` (feature
011-conversations-analytics, US5, FR-030). Same grouping/ranking mechanics
as knowledge-gaps, but across all outcomes; deterministic; same default
date-range behavior.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from shiruno.domain.question_normalization import normalize_question
from shiruno.persistence.models import ConversationOutcome, ConversationRecord
from tests.fixtures.admin import seed_admin_and_token


def _seed_conversation(db_session, tenant, *, question: str, **overrides) -> ConversationRecord:
    defaults = dict(
        tenant_id=tenant.id,
        request_id=uuid.uuid4(),
        question=question,
        normalized_question=normalize_question(question),
        outcome=ConversationOutcome.grounded,
        answer="Odpowiedź.",
        latency_ms=200,
    )
    defaults.update(overrides)
    record = ConversationRecord(**defaults)
    db_session.add(record)
    db_session.flush()
    return record


@pytest.mark.asyncio
async def test_all_outcomes_contribute(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    _seed_conversation(
        db_session,
        default_tenant,
        question="Popularne pytanie",
        outcome=ConversationOutcome.grounded,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        question="Popularne pytanie",
        outcome=ConversationOutcome.insufficient_information,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        question="Popularne pytanie",
        outcome=ConversationOutcome.small_talk,
    )

    response = await db_async_client.get(
        "/api/v1/admin/analytics/questions", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["count"] == 3


@pytest.mark.asyncio
async def test_ranked_by_frequency_descending(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    for _ in range(3):
        _seed_conversation(db_session, default_tenant, question="Czeste pytanie")
    _seed_conversation(db_session, default_tenant, question="Rzadkie pytanie")

    response = await db_async_client.get(
        "/api/v1/admin/analytics/questions", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["count"] == 3
    assert items[0]["example_question"] == "Czeste pytanie"


@pytest.mark.asyncio
async def test_default_range_matches_other_analytics_endpoints(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    now = datetime.now(UTC)
    old = _seed_conversation(db_session, default_tenant, question="Stare pytanie")
    db_session.execute(
        update(ConversationRecord)
        .where(ConversationRecord.id == old.id)
        .values(created_at=now - timedelta(days=40))
    )
    db_session.flush()
    _seed_conversation(db_session, default_tenant, question="Nowe pytanie")

    response = await db_async_client.get(
        "/api/v1/admin/analytics/questions", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    normalized_questions = {item["normalized_question"] for item in response.json()["items"]}
    assert "nowe pytanie" in normalized_questions
    assert "stare pytanie" not in normalized_questions
