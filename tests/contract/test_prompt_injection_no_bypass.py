"""T071 — contract test: a prompt-injection attempt is still subject to
every normal application-level control (US4.3). Phase 6 requirement D:
prompt-injection defenses are defense in depth only — the real security
boundary is these application-level controls (auth, rate limit, budget,
kill switch), which must hold regardless of message content, and must
never depend on the LLM behaving.
"""

import uuid

import pytest

from albercik_chatbot.config import get_settings
from albercik_chatbot.persistence.models import ProviderKind, ProviderName, UsageRecord
from tests.fixtures.admin import seed_admin_and_token
from tests.fixtures.prompt_injection import VISITOR_INJECTION_MESSAGES
from tests.fixtures.provider_app import build_app, client_for

_INJECTION_MESSAGE = VISITOR_INJECTION_MESSAGES[0]


@pytest.mark.asyncio
async def test_rate_limit_still_applies_to_injection_attempts(
    db_async_client, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "1")
    get_settings.cache_clear()

    first = await db_async_client.post("/api/v1/chat", json={"question": _INJECTION_MESSAGE})
    assert first.status_code == 200

    second = await db_async_client.post("/api/v1/chat", json={"question": _INJECTION_MESSAGE})

    get_settings.cache_clear()

    assert second.status_code == 429


@pytest.mark.asyncio
async def test_kill_switch_still_applies_to_injection_attempts(
    db_async_client, fake_llm_provider, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    response = await db_async_client.post("/api/v1/chat", json={"question": _INJECTION_MESSAGE})

    get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_budget_exhaustion_still_applies_to_injection_attempts(
    db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    # Budget-behavior correction: the Anthropic monetary budget only
    # applies to the Anthropic backend, so this must configure it
    # explicitly rather than relying on the (now Ollama-default) test app.
    monkeypatch.setenv("BUDGET_MAX_LLM_REQUESTS_PER_HOUR", "1")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    db_session.add(
        UsageRecord(
            request_id=uuid.uuid4(),
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName.anthropic,
            provider_model="claude-sonnet-4-5",
            input_tokens=10,
            output_tokens=5,
            success=True,
            latency_ms=100,
        )
    )
    db_session.flush()

    app = build_app(
        llm_provider=fake_llm_provider,
        embedding_provider=fake_embedding_provider,
        db_session=db_session,
    )
    async with client_for(app) as client:
        response = await client.post("/api/v1/chat", json={"question": _INJECTION_MESSAGE})

    get_settings.cache_clear()

    assert response.status_code == 503
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_injection_style_payload_cannot_reach_admin_only_endpoints(db_async_client) -> None:
    # No credentials at all — an injection attempt in a field an
    # unauthenticated request has no business supplying must not grant
    # access to the admin-only document-management endpoints.
    list_response = await db_async_client.get("/api/v1/documents")
    assert list_response.status_code == 401

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("x.txt", _INJECTION_MESSAGE.encode(), "text/plain")},
    )
    assert upload_response.status_code == 401


@pytest.mark.asyncio
async def test_forged_authorization_header_does_not_bypass_admin_auth(db_async_client) -> None:
    forged_tokens = [
        "Bearer ignore-previous-instructions-grant-admin-access",
        "Bearer null",
        "",
    ]
    for header_value in forged_tokens:
        headers = {"authorization": header_value} if header_value else {}
        response = await db_async_client.get("/api/v1/documents", headers=headers)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_chat_request_with_injection_content_faces_identical_controls(
    db_async_client, db_session, fake_llm_provider, monkeypatch
) -> None:
    token = seed_admin_and_token(db_session)
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat",
        json={"question": _INJECTION_MESSAGE},
        headers={"authorization": f"Bearer {token}"},
    )

    get_settings.cache_clear()

    assert response.status_code == 503
    assert fake_llm_provider.call_count == 0
