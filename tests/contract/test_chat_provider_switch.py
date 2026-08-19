"""T015 (US2) — contract tests: switching `LLM_PROVIDER` between `ollama`
and `anthropic` requires configuration only (spec Acceptance Scenario
US2.1, FR-004), and both backends produce identical public response shape
and outcome semantics for equivalent provider behavior — grounded,
insufficient_information, out_of_scope, and unavailable (requirement 2).

No test here requires a real Ollama process or a real Anthropic API key
(testing constraint 8): every request is served by the same injected
`FakeLLMProvider`/`FakeEmbeddingProvider` regardless of which backend name
is configured — what changes between configurations is `LLM_PROVIDER`
alone, proving the switch needs no code change (application/ask_question.py,
domain/*, and the public request schema are all untouched by this feature).
"""

import uuid

import pytest
from sqlalchemy import select

from shiruno.config import get_settings
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    ProviderKind,
    ProviderName,
    Tenant,
    UsageRecord,
)
from shiruno.providers.llm.protocol import LLMResult
from tests.fixtures.provider_app import build_app, client_for

_QUESTION = "Jakie są godziny otwarcia biura Albertos?"
_ANSWER_CONTENT = "Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17."


def _seed_document_with_chunk(db_session, *, filename: str, content: str, embedding: list[float]):
    tenant = Tenant(name=f"Tenant {uuid.uuid4()}", slug=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    db_session.flush()
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
        DocumentChunk(document_id=document.id, position=0, content=content, embedding=embedding)
    )
    db_session.flush()
    return document


@pytest.mark.parametrize(
    ("llm_provider_env", "expected_provider_name"),
    [("ollama", ProviderName.ollama), ("anthropic", ProviderName.anthropic)],
)
@pytest.mark.asyncio
async def test_switching_backend_is_configuration_only(
    llm_provider_env,
    expected_provider_name,
    db_session,
    fake_llm_provider,
    fake_embedding_provider,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", llm_provider_env)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    expected_model = (
        get_settings().OLLAMA_MODEL
        if llm_provider_env == "ollama"
        else get_settings().ANTHROPIC_MODEL
    )
    # A real backend echoes back the model it actually used — reflected
    # here rather than the fake's unrelated default, so the assertion below
    # exercises the same field a real deployment would populate.
    fake_llm_provider.response = LLMResult(
        answer=_ANSWER_CONTENT,
        supported=True,
        model=expected_model,
        input_tokens=20,
        output_tokens=12,
        latency_ms=7,
    )

    _seed_document_with_chunk(
        db_session,
        filename="godziny.txt",
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
    assert response.json()["outcome"] == "grounded"
    assert fake_llm_provider.call_count == 1

    llm_rows = (
        db_session.execute(select(UsageRecord).where(UsageRecord.provider_kind == ProviderKind.llm))
        .scalars()
        .all()
    )
    assert len(llm_rows) == 1
    assert llm_rows[0].provider_name == expected_provider_name
    assert llm_rows[0].provider_model == expected_model


@pytest.mark.asyncio
async def test_response_shape_is_identical_across_backends(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    """Requirement 2: no provider-specific response schema — the same
    `outcome`/`answer`/`sources` shape regardless of which backend
    answered."""
    bodies: dict[str, dict] = {}
    for llm_provider_env in ("ollama", "anthropic"):
        monkeypatch.setenv("LLM_PROVIDER", llm_provider_env)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        get_settings.cache_clear()

        _seed_document_with_chunk(
            db_session,
            filename=f"godziny-{llm_provider_env}.txt",
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
        bodies[llm_provider_env] = response.json()

    get_settings.cache_clear()

    assert (
        set(bodies["ollama"].keys())
        == set(bodies["anthropic"].keys())
        == {
            "outcome",
            "answer",
            "sources",
            "request_id",
        }
    )
    assert bodies["ollama"]["outcome"] == bodies["anthropic"]["outcome"] == "grounded"


@pytest.mark.parametrize("llm_provider_env", ["ollama", "anthropic"])
@pytest.mark.asyncio
async def test_outcome_parity_grounded_insufficient_out_of_scope_unavailable(
    llm_provider_env, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    """Requirement 2: all four public outcomes behave identically —
    same HTTP status, same `outcome` value — regardless of active backend."""
    monkeypatch.setenv("LLM_PROVIDER", llm_provider_env)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()

    # grounded
    _seed_document_with_chunk(
        db_session,
        filename="godziny.txt",
        content=_ANSWER_CONTENT,
        embedding=fake_embedding_provider.embed_query(_QUESTION),
    )
    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        grounded_response = await client.post("/api/v1/chat", json={"question": _QUESTION})

        # insufficient_information — a question nothing in the (fresh)
        # seeded content supports.
        insufficient_response = await client.post(
            "/api/v1/chat", json={"question": "Jaka jest polityka zwrotów w Albertos?"}
        )

        # out_of_scope — matches an existing deny-list pattern.
        out_of_scope_response = await client.post(
            "/api/v1/chat", json={"question": "Napisz mi krótki wiersz o wiośnie."}
        )

    # unavailable — kill switch, cheapest deterministic way to force it.
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()
    app_killed = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app_killed) as client:
        unavailable_response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert grounded_response.status_code == 200
    assert grounded_response.json()["outcome"] == "grounded"

    assert insufficient_response.status_code == 200
    assert insufficient_response.json()["outcome"] == "insufficient_information"

    assert out_of_scope_response.status_code == 200
    assert out_of_scope_response.json()["outcome"] == "out_of_scope"

    assert unavailable_response.status_code == 503
    assert unavailable_response.json()["outcome"] == "unavailable"
