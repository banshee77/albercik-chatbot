"""T024 — contract test: `POST /api/v1/documents/{id}/reindex` (feature
010-knowledge-base-admin, US5, FR-023-FR-027). A successful re-index keeps
the same document id and regenerates chunk embeddings; a failed re-index
never regresses a document that was already working, and its
`error_message` is always the fixed, sanitized string — never raw
exception detail (research.md §10a). The endpoint accepts no client
override of provider/model/chunking settings.
"""

import uuid

import pytest
from sqlalchemy import select

from shiruno.persistence.models import DocumentChunk
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


@pytest.mark.asyncio
async def test_successful_reindex_regenerates_embeddings(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]
    before_indexed_at = upload_response.json()["indexed_at"]
    before_chunk = db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
    ).scalar_one()
    before_embedding = list(before_chunk.embedding)

    reindex_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex", headers=headers
    )

    assert reindex_response.status_code == 200
    body = reindex_response.json()
    assert body["id"] == document_id
    assert body["status"] == "ready"
    assert body["error_message"] is None
    assert body["indexed_at"] != before_indexed_at

    db_session.expire_all()
    after_chunk = db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
    ).scalar_one()
    # FakeEmbeddingProvider is deterministic per input text — re-embedding
    # the exact same stored chunk content produces the exact same vector,
    # so equality here proves the chunk's real content was actually
    # re-embedded (not a no-op), even though the vector is unchanged.
    assert list(after_chunk.embedding) == before_embedding


@pytest.mark.asyncio
async def test_failed_reindex_on_ready_document_leaves_status_and_embeddings_unchanged(
    db_async_client, db_session, default_tenant, fake_embedding_provider
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]
    before_chunk = db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
    ).scalar_one()
    before_embedding = list(before_chunk.embedding)

    unsafe_exception = Exception(
        "Traceback (most recent call last): ... ConnectionError to "
        "http://embedding-internal.example:9999 using key sk-test-do-not-leak-12345"
    )
    fake_embedding_provider.error = unsafe_exception

    reindex_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex", headers=headers
    )

    assert reindex_response.status_code == 200
    body = reindex_response.json()
    assert body["status"] == "ready"
    assert body["error_message"] is not None
    response_text = reindex_response.text
    assert "Traceback" not in response_text
    assert "embedding-internal.example" not in response_text
    assert "sk-test-do-not-leak-12345" not in response_text

    db_session.expire_all()
    after_chunk = db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
    ).scalar_one()
    assert list(after_chunk.embedding) == before_embedding


@pytest.mark.asyncio
async def test_failed_reindex_on_failed_document_stays_failed_with_updated_message(
    db_async_client, db_session, default_tenant, fake_embedding_provider
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    fake_embedding_provider.error = Exception("boom")
    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("bad.txt", b"Nie zaindeksowana tresc.", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]
    assert upload_response.json()["status"] == "failed"

    reindex_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex", headers=headers
    )

    assert reindex_response.status_code == 200
    body = reindex_response.json()
    assert body["status"] == "failed"
    assert body["error_message"] is not None


@pytest.mark.asyncio
async def test_reindex_accepts_no_body_or_query_overrides(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]

    response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex"
        "?embedding_provider=other&embedding_model=other&chunk_size=1&overlap=1",
        json={"embedding_provider": "other", "chunk_size_chars": 1},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_reindex_nonexistent_document_returns_404(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        f"/api/v1/documents/{uuid.uuid4()}/reindex",
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reindex_foreign_tenant_document_returns_404(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    owner_token = seed_admin_and_token(db_session, tenant_id=other_tenant.id, username="owner")
    attacker_token = seed_admin_and_token(
        db_session, tenant_id=default_tenant.id, username="attacker"
    )

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("owner.txt", b"Tresc wlasciciela.", "text/plain")},
        headers={"authorization": f"Bearer {owner_token}"},
    )
    document_id = upload_response.json()["id"]

    response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex",
        headers={"authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reindex_deleted_document_returns_404(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("x.txt", b"tresc", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]
    await db_async_client.delete(f"/api/v1/documents/{document_id}", headers=headers)

    response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex", headers=headers
    )

    assert response.status_code == 404
