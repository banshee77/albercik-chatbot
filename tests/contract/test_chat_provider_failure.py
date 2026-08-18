"""T060 — contract test: a failing LLM provider call on
`POST /api/v1/chat` results in exactly one call at the `ask_question.py`
level and a safe `unavailable` (503) response — proving `ask_question.py`
adds no retry loop on top of `AnthropicLLMProvider`'s own bounded retries
(Design Constraint 1; US3.6, FR-036). Bounded-retry counting itself is
proven at the provider level by T018 (tests/unit/test_anthropic_provider_
retries.py); this test proves no *additional* multiplication above it.
"""

import uuid

import pytest

from albercik_chatbot.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
)
from albercik_chatbot.providers.llm.protocol import LLMProviderError


@pytest.mark.asyncio
async def test_llm_provider_failure_is_called_exactly_once_by_ask_question(
    db_async_client, db_session, fake_llm_provider, fake_embedding_provider
) -> None:
    fake_llm_provider.error = LLMProviderError("simulated post-retry provider failure")

    question = "Jakie są godziny otwarcia biura Albertos?"
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x")
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="godziny.txt",
        uploaded_by_admin_id=admin.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            position=0,
            content="Biuro Albertos jest otwarte od poniedziałku do piątku.",
            embedding=fake_embedding_provider.embed_query(question),
        )
    )
    db_session.flush()

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"
    assert fake_llm_provider.call_count == 1
