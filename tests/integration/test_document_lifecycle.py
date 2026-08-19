"""T045 — integration test: an uploaded document's chunks become
retrievable end-to-end against real `pgvector`, and deletion excludes them
immediately, with no restart or re-indexing (SC-006, SC-007). Goes through
the app under test via HTTP (admin upload/delete) with
`FakeEmbeddingProvider` injected — never the real `sentence-transformers`
model (Design Constraint 2) — then verifies retrievability directly
against `persistence/repositories.py`'s real pgvector query, and via the
full `/api/v1/chat` outcome (quickstart.md Scenario 3).
"""

import uuid

import pytest

from shiruno.persistence.repositories import search_similar_chunks
from tests.fixtures.admin import seed_admin_and_token


@pytest.mark.asyncio
async def test_uploaded_document_is_retrievable_then_deletion_excludes_it(
    db_async_client, db_session, fake_embedding_provider
) -> None:
    token = seed_admin_and_token(db_session)
    headers = {"authorization": f"Bearer {token}"}
    document_content = "Albertos jest czynny od poniedzialku do piatku w godzinach 9-17."

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", document_content.encode(), "text/plain")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]
    assert upload_response.json()["status"] == "ready"

    # The chunk was embedded via embed_passages([document_content]) during
    # upload; embed_query of the SAME text is numerically identical
    # (FakeEmbeddingProvider is a pure hash function of the input string —
    # research.md §8), letting this test prove real-pgvector
    # retrievability without the real semantic model.
    query_vector = fake_embedding_provider.embed_query(document_content)

    results_before_delete = search_similar_chunks(db_session, query_vector, top_k=5)
    assert any(r.document_id == uuid.UUID(document_id) for r in results_before_delete)

    delete_response = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 204

    results_after_delete = search_similar_chunks(db_session, query_vector, top_k=5)
    assert all(r.document_id != uuid.UUID(document_id) for r in results_after_delete)


@pytest.mark.asyncio
async def test_chat_outcome_flips_from_grounded_to_insufficient_after_deletion(
    db_async_client, db_session
) -> None:
    token = seed_admin_and_token(db_session)
    headers = {"authorization": f"Bearer {token}"}
    question = "Jakie sa godziny otwarcia Albertos?"

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", question.encode(), "text/plain")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    grounded_response = await db_async_client.post("/api/v1/chat", json={"question": question})
    assert grounded_response.json()["outcome"] == "grounded"

    delete_response = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 204

    insufficient_response = await db_async_client.post("/api/v1/chat", json={"question": question})
    assert insufficient_response.json()["outcome"] == "insufficient_information"
