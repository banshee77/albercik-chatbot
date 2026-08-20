"""T033 — contract test: cross-tenant isolation across all five new
capabilities (feature 011-conversations-analytics, US6, FR-034, FR-035,
FR-036). Tenant A's administrator never sees Tenant B's data via list,
detail, analytics summary, knowledge gaps, or common questions; a
client-supplied tenant identifier has no effect; a cross-tenant detail
lookup is indistinguishable from a nonexistent one.
"""

import uuid

import pytest

from shiruno.persistence.models import ConversationOutcome, ConversationRecord, ProviderName
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


def _seed_conversation(
    db_session, tenant, *, question: str = "Pytanie", **overrides
) -> ConversationRecord:
    defaults = dict(
        tenant_id=tenant.id,
        request_id=uuid.uuid4(),
        question=question,
        normalized_question=question.lower(),
        outcome=ConversationOutcome.insufficient_information,
        answer="Nie mam wystarczających informacji.",
        latency_ms=300,
        provider_name=ProviderName.ollama,
        provider_model="qwen3:8b",
        input_tokens=50,
        output_tokens=10,
    )
    defaults.update(overrides)
    record = ConversationRecord(**defaults)
    db_session.add(record)
    db_session.flush()
    return record


@pytest.mark.asyncio
async def test_tenant_a_never_sees_tenant_bs_conversations_or_analytics(
    db_async_client, db_session, default_tenant
) -> None:
    tenant_b = seed_tenant(db_session)
    token_a = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="admin-a")
    _seed_conversation(db_session, default_tenant, question="Pytanie tenanta A")
    conversation_b = _seed_conversation(db_session, tenant_b, question="Pytanie tenanta B")

    headers_a = {"authorization": f"Bearer {token_a}"}

    list_response = await db_async_client.get("/api/v1/admin/conversations", headers=headers_a)
    assert list_response.status_code == 200
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(conversation_b.id) not in ids

    detail_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{conversation_b.id}", headers=headers_a
    )
    assert detail_response.status_code == 404

    summary_response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers=headers_a
    )
    assert summary_response.status_code == 200
    assert summary_response.json()["total_requests"] == 1

    gaps_response = await db_async_client.get(
        "/api/v1/admin/analytics/knowledge-gaps", headers=headers_a
    )
    assert gaps_response.status_code == 200
    assert all(
        item["normalized_question"] != conversation_b.normalized_question
        for item in gaps_response.json()["items"]
    )

    questions_response = await db_async_client.get(
        "/api/v1/admin/analytics/questions", headers=headers_a
    )
    assert questions_response.status_code == 200
    assert all(
        item["normalized_question"] != conversation_b.normalized_question
        for item in questions_response.json()["items"]
    )


@pytest.mark.asyncio
async def test_cross_tenant_detail_lookup_matches_nonexistent_lookup(
    db_async_client, db_session, default_tenant
) -> None:
    tenant_b = seed_tenant(db_session)
    token_a = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="admin-a2")
    conversation_b = _seed_conversation(db_session, tenant_b)
    headers_a = {"authorization": f"Bearer {token_a}"}

    cross_tenant_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{conversation_b.id}", headers=headers_a
    )
    nonexistent_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{uuid.uuid4()}", headers=headers_a
    )

    assert cross_tenant_response.status_code == nonexistent_response.status_code == 404
    assert cross_tenant_response.json() == nonexistent_response.json()


@pytest.mark.asyncio
async def test_client_supplied_tenant_identifier_has_no_effect_on_new_routes(
    db_async_client, db_session, default_tenant
) -> None:
    tenant_b = seed_tenant(db_session)
    token_a = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="admin-a3")
    _seed_conversation(db_session, tenant_b, question="Pytanie tenanta B")
    headers = {"authorization": f"Bearer {token_a}", "X-Tenant-Id": str(tenant_b.id)}

    list_response = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"tenant_id": str(tenant_b.id)},
        headers=headers,
    )
    summary_response = await db_async_client.get(
        "/api/v1/admin/analytics/summary",
        params={"tenant_id": str(tenant_b.id)},
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.json()["items"] == []
    assert summary_response.status_code == 200
    assert summary_response.json()["total_requests"] == 0
