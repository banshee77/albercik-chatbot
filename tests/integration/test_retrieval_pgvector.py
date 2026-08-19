"""T031 — integration test for real pgvector-backed retrieval
(persistence/repositories.py, T036) against `db-test`. Verifies cosine
similarity ordering, Top-K limiting, relevance-threshold filtering
(combined with domain/retrieval.py), source metadata, and soft-delete
exclusion — seeding chunks with `FakeEmbeddingProvider` vectors, never the
real `sentence-transformers` model (research.md §6, §8; Design
Constraint 2).
"""

import uuid
from datetime import UTC, datetime

import pytest

from shiruno.domain.retrieval import select_sufficient_chunks
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    Tenant,
)
from shiruno.persistence.repositories import search_similar_chunks
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider


def _seed_document(db_session, *, filename: str, deleted: bool = False) -> KnowledgeDocument:
    tenant = Tenant(name=f"Tenant {uuid.uuid4()}", slug=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    db_session.flush()
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x", tenant_id=tenant.id)
    db_session.add(admin)
    db_session.flush()

    document = KnowledgeDocument(
        original_filename=filename,
        uploaded_by_admin_id=admin.id,
        tenant_id=tenant.id,
        status=DocumentStatus.ready,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db_session.add(document)
    db_session.flush()
    return document


def _add_chunk(
    db_session, document: KnowledgeDocument, *, position: int, content: str, embedding: list[float]
) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document.id, position=position, content=content, embedding=embedding
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk


def test_cosine_similarity_orders_most_relevant_first(db_session) -> None:
    provider = FakeEmbeddingProvider()
    query_vector = provider.embed_query("pytanie testowe o Albertos")

    document = _seed_document(db_session, filename="doc.txt")
    _add_chunk(
        db_session, document, position=0, content="dokladne dopasowanie", embedding=query_vector
    )
    _add_chunk(
        db_session,
        document,
        position=1,
        content="inny fragment A",
        embedding=provider.embed_passages(["zupelnie inny tekst A"])[0],
    )
    _add_chunk(
        db_session,
        document,
        position=2,
        content="inny fragment B",
        embedding=provider.embed_passages(["zupelnie inny tekst B"])[0],
    )

    results = search_similar_chunks(db_session, query_vector, top_k=10)

    assert results[0].content == "dokladne dopasowanie"
    assert results[0].similarity == pytest.approx(1.0, abs=1e-6)
    similarities = [r.similarity for r in results]
    assert similarities == sorted(similarities, reverse=True)


def test_top_k_limits_result_count(db_session) -> None:
    provider = FakeEmbeddingProvider()
    document = _seed_document(db_session, filename="doc.txt")
    for i in range(5):
        _add_chunk(
            db_session,
            document,
            position=i,
            content=f"fragment {i}",
            embedding=provider.embed_passages([f"tekst {i}"])[0],
        )

    results = search_similar_chunks(db_session, provider.embed_query("dowolne pytanie"), top_k=3)

    assert len(results) == 3


def test_relevance_threshold_filters_low_similarity_chunks(db_session) -> None:
    provider = FakeEmbeddingProvider()
    query_vector = provider.embed_query("pytanie o Albertos")

    document = _seed_document(db_session, filename="doc.txt")
    _add_chunk(db_session, document, position=0, content="trafny fragment", embedding=query_vector)
    _add_chunk(
        db_session,
        document,
        position=1,
        content="nietrafny fragment",
        embedding=provider.embed_passages(["cos zupelnie innego"])[0],
    )

    candidates = search_similar_chunks(db_session, query_vector, top_k=10)
    # Matches config.py's interim RETRIEVAL_RELEVANCE_THRESHOLD default
    # (Phase 3 calibration checkpoint) — see that setting's docstring for
    # what this threshold does and does not prove.
    grounding = select_sufficient_chunks(candidates, relevance_threshold=0.80)

    assert len(grounding) == 1
    assert grounding[0].content == "trafny fragment"


def test_source_metadata_survives_retrieval(db_session) -> None:
    provider = FakeEmbeddingProvider()
    document = _seed_document(db_session, filename="albertos-fakty.txt")
    vector = provider.embed_query("fakt o Albertos")
    _add_chunk(db_session, document, position=0, content="fakt o Albertos", embedding=vector)

    results = search_similar_chunks(db_session, vector, top_k=10)

    assert results[0].document_id == document.id
    assert results[0].document_label == "albertos-fakty.txt"


def test_soft_deleted_documents_excluded_from_retrieval(db_session) -> None:
    provider = FakeEmbeddingProvider()
    query_vector = provider.embed_query("pytanie")

    deleted_document = _seed_document(db_session, filename="usuniety.txt", deleted=True)
    _add_chunk(
        db_session, deleted_document, position=0, content="usunieta tresc", embedding=query_vector
    )

    results = search_similar_chunks(db_session, query_vector, top_k=10)

    assert results == []
