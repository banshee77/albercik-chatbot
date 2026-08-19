"""Contract tests for the structured-answerability decision (feature
004-rag-answerability-and-ollama-performance, User Story 1). Proves
`POST /api/v1/chat` decides `grounded` vs. `insufficient_information` from
`LLMResult.supported`, not from whether the model returned any text — the
core fix for the 7/7 false-grounded baseline (spec.md).

`test_grounded_answer_includes_source` (tests/contract/test_chat.py) and
`test_llm_provider_failure_is_called_exactly_once_by_ask_question`
(tests/contract/test_chat_provider_failure.py) already cover the
`supported=True` -> `grounded` and `LLMProviderError` -> `unavailable`
sides of this contract; this file adds the case that actually changed
behavior: `supported=False` even though retrieval *did* surface a
grounding chunk (the exact shape of the pre-fix bug — "the model returned
text" is no longer sufficient for `grounded`).
"""

import uuid

import pytest

from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    Tenant,
)
from shiruno.providers.llm.protocol import LLMResult


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


@pytest.mark.asyncio
async def test_supported_false_is_insufficient_information_even_with_a_grounding_chunk(
    db_async_client, db_session, fake_llm_provider, fake_embedding_provider
) -> None:
    """The pre-fix bug, reproduced and proven fixed: retrieval surfaces a
    chunk that clears the relevance threshold (so the old "any model text
    -> grounded" logic would have answered), but the model's structured
    decision says the context doesn't actually support an answer. FR-001:
    the outcome must come from `supported`, not from text presence."""
    question = "Czy Albertos oferuje wynajem sprzętu na wyjazdy zagraniczne?"
    _seed_document_with_chunk(
        db_session,
        filename="wyjazdy.txt",
        content="Albertos organizuje obozy sportowe w Polsce dla dzieci i młodzieży.",
        embedding=fake_embedding_provider.embed_query(question),
    )
    fabricated_negative_answer = "Nie, Albertos nie oferuje wynajmu sprzętu na wyjazdy zagraniczne."
    fake_llm_provider.response = LLMResult(
        answer=fabricated_negative_answer,
        supported=False,
        model="fake-llm",
        input_tokens=10,
        output_tokens=5,
        latency_ms=1,
        provider_metrics=None,
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    assert body["sources"] == []
    # The model's own (fabricated) answer text must never leak through —
    # only the fixed insufficient-information message (FR-003).
    assert fabricated_negative_answer not in body["answer"]


@pytest.mark.asyncio
async def test_supported_true_returns_answer_and_sources(
    db_async_client, db_session, fake_llm_provider, fake_embedding_provider
) -> None:
    question = "Jakie są godziny otwarcia biura Albertos?"
    document = _seed_document_with_chunk(
        db_session,
        filename="godziny.txt",
        content="Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17.",
        embedding=fake_embedding_provider.embed_query(question),
    )
    model_answer = "Biuro jest otwarte od poniedziałku do piątku, 9-17."
    fake_llm_provider.response = LLMResult(
        answer=model_answer,
        supported=True,
        model="fake-llm",
        input_tokens=10,
        output_tokens=5,
        latency_ms=1,
        provider_metrics=None,
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    assert body["answer"] == model_answer
    assert body["sources"] == [{"document_id": str(document.id), "label": "godziny.txt"}]
