"""T059 — contract test: configured LLM budget exhausted on
`POST /api/v1/chat` (US3.4, FR-044; Design Constraint 3). Once the hourly
LLM budget is used up, subsequent questions get `unavailable` with no
further LLM calls; heavy embedding volume alone must never exhaust it.

T018 (feature 002-add-ollama-provider, US2, requirement 4) extends this
file: heavy `provider_name='ollama'` usage volume must never reduce or
exhaust the Anthropic budget either, confirmed by the same
`check_llm_budget` call that already gates real Anthropic calls (not a
separate/duplicated check).

Budget-behavior correction (post-US2): the Anthropic monetary budget now
applies *only* when the currently selected backend is Anthropic. An
exhausted Anthropic budget must never block an Ollama-configured request
— proven end-to-end here via real `/chat` calls, complementing the
narrower `infra/budget.py`-level proof in `tests/unit/test_budget.py`.
Since the default test app now defaults to `LLM_PROVIDER=ollama` (US1),
every test in this file that means to exercise the Anthropic-gated path
configures `LLM_PROVIDER=anthropic` explicitly via
`tests/fixtures/provider_app.py` rather than relying on `db_async_client`'s
ambient default.
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
from tests.fixtures.provider_app import build_app, client_for

_QUESTION = "Jakie są godziny otwarcia biura Albertos?"


def _seed_answerable_chunk(db_session, fake_embedding_provider) -> None:
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
        DocumentChunk(
            document_id=document.id,
            position=0,
            content="Biuro Albertos jest otwarte od poniedziałku do piątku.",
            embedding=fake_embedding_provider.embed_query(_QUESTION),
        )
    )
    db_session.flush()


def _seed_usage(
    db_session,
    *,
    provider_kind: ProviderKind,
    count: int,
    provider_name: ProviderName | None = None,
) -> None:
    if provider_name is None:
        provider_name = (
            ProviderName.anthropic
            if provider_kind == ProviderKind.llm
            else ProviderName.local_sentence_transformer
        )
    provider_model = {
        ProviderName.anthropic: "claude-sonnet-4-5",
        ProviderName.ollama: "qwen3:4b",
        ProviderName.local_sentence_transformer: "intfloat/multilingual-e5-small",
    }[provider_name]
    for _ in range(count):
        db_session.add(
            UsageRecord(
                request_id=uuid.uuid4(),
                provider_kind=provider_kind,
                provider_name=provider_name,
                provider_model=provider_model,
                input_tokens=10 if provider_kind == ProviderKind.llm else None,
                output_tokens=5 if provider_kind == ProviderKind.llm else None,
                success=True,
                latency_ms=100,
            )
        )
    db_session.flush()


@pytest.mark.asyncio
async def test_exhausted_llm_budget_blocks_further_llm_calls(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Regression 1: Anthropic budget exhausted + LLM_PROVIDER=anthropic ->
    # unavailable, no provider call.
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed_usage(
        db_session, provider_kind=ProviderKind.llm, count=3, provider_name=ProviderName.anthropic
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
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_heavy_embedding_volume_alone_does_not_exhaust_the_llm_budget(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed_usage(db_session, provider_kind=ProviderKind.embedding, count=500)
    _seed_answerable_chunk(db_session, fake_embedding_provider)

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["outcome"] != "unavailable"


@pytest.mark.asyncio
async def test_heavy_ollama_llm_usage_volume_does_not_exhaust_the_anthropic_budget(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Requirement 4: many local-backend requests (provider_name='ollama')
    # must never reduce or exhaust the Anthropic budget — proven by
    # actually configuring the Anthropic backend afterward and confirming
    # `check_llm_budget` (the same check that gates real Anthropic calls)
    # still allows it, despite a volume of Ollama usage rows far exceeding
    # the configured hourly cap.
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed_usage(
        db_session, provider_kind=ProviderKind.llm, count=500, provider_name=ProviderName.ollama
    )
    _seed_answerable_chunk(db_session, fake_embedding_provider)

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _QUESTION})

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["outcome"] != "unavailable"
    assert fake_llm_provider.call_count == 1

    anthropic_rows = (
        db_session.execute(
            select(UsageRecord).where(
                UsageRecord.provider_kind == ProviderKind.llm,
                UsageRecord.provider_name == ProviderName.anthropic,
            )
        )
        .scalars()
        .all()
    )
    assert len(anthropic_rows) == 1


@pytest.mark.asyncio
async def test_anthropic_budget_exhaustion_is_unaffected_by_concurrent_ollama_volume(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Companion to the test above, proving isolation cuts both ways: a
    # large volume of Ollama usage rows must not pad, dilute, or otherwise
    # change the count that determines whether the Anthropic budget is
    # exhausted — exhaustion is driven exclusively by Anthropic-attributed
    # rows.
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed_usage(
        db_session, provider_kind=ProviderKind.llm, count=3, provider_name=ProviderName.anthropic
    )
    _seed_usage(
        db_session, provider_kind=ProviderKind.llm, count=500, provider_name=ProviderName.ollama
    )

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post(
            "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
        )

    get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_exhausted_anthropic_budget_does_not_block_ollama_requests(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Regression 2 (budget-behavior correction): Anthropic budget exhausted
    # + LLM_PROVIDER=ollama -> the request continues to Ollama normally.
    # The Anthropic monetary budget is scoped to the Anthropic backend
    # only (infra/budget.py::check_llm_budget) — it must never block a
    # backend that costs nothing to run, no matter how exhausted.
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed_usage(
        db_session, provider_kind=ProviderKind.llm, count=3, provider_name=ProviderName.anthropic
    )
    _seed_answerable_chunk(db_session, fake_embedding_provider)

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

    ollama_rows = (
        db_session.execute(
            select(UsageRecord).where(
                UsageRecord.provider_kind == ProviderKind.llm,
                UsageRecord.provider_name == ProviderName.ollama,
            )
        )
        .scalars()
        .all()
    )
    assert len(ollama_rows) == 1


@pytest.mark.asyncio
async def test_kill_switch_still_blocks_ollama_even_though_anthropic_budget_is_irrelevant(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Regression 4 (non-monetary parity): the kill switch is not a
    # monetary control and must keep applying to the Ollama backend even
    # though it is now exempt from the Anthropic budget check.
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
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
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0
