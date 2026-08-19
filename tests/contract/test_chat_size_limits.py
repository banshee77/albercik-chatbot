"""T057 — contract test: over-length question / oversized payload on
`POST /api/v1/chat` is rejected before any embedding or LLM provider call
(US3.2, FR-038, FR-039).
"""

import pytest

from shiruno.config import get_settings


@pytest.mark.asyncio
async def test_over_length_question_is_rejected_before_any_provider_call(
    db_async_client, fake_llm_provider, fake_embedding_provider
) -> None:
    limit = get_settings().MAX_QUESTION_LENGTH_CHARS

    response = await db_async_client.post("/api/v1/chat", json={"question": "a" * (limit + 1)})

    assert response.status_code == 400
    assert fake_embedding_provider.embed_calls == []
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_oversized_request_body_is_rejected_before_any_provider_call(
    db_async_client, fake_llm_provider, fake_embedding_provider, monkeypatch
) -> None:
    monkeypatch.setenv("MAX_CHAT_REQUEST_BODY_BYTES", "50")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/chat",
        json={"question": "Jakie są godziny otwarcia biura Albertos w tym miesiącu?"},
    )

    get_settings.cache_clear()

    assert response.status_code == 413
    assert fake_embedding_provider.embed_calls == []
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_question_exactly_at_the_configured_length_boundary_is_accepted(
    db_async_client,
) -> None:
    # T075 edge case: the boundary itself (not limit-1, not limit+1) must
    # be accepted — `tests/unit/test_schemas.py` already proves this at
    # the Pydantic-model level directly; this proves it end-to-end
    # through the real HTTP route too.
    limit = get_settings().MAX_QUESTION_LENGTH_CHARS

    response = await db_async_client.post("/api/v1/chat", json={"question": "a" * limit})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_empty_question_is_rejected_before_any_provider_call(
    db_async_client, fake_llm_provider, fake_embedding_provider
) -> None:
    response = await db_async_client.post("/api/v1/chat", json={"question": ""})

    assert response.status_code == 400
    assert fake_embedding_provider.embed_calls == []
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_whitespace_only_question_is_handled_safely_not_a_server_error(
    db_async_client,
) -> None:
    # No dedicated "meaningless question" rejection exists (spec.md
    # doesn't require one): a whitespace-only question passes the
    # non-empty check, is optimistically treated as in-scope (domain/
    # scope.py), and finds nothing in retrieval — the important property
    # is that this resolves safely (200, a normal outcome), never a 500.
    response = await db_async_client.post("/api/v1/chat", json={"question": "   "})

    assert response.status_code == 200
    assert response.json()["outcome"] in ("insufficient_information", "out_of_scope")
