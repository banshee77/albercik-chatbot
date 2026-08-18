"""T044 — contract test for `POST /api/v1/auth/login` (FR-008, Acceptance
Scenario US2.6). Verifies success issues an access token, and that
wrong-password, unknown-username, and inactive-account failures are all
generic — never revealing which case applied.
"""

import pytest

from albercik_chatbot.infra.security import hash_password
from albercik_chatbot.persistence.models import Administrator


def _seed_admin(
    db_session, *, username: str, password: str, is_active: bool = True
) -> Administrator:
    admin = Administrator(
        username=username, password_hash=hash_password(password), is_active=is_active
    )
    db_session.add(admin)
    db_session.flush()
    return admin


@pytest.mark.asyncio
async def test_login_success_issues_access_token(db_async_client, db_session) -> None:
    _seed_admin(db_session, username="admin1", password="correct-horse-battery-staple")

    response = await db_async_client.post(
        "/api/v1/auth/login",
        json={"username": "admin1", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password_is_rejected(db_async_client, db_session) -> None:
    _seed_admin(db_session, username="admin2", password="the-real-password")

    response = await db_async_client.post(
        "/api/v1/auth/login", json={"username": "admin2", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_login_unknown_username_and_wrong_password_return_identical_response(
    db_async_client, db_session
) -> None:
    _seed_admin(db_session, username="admin3", password="the-real-password")

    wrong_password_response = await db_async_client.post(
        "/api/v1/auth/login", json={"username": "admin3", "password": "wrong-password"}
    )
    unknown_username_response = await db_async_client.post(
        "/api/v1/auth/login", json={"username": "no-such-admin", "password": "anything"}
    )

    assert wrong_password_response.status_code == unknown_username_response.status_code == 401
    assert wrong_password_response.json() == unknown_username_response.json()


@pytest.mark.asyncio
async def test_login_inactive_administrator_is_rejected(db_async_client, db_session) -> None:
    _seed_admin(db_session, username="admin4", password="the-real-password", is_active=False)

    response = await db_async_client.post(
        "/api/v1/auth/login", json={"username": "admin4", "password": "the-real-password"}
    )

    assert response.status_code == 401
