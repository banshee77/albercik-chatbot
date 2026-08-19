"""T066 (HTTP-level) — contract test: `POST /api/v1/chat` respects the
process-local concurrency guard for paid LLM calls. The guard's own
mutual-exclusion mechanics are unit-tested in isolation
(tests/unit/test_concurrency.py); this proves the route/application
actually consults it at the right pipeline position and fails safely
(`unavailable`/503, no provider call) when no slot is free.

Deliberately does not attempt genuine concurrent HTTP requests: the shared
`db_session` fixture (a single SQLAlchemy `Session`) used by every other
contract test is not safe for concurrent use across the OS threads
FastAPI's sync route runs in — a real two-requests-at-once test would risk
flaky/undefined session behavior unrelated to what's being tested here.
Simulating "no slot available" by pre-holding the guard's only slot is
deterministic and exercises the same code path.
"""

import pytest

from shiruno.infra.concurrency import ChatConcurrencyGuard


@pytest.mark.asyncio
async def test_request_is_rejected_when_no_concurrency_slot_is_free(
    db_async_client, test_app, fake_llm_provider, fake_embedding_provider
) -> None:
    guard = ChatConcurrencyGuard(limit=1)
    test_app.state.chat_concurrency_guard = guard
    guard._semaphore.acquire()  # simulates an already in-flight paid LLM call
    try:
        response = await db_async_client.post(
            "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
        )
    finally:
        guard._semaphore.release()

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_embedding_provider.embed_calls == []
    assert fake_llm_provider.call_count == 0


@pytest.mark.asyncio
async def test_request_succeeds_once_the_slot_is_free_again(
    db_async_client, test_app, fake_llm_provider, fake_embedding_provider
) -> None:
    test_app.state.chat_concurrency_guard = ChatConcurrencyGuard(limit=1)

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 200
