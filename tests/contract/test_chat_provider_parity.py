"""T016 (US2) — contract tests: rate limiting, the `LLM_ENABLED` kill
switch, the concurrency guard, prompt injection, question/request-size
limits, the context-size cap, output-token forwarding, and provider-failure
mapping all behave identically under `LLM_PROVIDER=ollama` and
`LLM_PROVIDER=anthropic` (spec Acceptance Scenario US2.2, FR-009;
requirement 3, 6, 7). Every test here builds its own app per backend via
`tests/fixtures/provider_app.py` (mirrors T015's pattern) since these
controls must be proven under an *explicitly configured* backend, not just
whatever the ambient default happens to be.

Design Constraint 2 holds throughout: `fake_llm_provider`/
`fake_embedding_provider` back both configurations — no real Ollama
process, no real Anthropic API key, ever required.
"""

import uuid

import pytest

from shiruno.config import get_settings
from shiruno.domain.prompting import SYSTEM_PROMPT
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    Tenant,
)
from shiruno.providers.llm.protocol import LLMProviderError
from tests.fixtures.prompt_injection import VISITOR_INJECTION_MESSAGES
from tests.fixtures.provider_app import build_app, client_for

_QUESTION = "Jakie są godziny otwarcia biura Albertos?"
_ANSWER_CONTENT = "Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17."
_SECRET_MARKERS = (
    "ANTHROPIC_API_KEY",
    "AUTH_JWT_SECRET",
    "DATABASE_URL",
    "sk-ant",
    "11434",
    "OLLAMA_BASE_URL",
    "ollama:11434",
)
_BACKENDS = ["ollama", "anthropic"]


def _seed_document_with_chunk(db_session, *, content: str, embedding: list[float]):
    tenant = Tenant(name=f"Tenant {uuid.uuid4()}", slug=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    db_session.flush()
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="godziny.txt",
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


def _configure_backend(monkeypatch, llm_provider_env: str) -> None:
    monkeypatch.setenv("LLM_PROVIDER", llm_provider_env)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_rate_limit_parity(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "1")
    get_settings.cache_clear()

    _seed_document_with_chunk(
        db_session,
        content=_ANSWER_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        first = await client.post("/api/v1/chat", json={"question": _QUESTION})
        assert first.status_code == 200

        llm_calls_before = fake_llm_provider.call_count
        second = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert second.status_code == 429
    assert "retry-after" in {k.lower() for k in second.headers.keys()}
    assert fake_llm_provider.call_count == llm_calls_before


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_kill_switch_parity(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0
    serialized = str(body)
    for leaked in _SECRET_MARKERS:
        assert leaked not in serialized


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_concurrency_guard_parity(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    guard = ChatConcurrencyGuard(limit=1)
    app.state.chat_concurrency_guard = guard
    guard._semaphore.acquire()  # simulates an already in-flight paid LLM call
    try:
        async with client_for(app) as client:
            response = await client.post("/api/v1/chat", json={"question": _QUESTION})
    finally:
        guard._semaphore.release()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.parametrize("message", VISITOR_INJECTION_MESSAGES[:3])
@pytest.mark.asyncio
async def test_prompt_injection_parity(
    llm_provider_env, message, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": message})

    get_settings.cache_clear()

    assert response.status_code in (200, 400)
    body = response.text
    for marker in _SECRET_MARKERS:
        assert marker not in body
    assert SYSTEM_PROMPT not in body
    if response.status_code == 200:
        assert response.json()["outcome"] in (
            "insufficient_information",
            "out_of_scope",
            "grounded",
        )


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_question_and_request_size_limit_parity(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)
    limit = get_settings().MAX_QUESTION_LENGTH_CHARS

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        over_length = await client.post("/api/v1/chat", json={"question": "a" * (limit + 1)})

    monkeypatch.setenv("MAX_CHAT_REQUEST_BODY_BYTES", "50")
    get_settings.cache_clear()

    app_tight_body = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app_tight_body) as client:
        oversized_body = await client.post(
            "/api/v1/chat",
            json={"question": "Jakie są godziny otwarcia biura Albertos w tym miesiącu?"},
        )

    get_settings.cache_clear()

    assert over_length.status_code == 400
    assert fake_llm_provider.call_count == 0
    assert oversized_body.status_code == 413
    assert fake_llm_provider.call_count == 0


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_context_size_limit_parity(
    llm_provider_env,
    db_session,
    default_tenant,
    fake_llm_provider,
    fake_embedding_provider,
    monkeypatch,
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)
    monkeypatch.setenv("MAX_CONTEXT_CHARS", "80")
    monkeypatch.setenv("RETRIEVAL_RELEVANCE_THRESHOLD", "0.0")
    get_settings.cache_clear()

    # Two chunks, most-relevant first (exact embedding match) — the second,
    # lower-similarity chunk would push total content past the 80-char cap,
    # so it must be dropped (domain/retrieval.py's limit_context_chars),
    # identically regardless of active backend, with no crash and no leaked
    # internal detail.
    admin = Administrator(
        username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=default_tenant.id
    )
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="godziny.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=default_tenant.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            position=0,
            content=_ANSWER_CONTENT,
            embedding=fake_embedding_provider.embed_query(_QUESTION),
        )
    )
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            position=1,
            content="TRESC_DRUGIEGO_FRAGMENTU_PONIZEJ_PROGU_KONTEKSTU",
            embedding=fake_embedding_provider.embed_query(_QUESTION + " unrelated second chunk"),
        )
    )
    db_session.flush()

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["outcome"] == "grounded"
    assert fake_llm_provider.call_count == 1
    sent_message = fake_llm_provider.calls[0]["user_message"]
    assert _ANSWER_CONTENT in sent_message
    assert "TRESC_DRUGIEGO_FRAGMENTU_PONIZEJ_PROGU_KONTEKSTU" not in sent_message


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_max_output_tokens_forwarding_parity(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)
    settings = get_settings()

    _seed_document_with_chunk(
        db_session,
        content=_ANSWER_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert response.status_code == 200
    assert fake_llm_provider.calls[0]["max_tokens"] == settings.LLM_MAX_ANSWER_TOKENS


@pytest.mark.parametrize("llm_provider_env", _BACKENDS)
@pytest.mark.asyncio
async def test_provider_failure_mapping_parity(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    _configure_backend(monkeypatch, llm_provider_env)
    fake_llm_provider.error = LLMProviderError(
        "simulated post-retry provider failure — must never reach the client"
    )

    _seed_document_with_chunk(
        db_session,
        content=_ANSWER_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 1
    serialized = str(body)
    assert "simulated post-retry provider failure" not in serialized
    for leaked in _SECRET_MARKERS:
        assert leaked not in serialized
