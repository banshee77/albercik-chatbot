"""Feature 009-admin-platform-foundation, User Story 5 (FR-021, FR-022,
SC-009): the public `/api/v1/chat` endpoint requires no tenant/assistant
identifier and rejects an attempt to supply one exactly like any other
unknown field, via the pre-existing `extra="forbid"` guard
(api/schemas.py::ChatRequest) — unchanged by this feature.
"""

import pytest


@pytest.mark.asyncio
async def test_tenant_id_field_on_chat_request_is_rejected_like_any_unknown_field(
    db_async_client,
) -> None:
    response = await db_async_client.post(
        "/api/v1/chat",
        json={
            "question": "Jakie są godziny otwarcia biura Albertos?",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_assistant_id_field_on_chat_request_is_rejected_like_any_unknown_field(
    db_async_client,
) -> None:
    response = await db_async_client.post(
        "/api/v1/chat",
        json={
            "question": "Jakie są godziny otwarcia biura Albertos?",
            "assistant_id": "some-assistant",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_normal_chat_request_needs_no_tenant_or_assistant_identifier(
    db_async_client,
) -> None:
    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 200
    assert response.json()["outcome"] in (
        "grounded",
        "insufficient_information",
        "out_of_scope",
        "unavailable",
        "small_talk",
    )
