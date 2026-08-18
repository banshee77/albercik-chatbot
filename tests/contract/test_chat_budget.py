"""T059 — contract test: configured LLM budget exhausted on
`POST /api/v1/chat` (US3.4, FR-044; Design Constraint 3). Once the hourly
LLM budget is used up, subsequent questions get `unavailable` with no
further LLM calls; heavy embedding volume alone must never exhaust it.
"""

import uuid

import pytest

from albercik_chatbot.config import get_settings
from albercik_chatbot.persistence.models import ProviderKind, UsageRecord


def _seed_usage(db_session, *, provider_kind: ProviderKind, count: int) -> None:
    for _ in range(count):
        db_session.add(
            UsageRecord(
                request_id=uuid.uuid4(),
                provider_kind=provider_kind,
                provider_model="claude-sonnet-4-5"
                if provider_kind == ProviderKind.llm
                else "intfloat/multilingual-e5-small",
                input_tokens=10 if provider_kind == ProviderKind.llm else None,
                output_tokens=5 if provider_kind == ProviderKind.llm else None,
                success=True,
                latency_ms=100,
            )
        )
    db_session.flush()


@pytest.mark.asyncio
async def test_exhausted_llm_budget_blocks_further_llm_calls(
    db_async_client, db_session, fake_llm_provider, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    get_settings.cache_clear()
    _seed_usage(db_session, provider_kind=ProviderKind.llm, count=3)

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_heavy_embedding_volume_alone_does_not_exhaust_the_llm_budget(
    db_async_client, db_session, fake_llm_provider, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "3")
    get_settings.cache_clear()
    _seed_usage(db_session, provider_kind=ProviderKind.embedding, count=500)

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["outcome"] != "unavailable"
