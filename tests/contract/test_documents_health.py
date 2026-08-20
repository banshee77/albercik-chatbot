"""T011 — contract test: `GET /api/v1/documents/health` (feature
010-knowledge-base-admin, US1, FR-028-FR-030). Reports document counts by
status, active-chunk count, `ready_for_chat`, and `last_indexed_at`; an
administrator with zero documents receives `200` with all-zero counts and
`ready_for_chat: false`, never an error.
"""

from datetime import UTC, datetime

import pytest

from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
)
from tests.fixtures.admin import seed_admin_and_token


@pytest.mark.asyncio
async def test_zero_documents_returns_zeroed_health(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.get(
        "/api/v1/documents/health", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "documents": {"total": 0, "ready": 0, "processing": 0, "failed": 0},
        "chunks": 0,
        "ready_for_chat": False,
        "last_indexed_at": None,
    }


@pytest.mark.asyncio
async def test_health_reports_counts_across_mixed_states(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    admin = db_session.query(Administrator).filter_by(tenant_id=default_tenant.id).one()

    ready_doc = KnowledgeDocument(
        original_filename="ready.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=default_tenant.id,
        status=DocumentStatus.ready,
        indexed_at=datetime.now(UTC),
    )
    processing_doc = KnowledgeDocument(
        original_filename="processing.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=default_tenant.id,
        status=DocumentStatus.processing,
    )
    failed_doc = KnowledgeDocument(
        original_filename="failed.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=default_tenant.id,
        status=DocumentStatus.failed,
        safe_error_message="Embedding generation failed. Retry indexing or replace the document.",
    )
    db_session.add_all([ready_doc, processing_doc, failed_doc])
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=ready_doc.id,
            position=0,
            content="Tresc gotowego dokumentu.",
            embedding=[0.0] * 384,
        )
    )
    db_session.flush()

    response = await db_async_client.get(
        "/api/v1/documents/health", headers={"authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == {"total": 3, "ready": 1, "processing": 1, "failed": 1}
    assert body["chunks"] == 1
    assert body["ready_for_chat"] is True
    assert body["last_indexed_at"] is not None


@pytest.mark.asyncio
async def test_health_excludes_other_tenants_data(
    db_async_client, db_session, default_tenant
) -> None:
    from tests.fixtures.admin import seed_tenant

    other_tenant = seed_tenant(db_session)
    own_token = seed_admin_and_token(db_session, tenant_id=default_tenant.id, username="own")
    other_token = seed_admin_and_token(db_session, tenant_id=other_tenant.id, username="other")

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
