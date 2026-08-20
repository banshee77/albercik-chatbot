"""T029 — contract test: `GET /api/v1/admin/analytics/knowledge-gaps`
(feature 011-conversations-analytics, US4, FR-027-FR-029). Case/whitespace
variants group together; ranked by frequency; only `insufficient_information`
contributes; empty range/no matches returns a valid empty result.
"""

import uuid

import pytest

from shiruno.domain.question_normalization import normalize_question
from shiruno.persistence.models import ConversationOutcome, ConversationRecord
from tests.fixtures.admin import seed_admin_and_token


def _seed_conversation(db_session, tenant, *, question: str, **overrides) -> ConversationRecord:
    defaults = dict(
        tenant_id=tenant.id,
        request_id=uuid.uuid4(),
        question=question,
        normalized_question=normalize_question(question),
        outcome=ConversationOutcome.insufficient_information,
        answer="Nie mam wystarczających informacji.",
        latency_ms=200,
    )
    defaults.update(overrides)
    record = ConversationRecord(**defaults)
    db_session.add(record)
    db_session.flush()
    return record


@pytest.mark.asyncio
async def test_zero_matches_returns_valid_empty_result(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        "/api/v1/admin/analytics/knowledge-gaps", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_case_and_whitespace_variants_group_together(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    _seed_conversation(db_session, default_tenant, question="Jakie są ceny karnetu?")
    _seed_conversation(db_session, default_tenant, question="jakie   są ceny karnetu?")
    _seed_conversation(db_session, default_tenant, question="JAKIE SĄ CENY KARNETU?")

    response = await db_async_client.get(
        "/api/v1/admin/analytics/knowledge-gaps", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["count"] == 3


@pytest.mark.asyncio
async def test_ranked_by_frequency_descending(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    for _ in range(3):
        _seed_conversation(db_session, default_tenant, question="Popularne pytanie")
    _seed_conversation(db_session, default_tenant, question="Rzadkie pytanie")

    response = await db_async_client.get(
        "/api/v1/admin/analytics/knowledge-gaps", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["count"] == 3
    assert items[0]["example_question"] == "Popularne pytanie"


@pytest.mark.asyncio
async def test_only_insufficient_information_contributes(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie grounded",
        outcome=ConversationOutcome.grounded,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie out of scope",
        outcome=ConversationOutcome.out_of_scope,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie small talk",
        outcome=ConversationOutcome.small_talk,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie unavailable",
        outcome=ConversationOutcome.unavailable,
    )
    gap = _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie insufficient",
        outcome=ConversationOutcome.insufficient_information,
    )

    response = await db_async_client.get(
        "/api/v1/admin/analytics/knowledge-gaps", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["normalized_question"] == gap.normalized_question
