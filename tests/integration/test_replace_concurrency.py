"""T020 — proves the row-level lock in `replace_document.py` (feature
010-knowledge-base-admin, US3, research.md §3, data-model.md's
"Concurrency invariant"): two concurrent replace requests for the same
predecessor can never both end up with an active successor.

Drives two genuine, concurrent `replace_document()` calls, each on its own
`Session`/connection against the real `db-test` Postgres instance (not the
shared, never-committing `db_session` fixture — two separate connections
must actually contend for the same row's lock), synchronized with a
`threading.Barrier` so both requests reach `replace_document()` at
essentially the same instant. Because `replace_document()` never commits
(only flushes — committing is the caller's job, matching this codebase's
`get_session()` convention), the winning thread's transaction — and its
row lock — stays open for real wall-clock time until this test calls
`session.commit()`, so the losing thread's `SELECT ... FOR UPDATE` must
genuinely block on Postgres's own lock, not merely observe a value that
happened to already be updated.
"""

import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from shiruno.application.replace_document import RACE_LOSS_MESSAGE, replace_document
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    Tenant,
)
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider


def test_two_concurrent_replace_requests_exactly_one_wins(db_engine) -> None:
    session_factory = sessionmaker(bind=db_engine)

    setup_session = session_factory()
    tenant = Tenant(name=f"Concurrency Tenant {uuid.uuid4()}", slug=f"concurrency-{uuid.uuid4()}")
    setup_session.add(tenant)
    setup_session.flush()
    admin = Administrator(
        username=f"concurrency-admin-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id
    )
    setup_session.add(admin)
    setup_session.flush()
    predecessor = KnowledgeDocument(
        original_filename="predecessor.txt",
        uploaded_by_admin_id=admin.id,
        tenant_id=tenant.id,
        status=DocumentStatus.ready,
        indexed_at=datetime.now(UTC),
    )
    setup_session.add(predecessor)
    setup_session.flush()
    setup_session.add(
        DocumentChunk(
            document_id=predecessor.id,
            position=0,
            content="Oryginalna, aktywna tresc.",
            embedding=[0.0] * 384,
        )
    )
    setup_session.commit()
    predecessor_id = predecessor.id
    tenant_id = tenant.id
    admin_id = admin.id
    setup_session.close()

    results: dict[str, tuple[uuid.UUID, DocumentStatus, str | None]] = {}
    errors: dict[str, BaseException] = {}
    barrier = threading.Barrier(2)

    def run_replace(name: str, filename: str, content: bytes) -> None:
        session = session_factory()
        try:
            uploaded_by = session.get(Administrator, admin_id)
            assert uploaded_by is not None
            barrier.wait()
            successor = replace_document(
                predecessor_id,
                filename=filename,
                content_bytes=content,
                session=session,
                embedding_provider=FakeEmbeddingProvider(),
                uploaded_by=uploaded_by,
                tenant_id=tenant_id,
                max_upload_size_bytes=5_000_000,
                chunk_size_chars=1000,
                chunk_overlap_chars=150,
                embedding_model_name="test-model",
            )
            results[name] = (successor.id, successor.status, successor.safe_error_message)
            session.commit()
        except BaseException as exc:  # noqa: BLE001 - surfaced via assertion below
            errors[name] = exc
            session.rollback()
        finally:
            session.close()

    thread_a = threading.Thread(target=run_replace, args=("a", "a.txt", b"Nowa tresc A."))
    thread_b = threading.Thread(target=run_replace, args=("b", "b.txt", b"Nowa tresc B."))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=15)
    thread_b.join(timeout=15)

    try:
        assert not errors, f"replace_document raised in a thread: {errors}"
        assert set(results) == {"a", "b"}

        statuses = [status for _, status, _ in results.values()]
        assert statuses.count(DocumentStatus.ready) == 1
        assert statuses.count(DocumentStatus.failed) == 1

        winner = next(r for r in results.values() if r[1] == DocumentStatus.ready)
        loser = next(r for r in results.values() if r[1] == DocumentStatus.failed)
        assert loser[2] == RACE_LOSS_MESSAGE

        verify_session = session_factory()
        try:
            refreshed_predecessor = verify_session.get(KnowledgeDocument, predecessor_id)
            assert refreshed_predecessor is not None
            assert refreshed_predecessor.deleted_at is not None

            refreshed_winner = verify_session.get(KnowledgeDocument, winner[0])
            assert refreshed_winner is not None
            assert refreshed_winner.status == DocumentStatus.ready
            assert refreshed_winner.deleted_at is None

            refreshed_loser = verify_session.get(KnowledgeDocument, loser[0])
            assert refreshed_loser is not None
            assert refreshed_loser.status == DocumentStatus.failed

            # The loser's chunks (if ingestion itself produced any before
            # the lock decided it lost) must never be retrievable — the
            # status == ready filter (research.md §1) already guarantees
            # this structurally, but assert directly on this document's
            # own status as the proof, since it can never be `ready`.
            assert refreshed_loser.status != DocumentStatus.ready
        finally:
            verify_session.close()
    finally:
        cleanup_session = session_factory()
        try:
            document_ids = [predecessor_id, *[r[0] for r in results.values()]]
            cleanup_session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids))
            )
            cleanup_session.execute(
                delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids))
            )
            cleanup_session.execute(delete(Administrator).where(Administrator.id == admin_id))
            cleanup_session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            cleanup_session.commit()
        finally:
            cleanup_session.close()
