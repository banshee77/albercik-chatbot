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

from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.security import issue_access_token
from albercik_chatbot.persistence.models import Administrator, KnowledgeDocument


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
async def test_expired_token_is_rejected(db_async_client, db_session) -> None:
    admin = Administrator(username="expired-token-admin", password_hash="x")
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
async def test_deactivated_administrator_token_is_rejected(db_async_client, db_session) -> None:
    admin = Administrator(username="soon-inactive-admin", password_hash="x")
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
