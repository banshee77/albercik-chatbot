"""T019 — contract test: `POST /api/v1/documents/{id}/replace` (feature
010-knowledge-base-admin, US3, FR-014-FR-019). A successful replace
produces a new document id, retires the predecessor, and the assistant
answers from the new content; a failed replace leaves the predecessor
completely unaffected; replacing a nonexistent, foreign-tenant, or
already-deleted/retired document returns 404.
"""

import uuid

import pytest

from tests.fixtures.admin import seed_admin_and_token, seed_tenant


@pytest.mark.asyncio
async def test_successful_replace_retires_predecessor_and_activates_successor(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    predecessor_id = upload_response.json()["id"]

    replace_response = await db_async_client.post(
        f"/api/v1/documents/{predecessor_id}/replace",
        files={"file": ("godziny-nowe.txt", b"Albertos jest czynny od 8 do 20.", "text/plain")},
        headers=headers,
    )

    assert replace_response.status_code == 201
    body = replace_response.json()
    assert body["status"] == "ready"
    successor_id = body["id"]
    assert successor_id != predecessor_id

    list_response = await db_async_client.get("/api/v1/documents", headers=headers)
    ids = [doc["id"] for doc in list_response.json()]
    assert successor_id in ids
    assert predecessor_id not in ids

    predecessor_detail = await db_async_client.get(
        f"/api/v1/documents/{predecessor_id}", headers=headers
    )
    assert predecessor_detail.status_code == 404

    chat_response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Albertos jest czynny od 8 do 20."}
    )
    assert chat_response.status_code == 200


@pytest.mark.asyncio
async def test_failed_replace_leaves_predecessor_completely_unaffected(
    db_async_client, db_session, default_tenant, fake_embedding_provider
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    predecessor_id = upload_response.json()["id"]

    fake_embedding_provider.error = Exception("boom")
    replace_response = await db_async_client.post(
        f"/api/v1/documents/{predecessor_id}/replace",
        files={"file": ("bad.txt", b"To sie nie zaindeksuje.", "text/plain")},
        headers=headers,
    )

    assert replace_response.status_code == 201
    assert replace_response.json()["status"] == "failed"

    fake_embedding_provider.error = None
    predecessor_detail = await db_async_client.get(
        f"/api/v1/documents/{predecessor_id}", headers=headers
    )
    assert predecessor_detail.status_code == 200
    assert predecessor_detail.json()["status"] == "ready"

    list_response = await db_async_client.get("/api/v1/documents", headers=headers)
    ids = [doc["id"] for doc in list_response.json()]
    assert predecessor_id in ids


@pytest.mark.asyncio
async def test_replace_nonexistent_document_returns_404(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        f"/api/v1/documents/{uuid.uuid4()}/replace",
        files={"file": ("x.txt", b"tresc", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_replace_foreign_tenant_document_returns_404(
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
        f"/api/v1/documents/{document_id}/replace",
        files={"file": ("x.txt", b"tresc", "text/plain")},
        headers={"authorization": f"Bearer {attacker_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_replace_already_deleted_document_returns_404(
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
        f"/api/v1/documents/{document_id}/replace",
        files={"file": ("y.txt", b"nowa tresc", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 404
