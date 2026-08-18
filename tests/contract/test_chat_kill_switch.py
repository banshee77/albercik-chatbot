"""T058 — contract test: `LLM_ENABLED=false` on `POST /api/v1/chat` (US3.3,
US3.7, FR-043). No LLM provider call, a safe generic `unavailable` outcome
mapped to HTTP 503, no internal configuration leaked in the response body,
identically for a Public User and an authenticated Administrator.
"""

import pytest

from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.security import hash_password, issue_access_token
from albercik_chatbot.persistence.models import Administrator


@pytest.mark.asyncio
async def test_kill_switch_off_returns_unavailable_without_any_provider_call(
    db_async_client, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert fake_embedding_provider.embed_calls == []
    assert fake_llm_provider.call_count == 0

    serialized = str(body)
    for leaked in ("ANTHROPIC_API_KEY", "AUTH_JWT_SECRET", "DATABASE_URL", "sk-ant"):
        assert leaked not in serialized


@pytest.mark.asyncio
async def test_kill_switch_off_applies_identically_to_an_authenticated_administrator(
    db_async_client, db_session, fake_llm_provider, monkeypatch
) -> None:
    settings = get_settings()
    admin = Administrator(username="ks-admin", password_hash=hash_password("irrelevant"))
    db_session.add(admin)
    db_session.flush()
    token = issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=settings.AUTH_JWT_EXPIRE_MINUTES,
    ).access_token

    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat",
        json={"question": "Jakie są godziny otwarcia biura Albertos?"},
        headers={"authorization": f"Bearer {token}"},
    )

    get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0
