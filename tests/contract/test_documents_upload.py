"""T042 — contract test: upload validation (FR-009-FR-013) — non-`.txt`,
invalid UTF-8, empty content, oversized, and a path-traversal-style
filename. Per spec.md's Edge Cases, a path-traversal-style filename is NOT
rejected — the filename is never interpreted as a filesystem path and the
document is stored safely under a system-generated identifier regardless
of what filename is supplied, so that case asserts safe acceptance, not a
400.

Also (pre-Phase-5 security checkpoint, 2026-08-17): proves oversized
uploads are rejected by the bounded chunked reader in
`api/routers/documents.py` before any chunking/embedding/storage happens,
and that a valid file larger than one read-chunk (64 KiB) still round-trips
correctly through that same bounded-read loop.
"""

import uuid

import pytest
from sqlalchemy import func, select

from shiruno.config import get_settings
from shiruno.persistence.models import DocumentChunk, KnowledgeDocument
from tests.fixtures.admin import seed_admin_and_token


@pytest.mark.asyncio
async def test_non_txt_extension_is_rejected(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", b"tresc", "application/octet-stream")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_invalid_utf8_is_rejected(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("dokument.txt", b"\xff\xfe\x00invalid-utf8", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_empty_file_is_rejected(db_async_client, db_session, default_tenant) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("dokument.txt", b"", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_whitespace_only_file_is_rejected(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("dokument.txt", b"   \n\n   \n", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_oversized_file_is_rejected(
    db_async_client, db_session, default_tenant, monkeypatch
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "10")
    get_settings.cache_clear()

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("dokument.txt", b"to jest zdecydowanie za duzo bajtow", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    get_settings.cache_clear()  # restore before monkeypatch reverts, for subsequent tests

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_oversized_upload_rejected_without_processing_embedding_or_storing(
    db_async_client, db_session, default_tenant, fake_embedding_provider, monkeypatch
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "1000")
    get_settings.cache_clear()

    # Larger than both the 1000-byte limit and the 64 KiB bounded-read
    # chunk size, so the reader must reject mid-stream, not after fully
    # buffering.
    oversized_content = ("Zbyt duzo tresci Albertos. " * 5000).encode()
    assert len(oversized_content) > 100_000

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("duzy.txt", oversized_content, "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    get_settings.cache_clear()

    assert response.status_code == 413
    document_count = db_session.execute(
        select(func.count()).select_from(KnowledgeDocument)
    ).scalar_one()
    chunk_count = db_session.execute(select(func.count()).select_from(DocumentChunk)).scalar_one()
    assert document_count == 0
    assert chunk_count == 0
    assert fake_embedding_provider.embed_calls == []


@pytest.mark.asyncio
async def test_valid_file_larger_than_one_read_chunk_still_uploads(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    # ~100 KB, comfortably bigger than the 64 KiB bounded-read chunk size,
    # well under the default 5 MB MAX_UPLOAD_SIZE_BYTES.
    paragraph = "Albertos oferuje szeroki wybor produktow w dobrej cenie. "
    large_content = "\n\n".join([paragraph * 20] * 90).encode()
    assert len(large_content) > 100_000

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("duzy-poprawny.txt", large_content, "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"

    chunk_count = db_session.execute(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == uuid.UUID(body["id"]))
    ).scalar_one()
    assert chunk_count > 1


@pytest.mark.asyncio
async def test_path_traversal_style_filename_is_accepted_and_stored_safely(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)
    traversal_filename = "../../etc/passwd.txt"

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": (traversal_filename, b"Tresc dokumentu Albertos.", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    # System-generated UUID identifier, never derived from the filename.
    assert body["filename"] == traversal_filename
    assert len(body["id"]) == 36
