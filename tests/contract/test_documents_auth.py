"""T041 — contract test: `/api/v1/documents` (POST/GET) and
`/api/v1/documents/{id}` (DELETE) reject a Public User and unauthenticated
requests (FR-003, FR-004, FR-007, SC-004). No knowledge-base state may
change as a side effect of a rejected request.

Also (pre-Phase-5 security checkpoint, 2026-08-17): an expired token and a
still-cryptographically-valid token belonging to a since-deactivated
administrator are both rejected at the HTTP layer, generically.
"""

import uuid

import pytest
from sqlalchemy import func, select

from shiruno.config import get_settings
from shiruno.infra.security import issue_access_token
from shiruno.persistence.models import Administrator, KnowledgeDocument, TenantStatus
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


@pytest.mark.asyncio
async def test_upload_without_token_is_rejected_and_creates_nothing(
    db_async_client, db_session
) -> None:
    response = await db_async_client.post(
        "/api/v1/documents", files={"file": ("test.txt", b"tresc", "text/plain")}
    )

    assert response.status_code == 401
    count = db_session.execute(select(func.count()).select_from(KnowledgeDocument)).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_list_without_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.get("/api/v1/documents")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_without_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.delete(f"/api/v1/documents/{uuid.uuid4()}")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_with_invalid_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", b"tresc", "text/plain")},
        headers={"authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_with_invalid_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_with_invalid_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.delete(
        f"/api/v1/documents/{uuid.uuid4()}", headers={"authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_is_rejected(db_async_client, db_session, default_tenant) -> None:
    admin = Administrator(
        username="expired-token-admin", password_hash="x", tenant_id=default_tenant.id
    )
    db_session.add(admin)
    db_session.flush()

    settings = get_settings()
    expired_token = issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=-1,
    ).access_token

    response = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_administrator_token_is_rejected(
    db_async_client, db_session, default_tenant
) -> None:
    admin = Administrator(
        username="soon-inactive-admin", password_hash="x", tenant_id=default_tenant.id
    )
    db_session.add(admin)
    db_session.flush()

    settings = get_settings()
    token = issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=settings.AUTH_JWT_EXPIRE_MINUTES,
    ).access_token

    # The token itself is still perfectly valid — only the account's
    # is_active flag changes, proving get_current_administrator re-checks
    # DB state on every request rather than trusting the token alone.
    admin.is_active = False
    db_session.flush()

    response = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


# --- Feature 009-admin-platform-foundation, User Story 3: cross-tenant
# isolation on the existing document endpoints (FR-013, FR-015, FR-018,
# FR-024, spec Testing Requirements #10, #13). ---


@pytest.mark.asyncio
async def test_administrator_only_sees_own_tenants_documents_in_list(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    own_token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="own-admin")
    other_token = seed_admin_and_token(
        db_session, tenant_id=other_tenant.id, username="other-admin"
    )

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("own.txt", b"Tresc dokumentu wlasciciela.", "text/plain")},
        headers={"authorization": f"Bearer {own_token}"},
    )
    assert upload_response.status_code == 201
    own_document_id = upload_response.json()["id"]

    own_list = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {own_token}"}
    )
    other_list = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {other_token}"}
    )

    assert any(doc["id"] == own_document_id for doc in own_list.json())
    assert all(doc["id"] != own_document_id for doc in other_list.json())


@pytest.mark.asyncio
async def test_deleting_another_tenants_document_returns_404_and_leaves_it_intact(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    owner_token = seed_admin_and_token(
        db_session, tenant_id=default_tenant.id, username="owner-admin"
    )
    attacker_token = seed_admin_and_token(
        db_session, tenant_id=other_tenant.id, username="attacker-admin"
    )

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("owner.txt", b"Tresc dokumentu wlasciciela.", "text/plain")},
        headers={"authorization": f"Bearer {owner_token}"},
    )
    document_id = upload_response.json()["id"]

    delete_attempt = await db_async_client.delete(
        f"/api/v1/documents/{document_id}", headers={"authorization": f"Bearer {attacker_token}"}
    )
    assert delete_attempt.status_code == 404

    owner_list = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {owner_token}"}
    )
    assert any(doc["id"] == document_id for doc in owner_list.json())


@pytest.mark.asyncio
async def test_client_supplied_tenant_identifier_has_no_effect_on_documents_routes(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    token = seed_admin_and_token(
        db_session, tenant_id=default_tenant.id, username="no-override-admin"
    )

    header_response = await db_async_client.get(
        "/api/v1/documents",
        headers={"authorization": f"Bearer {token}", "X-Tenant-Id": str(other_tenant.id)},
    )
    query_response = await db_async_client.get(
        f"/api/v1/documents?tenant_id={other_tenant.id}",
        headers={"authorization": f"Bearer {token}"},
    )

    assert header_response.status_code == 200
    assert query_response.status_code == 200

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", b"Tresc.", "text/plain")},
        data={"tenant_id": str(other_tenant.id)},
        headers={"authorization": f"Bearer {token}"},
    )
    assert upload_response.status_code == 201
    document = db_session.get(KnowledgeDocument, uuid.UUID(upload_response.json()["id"]))
    assert document.tenant_id == default_tenant.id
    assert document.tenant_id != other_tenant.id


@pytest.mark.asyncio
async def test_deactivated_tenant_denies_document_access(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(
        db_session, tenant_id=default_tenant.id, username="soon-inactive-tenant-admin"
    )
    # The token itself, and the administrator account, remain perfectly
    # valid — only the tenant's status changes (no supported operation to
    # do this exists, Clarifications 2026-08-19; this is direct test setup).
    default_tenant.status = TenantStatus.inactive
    db_session.flush()

    list_response = await db_async_client.get(
        "/api/v1/documents", headers={"authorization": f"Bearer {token}"}
    )
    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", b"Tresc.", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )
    delete_response = await db_async_client.delete(
        f"/api/v1/documents/{uuid.uuid4()}", headers={"authorization": f"Bearer {token}"}
    )

    assert list_response.status_code == 401
    assert upload_response.status_code == 401
    assert delete_response.status_code == 401


# --- Feature 010-knowledge-base-admin, User Story 6: cross-tenant
# isolation on detail, health, replace, and re-index (FR-031, FR-032,
# spec Testing Requirements #14, #16, #18, #20). ---


@pytest.mark.asyncio
async def test_foreign_tenant_cannot_view_replace_or_reindex_document(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    owner_token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="owner-b")
    attacker_token = seed_admin_and_token(
        db_session, tenant_id=other_tenant.id, username="attacker-b"
    )

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("owner.txt", b"Tresc wlasciciela.", "text/plain")},
        headers={"authorization": f"Bearer {owner_token}"},
    )
    document_id = upload_response.json()["id"]
    attacker_headers = {"authorization": f"Bearer {attacker_token}"}

    detail_response = await db_async_client.get(
        f"/api/v1/documents/{document_id}", headers=attacker_headers
    )
    replace_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/replace",
        files={"file": ("x.txt", b"tresc", "text/plain")},
        headers=attacker_headers,
    )
    reindex_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex", headers=attacker_headers
    )

    assert detail_response.status_code == 404
    assert replace_response.status_code == 404
    assert reindex_response.status_code == 404

    owner_detail = await db_async_client.get(
        f"/api/v1/documents/{document_id}", headers={"authorization": f"Bearer {owner_token}"}
    )
    assert owner_detail.status_code == 200
    assert owner_detail.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_health_summary_never_reflects_another_tenants_data(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    own_token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="own-h")
    other_token = seed_admin_and_token(db_session, tenant_id=other_tenant.id, username="other-h")

    await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("own.txt", b"Tresc wlasna.", "text/plain")},
        headers={"authorization": f"Bearer {own_token}"},
    )

    own_health = await db_async_client.get(
        "/api/v1/documents/health", headers={"authorization": f"Bearer {own_token}"}
    )
    other_health = await db_async_client.get(
        "/api/v1/documents/health", headers={"authorization": f"Bearer {other_token}"}
    )

    assert own_health.json()["documents"]["total"] == 1
    assert other_health.json()["documents"] == {
        "total": 0,
        "ready": 0,
        "processing": 0,
        "failed": 0,
    }


@pytest.mark.asyncio
async def test_client_supplied_tenant_identifier_has_no_effect_on_new_routes(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="no-override-b")
    headers = {"authorization": f"Bearer {token}", "X-Tenant-Id": str(other_tenant.id)}

    upload_response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("own.txt", b"Tresc wlasna.", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )
    document_id = upload_response.json()["id"]

    detail_response = await db_async_client.get(f"/api/v1/documents/{document_id}", headers=headers)
    health_response = await db_async_client.get("/api/v1/documents/health", headers=headers)
    replace_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/replace",
        files={"file": ("new.txt", b"Nowa tresc.", "text/plain")},
        data={"tenant_id": str(other_tenant.id)},
        headers=headers,
    )
    reindex_response = await db_async_client.post(
        f"/api/v1/documents/{document_id}/reindex"
        if replace_response.status_code != 201
        else f"/api/v1/documents/{replace_response.json()['id']}/reindex",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert health_response.status_code == 200
    assert replace_response.status_code == 201
    successor = db_session.get(KnowledgeDocument, uuid.UUID(replace_response.json()["id"]))
    assert successor.tenant_id == default_tenant.id
    assert successor.tenant_id != other_tenant.id
    assert reindex_response.status_code == 200
