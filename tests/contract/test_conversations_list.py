"""T017 — contract test: `GET /api/v1/admin/conversations` (feature
011-conversations-analytics, US1, FR-017-FR-020). Newest-first ordering,
outcome/date/search filters, bounded pagination, tenant scoping.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from shiruno.persistence.models import ConversationOutcome, ConversationRecord
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


def _seed_conversation(
    db_session,
    tenant,
    *,
    question: str,
    outcome: ConversationOutcome = ConversationOutcome.grounded,
    created_at: datetime | None = None,
    latency_ms: int = 100,
) -> ConversationRecord:
    record = ConversationRecord(
        tenant_id=tenant.id,
        request_id=uuid.uuid4(),
        question=question,
        normalized_question=question.lower(),
        outcome=outcome,
        answer="Odpowiedź testowa.",
        latency_ms=latency_ms,
    )
    db_session.add(record)
    db_session.flush()
    if created_at is not None:
        db_session.execute(
            update(ConversationRecord)
            .where(ConversationRecord.id == record.id)
            .values(created_at=created_at)
        )
        db_session.flush()
        db_session.refresh(record)
    return record


@pytest.mark.asyncio
async def test_zero_conversations_returns_valid_empty_result(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        "/api/v1/admin/conversations", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.asyncio
async def test_list_is_newest_first(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    now = datetime.now(UTC)
    oldest = _seed_conversation(
        db_session, default_tenant, question="Pytanie 1", created_at=now - timedelta(minutes=10)
    )
    middle = _seed_conversation(
        db_session, default_tenant, question="Pytanie 2", created_at=now - timedelta(minutes=5)
    )
    newest = _seed_conversation(db_session, default_tenant, question="Pytanie 3", created_at=now)

    response = await db_async_client.get(
        "/api/v1/admin/conversations", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [str(newest.id), str(middle.id), str(oldest.id)]


@pytest.mark.asyncio
async def test_outcome_filter_narrows_results(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    grounded = _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie grounded",
        outcome=ConversationOutcome.grounded,
    )
    _seed_conversation(
        db_session,
        default_tenant,
        question="Pytanie small talk",
        outcome=ConversationOutcome.small_talk,
    )

    response = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"outcome": "grounded"},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [str(grounded.id)]


@pytest.mark.asyncio
async def test_date_range_filter_narrows_results(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    now = datetime.now(UTC)
    old = _seed_conversation(
        db_session, default_tenant, question="Stare pytanie", created_at=now - timedelta(days=40)
    )
    recent = _seed_conversation(
        db_session, default_tenant, question="Nowe pytanie", created_at=now - timedelta(days=1)
    )

    response = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"start_date": (now - timedelta(days=10)).isoformat()},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    ids = [item["id"] for item in items]
    assert str(recent.id) in ids
    assert str(old.id) not in ids


@pytest.mark.asyncio
async def test_question_search_narrows_results(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    matching = _seed_conversation(db_session, default_tenant, question="Jakie są godziny otwarcia?")
    _seed_conversation(db_session, default_tenant, question="Jaka jest polityka zwrotów?")

    response = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"q": "godziny"},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [str(matching.id)]


@pytest.mark.asyncio
async def test_search_with_no_matches_returns_empty_result(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    _seed_conversation(db_session, default_tenant, question="Jakie są godziny otwarcia?")

    response = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"q": "zupelnie-inny-tekst"},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_requesting_more_than_max_page_size_is_clamped_not_rejected(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    for i in range(3):
        _seed_conversation(db_session, default_tenant, question=f"Pytanie {i}")

    response = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"limit": 100000},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 100
    assert len(body["items"]) <= 100


@pytest.mark.asyncio
async def test_pagination_is_complete_and_non_duplicated(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    now = datetime.now(UTC)
    seeded_ids = []
    for i in range(5):
        record = _seed_conversation(
            db_session,
            default_tenant,
            question=f"Pytanie {i}",
            created_at=now - timedelta(minutes=i),
        )
        seeded_ids.append(str(record.id))

    page1 = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"limit": 2, "offset": 0},
        headers={"authorization": f"Bearer {token}"},
    )
    page2 = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"limit": 2, "offset": 2},
        headers={"authorization": f"Bearer {token}"},
    )
    page3 = await db_async_client.get(
        "/api/v1/admin/conversations",
        params={"limit": 2, "offset": 4},
        headers={"authorization": f"Bearer {token}"},
    )

    all_ids = [item["id"] for page in (page1, page2, page3) for item in page.json()["items"]]
    assert len(all_ids) == 5
    assert len(set(all_ids)) == 5
    assert set(all_ids) == set(seeded_ids)
    assert page1.json()["total"] == 5


@pytest.mark.asyncio
async def test_only_own_tenants_conversations_are_returned(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    own_token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="own")
    own = _seed_conversation(db_session, default_tenant, question="Pytanie wlasne")
    _seed_conversation(db_session, other_tenant, question="Pytanie innego tenanta")

    response = await db_async_client.get(
        "/api/v1/admin/conversations", headers={"authorization": f"Bearer {own_token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [str(own.id)]
