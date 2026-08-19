"""T074 — contract test: security-relevant administrator actions produce
an audit log line via the real HTTP routes (FR-053). Verifies wiring only
— `tests/unit/test_audit.py` covers `log_audit_event`'s own content
guarantees in isolation.
"""

import logging

import pytest

from shiruno.infra.security import hash_password
from shiruno.persistence.models import Administrator
from tests.fixtures.admin import seed_admin_and_token


@pytest.mark.asyncio
async def test_login_success_and_failure_are_both_audit_logged(
    db_async_client, db_session, default_tenant, caplog
) -> None:
    admin = Administrator(
        username="audit-admin",
        password_hash=hash_password("correct-pw"),
        tenant_id=default_tenant.id,
    )
    db_session.add(admin)
    db_session.flush()

    with caplog.at_level(logging.INFO, logger="shiruno.audit"):
        ok = await db_async_client.post(
            "/api/v1/auth/login", json={"username": "audit-admin", "password": "correct-pw"}
        )
        bad = await db_async_client.post(
            "/api/v1/auth/login", json={"username": "audit-admin", "password": "wrong-pw"}
        )

    assert ok.status_code == 200
    assert bad.status_code == 401
    messages = [r.message for r in caplog.records if r.name == "shiruno.audit"]
    tenant_id = str(default_tenant.id)
    assert any("login_success" in m and "audit-admin" in m and tenant_id in m for m in messages)
    assert any("login_failure" in m and "audit-admin" in m for m in messages)


@pytest.mark.asyncio
async def test_document_upload_and_delete_are_audit_logged(
    db_async_client, db_session, default_tenant, caplog
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    headers = {"authorization": f"Bearer {token}"}

    with caplog.at_level(logging.INFO, logger="shiruno.audit"):
        upload_response = await db_async_client.post(
            "/api/v1/documents",
            files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
            headers=headers,
        )
        document_id = upload_response.json()["id"]
        delete_response = await db_async_client.delete(
            f"/api/v1/documents/{document_id}", headers=headers
        )

    assert upload_response.status_code == 201
    assert delete_response.status_code == 204
    messages = [r.message for r in caplog.records if r.name == "shiruno.audit"]
    tenant_id = str(default_tenant.id)
    assert any("document_upload" in m and document_id in m and tenant_id in m for m in messages)
    assert any("document_delete" in m and document_id in m and tenant_id in m for m in messages)


@pytest.mark.asyncio
async def test_audit_log_never_contains_the_password(
    db_async_client, db_session, default_tenant, caplog
) -> None:
    secret_password = "extremely-secret-password-should-never-appear"

    admin = Administrator(
        username="password-check-admin",
        password_hash=hash_password(secret_password),
        tenant_id=default_tenant.id,
    )
    db_session.add(admin)
    db_session.flush()

    with caplog.at_level(logging.INFO):
        await db_async_client.post(
            "/api/v1/auth/login",
            json={"username": "password-check-admin", "password": secret_password},
        )

    for record in caplog.records:
        assert secret_password not in record.message
