"""T021 — contract test: `GET /api/v1/admin/conversations/{id}` (feature
011-conversations-analytics, US2, FR-005, FR-006, FR-009, FR-022, FR-035).
Full detail shape; sources only for grounded; safe_failure_category only
for unavailable; 404 for nonexistent/cross-tenant (identical body);
historical-snapshot immutability (research.md §2a "Testing implication").
"""

import uuid

import pytest

from shiruno.application.delete_document import delete_document
from shiruno.persistence.models import (
    Administrator,
    ConversationOutcome,
    ConversationRecord,
    DocumentChunk,
    DocumentStatus,
    FailureCategory,
    KnowledgeDocument,
    ProviderName,
)
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


def _seed_document_with_chunk(
    db_session, tenant, *, filename: str, content: str
) -> KnowledgeDocument:
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename=filename,
        uploaded_by_admin_id=admin.id,
        tenant_id=tenant.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(document_id=document.id, position=0, content=content, embedding=[0.0] * 384)
    )
    db_session.flush()
    return document


def _seed_conversation(db_session, tenant, **overrides) -> ConversationRecord:
    defaults = dict(
        tenant_id=tenant.id,
        request_id=uuid.uuid4(),
        question="Kiedy są zajęcia dla początkujących?",
        normalized_question="kiedy sa zajecia dla poczatkujacych?",
        outcome=ConversationOutcome.grounded,
        answer="Zajęcia dla początkujących odbywają się we wtorki.",
        latency_ms=500,
    )
    defaults.update(overrides)
    record = ConversationRecord(**defaults)
    db_session.add(record)
    db_session.flush()
    return record


@pytest.mark.asyncio
async def test_grounded_detail_includes_sources(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    document = _seed_document_with_chunk(
        db_session, default_tenant, filename="treningi.txt", content="Treningi..."
    )
    record = _seed_conversation(
        db_session,
        default_tenant,
        sources=[{"document_id": str(document.id), "label": "treningi.txt"}],
        provider_name=ProviderName.ollama,
        provider_model="qwen3:8b",
        input_tokens=100,
        output_tokens=50,
    )

    response = await db_async_client.get(
        f"/api/v1/admin/conversations/{record.id}", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    assert body["sources"] == [{"document_id": str(document.id), "label": "treningi.txt"}]
    assert body["provider_name"] == "ollama"
    assert body["provider_model"] == "qwen3:8b"
    assert body["input_tokens"] == 100
    assert body["output_tokens"] == 50
    assert body["safe_failure_category"] is None


@pytest.mark.asyncio
async def test_non_grounded_detail_has_null_sources(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    record = _seed_conversation(
        db_session,
        default_tenant,
        outcome=ConversationOutcome.insufficient_information,
        sources=None,
        answer="Nie mam wystarczających informacji.",
    )

    response = await db_async_client.get(
        f"/api/v1/admin/conversations/{record.id}", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] is None


@pytest.mark.asyncio
async def test_unavailable_detail_includes_failure_category(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    record = _seed_conversation(
        db_session,
        default_tenant,
        outcome=ConversationOutcome.unavailable,
        sources=None,
        answer="Chatbot jest obecnie niedostępny.",
        safe_failure_category=FailureCategory.provider_error,
    )

    response = await db_async_client.get(
        f"/api/v1/admin/conversations/{record.id}", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["safe_failure_category"] == "provider_error"


@pytest.mark.asyncio
async def test_detail_returns_404_for_nonexistent_conversation(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        f"/api/v1/admin/conversations/{uuid.uuid4()}",
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detail_returns_404_for_foreign_tenant_conversation(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    attacker_token = seed_admin_and_token(
        db_session, tenant_id=default_tenant.id, username="attacker"
    )
    record = _seed_conversation(db_session, other_tenant)

    nonexistent_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{uuid.uuid4()}",
        headers={"authorization": f"Bearer {attacker_token}"},
    )
    cross_tenant_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{record.id}",
        headers={"authorization": f"Bearer {attacker_token}"},
    )

    assert nonexistent_response.status_code == 404
    assert cross_tenant_response.status_code == 404
    assert nonexistent_response.json() == cross_tenant_response.json()


@pytest.mark.asyncio
async def test_sources_survive_document_deletion(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    document = _seed_document_with_chunk(
        db_session, default_tenant, filename="sekcje.txt", content="Sekcje..."
    )
    record = _seed_conversation(
        db_session,
        default_tenant,
        sources=[{"document_id": str(document.id), "label": "sekcje.txt"}],
    )

    delete_document(document.id, session=db_session, tenant_id=default_tenant.id)

    # The document itself is now gone from the admin's point of view...
    detail_response = await db_async_client.get(
        f"/api/v1/documents/{document.id}", headers={"authorization": f"Bearer {token}"}
    )
    assert detail_response.status_code == 404

    # ...but the historical conversation's recorded source is untouched.
    conversation_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{record.id}", headers={"authorization": f"Bearer {token}"}
    )
    assert conversation_response.status_code == 200
    assert conversation_response.json()["sources"] == [
        {"document_id": str(document.id), "label": "sekcje.txt"}
    ]


@pytest.mark.asyncio
async def test_provider_model_snapshot_is_independent_of_current_configuration(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    ollama_record = _seed_conversation(
        db_session,
        default_tenant,
        provider_name=ProviderName.ollama,
        provider_model="qwen3:8b",
    )
    anthropic_record = _seed_conversation(
        db_session,
        default_tenant,
        provider_name=ProviderName.anthropic,
        provider_model="claude-sonnet-4-5",
    )

    ollama_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{ollama_record.id}",
        headers={"authorization": f"Bearer {token}"},
    )
    anthropic_response = await db_async_client.get(
        f"/api/v1/admin/conversations/{anthropic_record.id}",
        headers={"authorization": f"Bearer {token}"},
    )

    assert ollama_response.json()["provider_name"] == "ollama"
    assert ollama_response.json()["provider_model"] == "qwen3:8b"
    assert anthropic_response.json()["provider_name"] == "anthropic"
    assert anthropic_response.json()["provider_model"] == "claude-sonnet-4-5"
