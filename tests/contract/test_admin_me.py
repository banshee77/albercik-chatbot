"""Contract test for `GET /api/v1/admin/me` (feature
009-admin-platform-foundation, User Story 1; FR-012, FR-013, FR-016,
FR-019, FR-020; contracts/admin-api-delta.md).
"""

import pytest

from shiruno.config import get_settings
from shiruno.infra.security import hash_password, issue_access_token
from shiruno.persistence.models import Administrator
from tests.fixtures.admin import seed_admin_and_token, seed_tenant


@pytest.mark.asyncio
async def test_valid_token_returns_own_administrator_and_tenant(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="me-admin")

    response = await db_async_client.get(
        "/api/v1/admin/me", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["administrator"]["username"] == "me-admin"
    assert body["tenant"]["id"] == str(default_tenant.id)
    assert body["tenant"]["name"] == default_tenant.name
    assert body["tenant"]["slug"] == default_tenant.slug


@pytest.mark.asyncio
async def test_response_never_includes_secrets_or_another_tenant(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    seed_admin_and_token(db_session, tenant_id=other_tenant.id, username="other-tenant-admin")
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="me-admin-2")

    response = await db_async_client.get(
        "/api/v1/admin/me", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    serialized = response.text
    assert "password" not in serialized.lower()
    assert str(other_tenant.id) not in serialized
    assert other_tenant.slug not in serialized


@pytest.mark.asyncio
async def test_missing_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.get("/api/v1/admin/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_is_rejected(db_async_client) -> None:
    response = await db_async_client.get(
        "/api/v1/admin/me", headers={"authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_is_rejected(db_async_client, db_session, default_tenant) -> None:
    settings = get_settings()
    admin = Administrator(
        username="expiring-me-admin", password_hash=hash_password("x"), tenant_id=default_tenant.id
    )
    db_session.add(admin)
    db_session.flush()
    expired_token = issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=-1,
    ).access_token

    response = await db_async_client.get(
        "/api/v1/admin/me", headers={"authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_supplied_tenant_override_has_no_effect(
    db_async_client, db_session, default_tenant
) -> None:
    other_tenant = seed_tenant(db_session)
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="override-admin")

    header_response = await db_async_client.get(
        "/api/v1/admin/me",
        headers={"authorization": f"Bearer {token}", "X-Tenant-Id": str(other_tenant.id)},
    )
    query_response = await db_async_client.get(
        f"/api/v1/admin/me?tenant_id={other_tenant.id}",
        headers={"authorization": f"Bearer {token}"},
    )

    for response in (header_response, query_response):
        assert response.status_code == 200
        assert response.json()["tenant"]["id"] == str(default_tenant.id)
        assert response.json()["tenant"]["id"] != str(other_tenant.id)
