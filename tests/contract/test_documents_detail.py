"""T010 — contract test: `GET /api/v1/documents/{id}` (feature
010-knowledge-base-admin, US1, research.md §5). Returns the same
`DocumentSummary` shape as a list item; `404` for a nonexistent,
foreign-tenant, or soft-deleted/retired document — all three identical.
"""

import uuid

import pytest

from tests.fixtures.admin import seed_admin_and_token, seed_tenant


@pytest.mark.asyncio
async def test_detail_returns_own_document(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers=headers,
    )
    document_id = upload_response.json()["id"]

    detail_response = await db_async_client.get(f"/api/v1/documents/{document_id}", headers=headers)

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["id"] == document_id
    assert body["content_type"] == "text/plain"
    assert body["status"] == "ready"
    assert body["error_message"] is None


@pytest.mark.asyncio
async def test_detail_returns_404_for_nonexistent_document(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        f"/api/v1/documents/{uuid.uuid4()}", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detail_returns_404_for_foreign_tenant_document(
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

    response = await db_async_client.get(
        f"/api/v1/documents/{document_id}", headers={"authorization": f"Bearer {attacker_token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detail_returns_404_for_deleted_document(
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
    delete_response = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers=headers
    )
    assert delete_response.status_code == 204

    response = await db_async_client.get(f"/api/v1/documents/{document_id}", headers=headers)

    assert response.status_code == 404
