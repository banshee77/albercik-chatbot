"""T030 — contract test for `POST /api/v1/chat` (US1 Acceptance Scenarios
US1.1-US1.4; FR-027). Uses fake LLM/embedding providers (research.md §8)
and seeds `document_chunks` directly against `db-test` — no upload
endpoint exists yet (US2/Phase 4).

`FakeEmbeddingProvider` is a hash-based, not a semantic, embedder (it has
no notion of which Polish sentences are "about" the same thing) — so a
chunk is made "relevant" to a question by seeding its embedding as the
exact vector `embed_query(question)` will produce for that question at
request time (a pure function of the input text, research.md §8), giving a
real pgvector cosine similarity of 1.0. A chunk is made "irrelevant" by
seeding it with `embed_passages([...])` of unrelated text instead, which
lands far below the configured relevance threshold.
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
async def test_grounded_answer_includes_source(
    db_async_client, db_session, fake_embedding_provider
):
    question = "Jakie są godziny otwarcia biura Albertos?"
    document = _seed_document_with_chunk(
        db_session,
        filename="godziny.txt",
        content="Biuro Albertos jest otwarte od poniedziałku do piątku, w godzinach 9-17.",
        embedding=fake_embedding_provider.embed_query(question),
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "grounded"
    assert body["answer"]
    assert body["sources"] == [{"document_id": str(document.id), "label": "godziny.txt"}]


@pytest.mark.asyncio
async def test_insufficient_information_when_no_chunk_meets_threshold(
    db_async_client, db_session, fake_embedding_provider
):
    unrelated_embedding = fake_embedding_provider.embed_passages(
        ["zupełnie inny, niepowiązany tekst źródłowy"]
    )[0]
    _seed_document_with_chunk(
        db_session,
        filename="niepowiazane.txt",
        content="Zupełnie inna treść, niepowiązana z zadanym pytaniem.",
        embedding=unrelated_embedding,
    )

    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jaka jest polityka zwrotów w Albertos?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_insufficient_information_with_empty_knowledge_base(db_async_client) -> None:
    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Jakie są godziny otwarcia biura Albertos?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "insufficient_information"
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_out_of_scope_question_is_not_answered(db_async_client) -> None:
    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Napisz mi krótki wiersz o wiośnie."}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "out_of_scope"
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_mixed_intent_question_is_out_of_scope_even_with_matching_context(
    db_async_client, db_session, fake_embedding_provider
) -> None:
    question = "Jakie są stawki za wysyłkę w Albertos, a przy okazji napisz mi wiersz?"
    _seed_document_with_chunk(
        db_session,
        filename="wysylka.txt",
        content="Stawki za wysyłkę w Albertos wynoszą 10 zł na terenie kraju.",
        embedding=fake_embedding_provider.embed_query(question),
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})

    assert response.status_code == 200
    assert response.json()["outcome"] == "out_of_scope"


@pytest.mark.asyncio
async def test_ambiguous_but_plausible_question_is_routed_through_retrieval(
    db_async_client, db_session, fake_embedding_provider
) -> None:
    """T075 edge case, spec.md Clarifications: a vague-but-plausibly-
    Albertos-related question (no off-topic pattern match, so the
    optimistic-by-default scope classifier lets it through) is routed
    through retrieval exactly like any other in-scope question, not
    special-cased — insufficient_information when nothing in the KB
    supports it, grounded when something does."""
    ambiguous_question = "Możecie mi pomóc z czymś?"

    empty_kb_response = await db_async_client.post(
        "/api/v1/chat", json={"question": ambiguous_question}
    )
    assert empty_kb_response.status_code == 200
    assert empty_kb_response.json()["outcome"] == "insufficient_information"

    _seed_document_with_chunk(
        db_session,
        filename="pomoc.txt",
        content="Nasz zespół pomocy Albertos jest dostępny od poniedziałku do piątku.",
        embedding=fake_embedding_provider.embed_query(ambiguous_question),
    )
    grounded_response = await db_async_client.post(
        "/api/v1/chat", json={"question": ambiguous_question}
    )
    assert grounded_response.status_code == 200
    assert grounded_response.json()["outcome"] == "grounded"
