"""Feature 009-admin-platform-foundation, User Story 4 (FR-016, FR-018):
every tenant-scoped admin route fails closed identically for missing,
malformed, and expired authentication — no route leaks a different status
or message across the three cases.
"""

import uuid

import pytest

from shiruno.config import get_settings
from shiruno.infra.security import hash_password, issue_access_token
from shiruno.persistence.models import Administrator

_EXPECTED_STATUS = 401
# api/deps.py::_GENERIC_AUTH_FAILURE — the actual message every
# get_current_administrator/get_current_tenant failure raises with,
# deliberately generic and identical for missing/invalid/expired.
_EXPECTED_BODY = {"detail": "Authentication required."}

_ROUTES = [
    ("GET", "/api/v1/admin/me", {}),
    ("POST", "/api/v1/documents", {"files": {"file": ("x.txt", b"tresc", "text/plain")}}),
    ("GET", "/api/v1/documents", {}),
    ("DELETE", f"/api/v1/documents/{uuid.uuid4()}", {}),
]


def _make_expired_token(db_session, default_tenant) -> str:
    admin = Administrator(
        username=f"fail-closed-{uuid.uuid4()}",
        password_hash=hash_password("x"),
        tenant_id=default_tenant.id,
    )
    db_session.add(admin)
    db_session.flush()
    settings = get_settings()
    return issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=-1,
    ).access_token


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,kwargs", _ROUTES)
async def test_missing_token_fails_closed_identically(
    db_async_client, method, path, kwargs
) -> None:
    response = await db_async_client.request(method, path, **kwargs)

    assert response.status_code == _EXPECTED_STATUS
    assert response.json() == _EXPECTED_BODY


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,kwargs", _ROUTES)
async def test_malformed_token_fails_closed_identically(
    db_async_client, method, path, kwargs
) -> None:
    response = await db_async_client.request(
        method, path, headers={"authorization": "Bearer not-a-real-token"}, **kwargs
    )

    assert response.status_code == _EXPECTED_STATUS
    assert response.json() == _EXPECTED_BODY


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,kwargs", _ROUTES)
async def test_expired_token_fails_closed_identically(
    db_async_client, db_session, default_tenant, method, path, kwargs
) -> None:
    expired_token = _make_expired_token(db_session, default_tenant)

    response = await db_async_client.request(
        method, path, headers={"authorization": f"Bearer {expired_token}"}, **kwargs
    )

    assert response.status_code == _EXPECTED_STATUS
    assert response.json() == _EXPECTED_BODY
