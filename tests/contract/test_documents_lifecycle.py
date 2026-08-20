"""T043 — contract test: list shows uploaded documents; delete removes it
from the list (FR-014-FR-016). Also covers the edge case of deleting an
already-deleted/unknown document (safe 404, spec.md Edge Cases).
"""

import uuid

import pytest

from tests.fixtures.admin import seed_admin_and_token


@pytest.mark.asyncio
async def test_uploaded_document_appears_in_list_then_delete_removes_it(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]
    assert upload_response.json()["status"] == "ready"

    list_response = await db_async_client.get("/api/v1/documents", headers=headers)
    assert list_response.status_code == 200
    listed = next(doc for doc in list_response.json() if doc["id"] == document_id)
    assert listed["content_type"] == "text/plain"
    assert listed["updated_at"] is not None
    assert listed["indexed_at"] is not None
    assert listed["error_message"] is None

    delete_response = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 204

    list_after_delete = await db_async_client.get("/api/v1/documents", headers=headers)
    assert all(doc["id"] != document_id for doc in list_after_delete.json())


@pytest.mark.asyncio
async def test_delete_unknown_document_returns_404(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.delete(
        f"/api/v1/documents/{uuid.uuid4()}", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_already_deleted_document_returns_404(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("x.txt", b"Tresc dokumentu.", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]
    first_delete = await db_async_client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert first_delete.status_code == 204

    second_delete = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert second_delete.status_code == 404


@pytest.mark.asyncio
async def test_deleted_document_excluded_from_list_detail_health_and_chat(
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

    delete_response = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 204

    list_response = await db_async_client.get("/api/v1/documents", headers=headers)
    assert all(doc["id"] != document_id for doc in list_response.json())

    detail_response = await db_async_client.get(f"/api/v1/documents/{document_id}", headers=headers)
    assert detail_response.status_code == 404

    health_response = await db_async_client.get("/api/v1/documents/health", headers=headers)
    assert health_response.json()["documents"] == {
        "total": 0,
        "ready": 0,
        "processing": 0,
        "failed": 0,
    }

    chat_response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Albertos jest czynny od 9 do 17."}
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["outcome"] == "insufficient_information"


@pytest.mark.asyncio
async def test_zero_documents_returns_valid_empty_list(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == []
