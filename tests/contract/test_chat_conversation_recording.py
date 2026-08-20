"""T012 — contract test: every public chat outcome produces exactly one
correctly-populated `ConversationRecord` (feature
011-conversations-analytics, research.md §3, §4, §5); a `ConversationRecord`
insert failure never turns a successful `ChatResponse` into an error, and
leaves already-flushed `UsageRecord` rows intact (only the SAVEPOINT rolls
back, never the outer transaction); a missing or inactive configured
public tenant behaves identically — normal response, no recorded row.
"""

import uuid

import pytest
from sqlalchemy import func, select

from shiruno.config import get_settings
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.persistence.models import (
    Administrator,
    ConversationRecord,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    ProviderName,
    Tenant,
    TenantStatus,
    UsageRecord,
)
from shiruno.providers.llm.protocol import LLMProviderError, LLMResult


def _seed_public_tenant(db_session, monkeypatch, *, status: TenantStatus = TenantStatus.active):
    slug = f"albertos-{uuid.uuid4()}"
    tenant = Tenant(name="Albertos", slug=slug, status=status)
    db_session.add(tenant)
    db_session.flush()
    monkeypatch.setenv("PUBLIC_CHAT_TENANT_SLUG", slug)
    get_settings.cache_clear()
    return tenant


def _seed_matching_chunk(db_session, tenant, *, content: str, embedding: list[float]) -> None:
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="seed.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=tenant.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(document_id=document.id, position=0, content=content, embedding=embedding)
    )
    db_session.flush()


def _get_conversation_record(db_session, request_id: uuid.UUID):
    return db_session.execute(
        select(ConversationRecord).where(ConversationRecord.request_id == request_id)
    ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_grounded_conversation_is_recorded_correctly(
    db_async_client, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    question = "Jakie są godziny otwarcia biura Albertos?"
    _seed_matching_chunk(
        db_session,
        tenant,
        content="Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17.",
        embedding=fake_embedding_provider.embed_query(question),
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.tenant_id == tenant.id
    assert record.question == question
    assert record.normalized_question == question.lower()
    assert record.answer == body["answer"]
    assert record.sources == [
        {"document_id": s["document_id"], "label": s["label"]} for s in body["sources"]
    ]
    assert record.safe_failure_category is None
    assert record.provider_name == ProviderName.ollama
    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.latency_ms >= 0


@pytest.mark.asyncio
async def test_insufficient_information_zero_chunk_is_recorded_correctly(
    db_async_client, db_session, monkeypatch
) -> None:
    _seed_public_tenant(db_session, monkeypatch)
    question = "Jakie są godziny otwarcia biura Albertos?"

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.sources is None
    assert record.safe_failure_category is None
    assert record.provider_name is None
    assert record.input_tokens is None
    assert record.output_tokens is None


@pytest.mark.asyncio
async def test_insufficient_information_after_real_llm_call_retains_usage(
    db_async_client, db_session, monkeypatch, fake_embedding_provider, fake_llm_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    question = "Jakie są godziny otwarcia biura Albertos?"
    _seed_matching_chunk(
        db_session,
        tenant,
        content="Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17.",
        embedding=fake_embedding_provider.embed_query(question),
    )
    fake_llm_provider.response = LLMResult(
        answer="ignored",
        supported=False,
        model="fake-llm",
        input_tokens=42,
        output_tokens=7,
        latency_ms=1,
        provider_metrics=None,
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.sources is None
    assert record.provider_name == ProviderName.ollama
    assert record.input_tokens == 42
    assert record.output_tokens == 7


@pytest.mark.asyncio
async def test_out_of_scope_is_recorded_correctly(db_async_client, db_session, monkeypatch) -> None:
    _seed_public_tenant(db_session, monkeypatch)
    question = "Napisz mi krótki wiersz o wiośnie."

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "out_of_scope"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.sources is None
    assert record.safe_failure_category is None
    assert record.provider_name is None


@pytest.mark.asyncio
async def test_small_talk_is_recorded_with_zero_llm_usage(
    db_async_client, db_session, monkeypatch
) -> None:
    _seed_public_tenant(db_session, monkeypatch)
    question = "Cześć"

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "small_talk"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.sources is None
    assert record.provider_name is None
    assert record.input_tokens is None
    assert record.output_tokens is None
    assert record.safe_failure_category is None


@pytest.mark.asyncio
async def test_unavailable_provider_error_is_recorded_correctly(
    db_async_client, db_session, monkeypatch, fake_embedding_provider, fake_llm_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    question = "Jakie są godziny otwarcia biura Albertos?"
    _seed_matching_chunk(
        db_session,
        tenant,
        content="Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17.",
        embedding=fake_embedding_provider.embed_query(question),
    )
    fake_llm_provider.error = LLMProviderError("boom")

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.safe_failure_category == "provider_error"
    assert record.provider_name == ProviderName.ollama


@pytest.mark.asyncio
async def test_unavailable_concurrency_limit_is_recorded_correctly(
    db_async_client, db_session, monkeypatch, test_app
) -> None:
    _seed_public_tenant(db_session, monkeypatch)
    exhausted_guard = ChatConcurrencyGuard(limit=1)
    exhausted_guard._semaphore.acquire(blocking=False)
    test_app.state.chat_concurrency_guard = exhausted_guard

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.safe_failure_category == "concurrency_limit"
    assert record.provider_name is None


@pytest.mark.asyncio
async def test_unavailable_kill_switch_is_recorded_correctly(
    db_async_client, db_session, monkeypatch
) -> None:
    _seed_public_tenant(db_session, monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )
    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.safe_failure_category == "kill_switch"
    assert record.provider_name is None


@pytest.mark.asyncio
async def test_unavailable_budget_exceeded_is_recorded_correctly(
    db_async_client, db_session, monkeypatch, test_app
) -> None:
    _seed_public_tenant(db_session, monkeypatch)
    test_app.state.llm_provider_name = "anthropic"
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "0")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )
    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    request_id = uuid.UUID(body["request_id"])

    record = _get_conversation_record(db_session, request_id)
    assert record is not None
    assert record.safe_failure_category == "budget_exceeded"
    assert record.provider_name is None


@pytest.mark.asyncio
async def test_recording_failure_does_not_break_the_chat_response(
    db_async_client, db_session, monkeypatch, fake_embedding_provider
) -> None:
    tenant = _seed_public_tenant(db_session, monkeypatch)
    question = "Jakie są godziny otwarcia biura Albertos?"
    _seed_matching_chunk(
        db_session,
        tenant,
        content="Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17.",
        embedding=fake_embedding_provider.embed_query(question),
    )

    def _raise(_text: str) -> str:
        raise RuntimeError("forced normalization failure")

    monkeypatch.setattr("shiruno.application.record_conversation.normalize_question", _raise)

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    assert body["answer"]
    request_id = uuid.UUID(body["request_id"])

    # Only the SAVEPOINT rolled back — no ConversationRecord — but the
    # UsageRecord rows ask_question() already flushed earlier in this same
    # request survive untouched (research.md §3).
    record = _get_conversation_record(db_session, request_id)
    assert record is None

    usage_count = db_session.execute(
        select(func.count()).select_from(UsageRecord).where(UsageRecord.request_id == request_id)
    ).scalar_one()
    assert usage_count > 0


@pytest.mark.asyncio
async def test_missing_public_tenant_does_not_break_chat_or_record_anything(
    db_async_client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("PUBLIC_CHAT_TENANT_SLUG", f"nonexistent-{uuid.uuid4()}")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    request_id = uuid.UUID(body["request_id"])

    assert _get_conversation_record(db_session, request_id) is None


@pytest.mark.asyncio
async def test_inactive_public_tenant_does_not_break_chat_or_record_anything(
    db_async_client, db_session, monkeypatch
) -> None:
    _seed_public_tenant(db_session, monkeypatch, status=TenantStatus.inactive)

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    request_id = uuid.UUID(body["request_id"])

    assert _get_conversation_record(db_session, request_id) is None
