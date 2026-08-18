"""T056 — contract test: rate limit exceeded on `POST /api/v1/chat` (US3.1,
FR-041). A rate-limited request must be rejected with `429` + `Retry-After`
before either provider is ever touched, identically for a Public User and
an authenticated Administrator (US3.7-style parity, requirement #11).
"""

import pytest

from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.security import hash_password, issue_access_token
from albercik_chatbot.persistence.models import Administrator


def _seed_admin_token(db_session) -> str:
    settings = get_settings()
    admin = Administrator(username="rl-admin", password_hash=hash_password("irrelevant"))
    db_session.add(admin)
    db_session.flush()
    issued = issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=settings.AUTH_JWT_EXPIRE_MINUTES,
    )
    return issued.access_token


@pytest.mark.asyncio
async def test_request_beyond_the_limit_is_rejected_before_any_provider_call(
    db_async_client, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "2")
    get_settings.cache_clear()

    for _ in range(2):
        response = await db_async_client.post(
            "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
        )
        assert response.status_code == 200

    embed_calls_before = len(fake_embedding_provider.embed_calls)
    llm_calls_before = fake_llm_provider.call_count

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    get_settings.cache_clear()

    assert response.status_code == 429
    assert "retry-after" in {k.lower() for k in response.headers.keys()}
    # The rejected request itself must not touch either provider — the two
    # earlier, *allowed* requests are expected to have called the
    # embedding provider (they legitimately proceeded through the
    # pipeline), so the assertion is "no *new* calls", not "zero calls".
    assert len(fake_embedding_provider.embed_calls) == embed_calls_before
    assert fake_llm_provider.call_count == llm_calls_before


@pytest.mark.asyncio
async def test_rate_limit_applies_identically_to_an_authenticated_administrator(
    db_async_client, db_session, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    token = _seed_admin_token(db_session)
    monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "1")
    get_settings.cache_clear()

    headers = {"authorization": f"Bearer {token}"}
    first = await db_async_client.post(
        "/api/v1/chat",
        json={"question": "Jakie są godziny otwarcia biura Albertos?"},
        headers=headers,
    )
    assert first.status_code == 200

    second = await db_async_client.post(
        "/api/v1/chat",
        json={"question": "Jakie są godziny otwarcia biura Albertos?"},
        headers=headers,
    )

    get_settings.cache_clear()

    assert second.status_code == 429
