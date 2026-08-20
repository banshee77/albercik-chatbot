"""T025 — contract test: `GET /api/v1/admin/analytics/summary` (feature
011-conversations-analytics, US3, FR-023-FR-026). Outcome counts/rates,
latency aggregates, token/provider breakdown, tenant scoping, zero-activity
and default-range behavior, and historical-snapshot independence from the
app's current provider configuration (research.md §2a).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from shiruno.persistence.models import ConversationOutcome, ConversationRecord, ProviderName
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


def _seed_conversation(db_session, tenant, **overrides) -> ConversationRecord:
    defaults = dict(
        tenant_id=tenant.id,
        request_id=uuid.uuid4(),
        question="Pytanie testowe",
        normalized_question="pytanie testowe",
        outcome=ConversationOutcome.grounded,
        answer="Odpowiedź testowa.",
        latency_ms=200,
    )
    defaults.update(overrides)
    record = ConversationRecord(**defaults)
    db_session.add(record)
    db_session.flush()
    return record


@pytest.mark.asyncio
async def test_zero_activity_returns_valid_zeroed_summary(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 0
    for stats in body["outcomes"].values():
        assert stats == {"count": 0, "rate": 0.0}
    assert body["latency_ms"] == {"average": None, "p50": None, "p95": None}
    assert body["tokens"] == {"input_total": 0, "output_total": 0}
    assert body["providers"] == []


@pytest.mark.asyncio
async def test_outcome_counts_and_rates_are_correct(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    for _ in range(3):
        _seed_conversation(db_session, default_tenant, outcome=ConversationOutcome.grounded)
    _seed_conversation(
        db_session, default_tenant, outcome=ConversationOutcome.insufficient_information
    )

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 4
    assert body["outcomes"]["grounded"] == {"count": 3, "rate": pytest.approx(0.75)}
    assert body["outcomes"]["insufficient_information"] == {"count": 1, "rate": pytest.approx(0.25)}
    assert body["outcomes"]["out_of_scope"] == {"count": 0, "rate": 0.0}


@pytest.mark.asyncio
async def test_small_talk_contributes_to_total_but_not_tokens_or_providers(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    _seed_conversation(
        db_session,
        default_tenant,
        outcome=ConversationOutcome.grounded,
        provider_name=ProviderName.ollama,
        provider_model="qwen3:8b",
        input_tokens=100,
        output_tokens=20,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        outcome=ConversationOutcome.small_talk,
        provider_name=None,
        provider_model=None,
        input_tokens=None,
        output_tokens=None,
    )

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_requests"] == 2
    assert body["outcomes"]["small_talk"]["count"] == 1
    assert body["tokens"] == {"input_total": 100, "output_total": 20}
    assert body["providers"] == [
        {
            "provider_name": "ollama",
            "provider_model": "qwen3:8b",
            "request_count": 1,
            "input_tokens": 100,
            "output_tokens": 20,
        }
    ]


@pytest.mark.asyncio
async def test_latency_aggregates_are_correct(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    for _ in range(3):
        _seed_conversation(db_session, default_tenant, latency_ms=200)

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    latency = response.json()["latency_ms"]
    assert latency["average"] == pytest.approx(200.0)
    assert latency["p50"] == pytest.approx(200.0)
    assert latency["p95"] == pytest.approx(200.0)


@pytest.mark.asyncio
async def test_default_range_applied_when_omitted(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    now = datetime.now(UTC)
    recent = _seed_conversation(db_session, default_tenant)
    old = _seed_conversation(db_session, default_tenant)
    db_session.execute(
        update(ConversationRecord)
        .where(ConversationRecord.id == old.id)
        .values(created_at=now - timedelta(days=40))
    )
    db_session.flush()
    db_session.refresh(recent)
    db_session.refresh(old)

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    # Default lookback is 30 days — only the recent record should count.
    assert response.json()["total_requests"] == 1


@pytest.mark.asyncio
async def test_multi_provider_summary_reflects_each_recorded_snapshot(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    _seed_conversation(
        db_session,
        default_tenant,
        provider_name=ProviderName.ollama,
        provider_model="qwen3:8b",
        input_tokens=10,
        output_tokens=5,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        provider_name=ProviderName.anthropic,
        provider_model="claude-sonnet-4-5",
        input_tokens=20,
        output_tokens=8,
    )

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    providers = {p["provider_name"]: p for p in response.json()["providers"]}
    assert providers["ollama"]["provider_model"] == "qwen3:8b"
    assert providers["anthropic"]["provider_model"] == "claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_only_own_tenants_data_is_included(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    own_token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="own")
    _seed_conversation(db_session, default_tenant)
    _seed_conversation(db_session, other_tenant)

    response = await db_async_client.get(
        "/api/v1/admin/analytics/summary", headers={"authorization": f"Bearer {own_token}"}
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 1
