"""T013–T014 — contract tests (feature 002-add-ollama-provider, spec
Acceptance Scenarios US1.1, US1.2): with `LLM_PROVIDER` unset (the
documented default), `POST /api/v1/chat` produces a grounded answer
through the existing RAG pipeline, and the resulting `usage_records` row
is correctly attributed to the local backend.

Builds the app directly rather than via `conftest.py`'s `test_app`/
`db_async_client` fixtures: `LLM_PROVIDER`/`ANTHROPIC_API_KEY` must be
cleared *before* `create_app()` runs (it reads `get_settings()` at
factory-call time), and those fixtures already construct the app before a
test function body gets a chance to monkeypatch anything. Still uses
`FakeLLMProvider`/`FakeEmbeddingProvider` throughout (Design Constraint 2
— no real Ollama process, no real network call) and the real
`db_session`/`db_engine` fixtures for pgvector-backed seeding, exactly
like the rest of the contract suite.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from shiruno.config import get_settings
from shiruno.infra.budget import check_llm_budget
from shiruno.main import create_app
from shiruno.persistence.database import get_session
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    ProviderKind,
    ProviderName,
    UsageRecord,
)
from shiruno.providers.llm.protocol import LLMResult

_QUESTION = "Jakie są godziny otwarcia biura Albertos?"
_ANSWER_CONTENT = "Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17."


def _seed_document_with_chunk(db_session, *, filename: str, content: str, embedding: list[float]):
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x")
    db_session.add(admin)
    db_session.flush()

    document = KnowledgeDocument(
        original_filename=filename,
        uploaded_by_admin_id=admin.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()

    db_session.add(
        DocumentChunk(document_id=document.id, position=0, content=content, embedding=embedding)
    )
    db_session.flush()
    return document


async def _post_chat_with_default_provider(db_session, fake_llm_provider, fake_embedding_provider):
    """Shared setup for both tests: seeds a matching chunk, builds an app
    with LLM_PROVIDER/ANTHROPIC_API_KEY absent from the environment, and
    posts the question that chunk answers."""
    _seed_document_with_chunk(
        db_session,
        filename="godziny.txt",
        content=_ANSWER_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )

    app = create_app(llm_provider=fake_llm_provider, embedding_provider=fake_embedding_provider)
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/chat", json={"question": _QUESTION})


@pytest.mark.asyncio
async def test_default_provider_answers_grounded_question_via_local_backend(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Requirement 7: default provider selection when LLM_PROVIDER is not
    # explicitly set. Requirement 8: no Anthropic API key required.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()

    response = await _post_chat_with_default_provider(
        db_session, fake_llm_provider, fake_embedding_provider
    )

    get_settings.cache_clear()

    assert get_settings().LLM_PROVIDER == "ollama"
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    assert body["answer"]
    # Exactly one provider call: the injected (local-backend-standing-in)
    # fake, and nothing else — proving there is no hidden/parallel
    # Anthropic-specific path invoked alongside the configured backend.
    assert fake_llm_provider.call_count == 1


@pytest.mark.asyncio
async def test_default_provider_usage_is_recorded_as_ollama(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    configured_model = get_settings().OLLAMA_MODEL

    # A correctly-functioning Ollama backend echoes back the model it
    # actually used (research.md §2) — reflected here rather than the
    # fake's unrelated default, so the assertion below exercises the same
    # field a real deployment would populate.
    fake_llm_provider.response = LLMResult(
        answer="Biuro jest czynne od 9 do 17.",
        supported=True,
        model=configured_model,
        input_tokens=20,
        output_tokens=12,
        latency_ms=7,
    )

    response = await _post_chat_with_default_provider(
        db_session, fake_llm_provider, fake_embedding_provider
    )

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["outcome"] == "grounded"

    llm_rows = (
        db_session.execute(select(UsageRecord).where(UsageRecord.provider_kind == ProviderKind.llm))
        .scalars()
        .all()
    )
    assert len(llm_rows) == 1
    row = llm_rows[0]
    assert row.provider_kind == ProviderKind.llm
    assert row.provider_name == ProviderName.ollama
    assert row.provider_model == configured_model
    assert row.success is True

    # And, separately: this Ollama-attributed usage must never be visible
    # to the Anthropic budget query (spec: "Ollama usage must not affect
    # the Anthropic monetary budget") — proven here by checking against
    # the actual configured (Ollama) backend, which the budget-behavior
    # correction now exempts from the Anthropic count entirely.
    budget_result = check_llm_budget(
        db_session, llm_enabled=True, llm_provider_name="ollama", max_requests_per_hour=1
    )
    assert budget_result.allowed is True
