"""T065 (usage-accounting half) — contract test: a grounded
`POST /api/v1/chat` request writes one `embedding`-kind and one
`llm`-kind `UsageRecord` row with the fields research.md §3/FR-047
require (provider/model, token counts, success, latency, timestamp) and
none of the content FR-052/Principle IX forbid (no prompt/document/system-
instruction text, since `UsageRecord` has no such column at all).
"""

import uuid

import pytest
from sqlalchemy import select

from shiruno.domain.prompting import SYSTEM_PROMPT
from shiruno.persistence.models import (
    Administrator,
    DocumentChunk,
    DocumentStatus,
    KnowledgeDocument,
    ProviderKind,
    UsageRecord,
)
from shiruno.providers.llm.protocol import LLMResult


@pytest.mark.asyncio
async def test_grounded_chat_request_records_one_embedding_and_one_llm_usage_row(
    db_async_client, db_session, fake_embedding_provider
) -> None:
    question = "Jakie są godziny otwarcia biura Albertos?"
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x")
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="godziny.txt",
        uploaded_by_admin_id=admin.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            position=0,
            content="Biuro Albertos jest otwarte od poniedziałku do piątku.",
            embedding=fake_embedding_provider.embed_query(question),
        )
    )
    db_session.flush()

    response = await db_async_client.post("/api/v1/chat", json={"question": question})
    assert response.status_code == 200

    rows = db_session.execute(select(UsageRecord)).scalars().all()
    by_kind = {row.provider_kind: row for row in rows}

    assert ProviderKind.embedding in by_kind
    embedding_row = by_kind[ProviderKind.embedding]
    assert embedding_row.success is True
    assert embedding_row.latency_ms >= 0
    assert embedding_row.provider_model

    assert ProviderKind.llm in by_kind
    llm_row = by_kind[ProviderKind.llm]
    assert llm_row.success is True
    assert llm_row.input_tokens is not None
    assert llm_row.output_tokens is not None
    assert llm_row.latency_ms >= 0
    assert llm_row.provider_model

    for row in rows:
        assert question not in str(row.provider_model)
        assert SYSTEM_PROMPT not in str(row.provider_model)


@pytest.mark.asyncio
async def test_out_of_scope_request_records_no_usage_rows(db_async_client, db_session) -> None:
    response = await db_async_client.post(
        "/api/v1/chat", json={"question": "Napisz mi krótki wiersz o wiośnie."}
    )
    assert response.status_code == 200

    rows = db_session.execute(select(UsageRecord)).scalars().all()
    assert rows == []


# --- Feature 004-rag-answerability-and-ollama-performance, User Story 3
# (research.md §8, data-model.md "UsageRecord (extended)"):
# `provider_metrics` is persisted opaquely, verbatim from whatever
# `LLMResult.provider_metrics` the provider returned. ---


@pytest.mark.asyncio
async def test_llm_usage_row_persists_provider_metrics_verbatim(
    db_async_client, db_session, fake_llm_provider, fake_embedding_provider
) -> None:
    question = "Jakie są godziny otwarcia biura Albertos?"
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x")
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="godziny.txt",
        uploaded_by_admin_id=admin.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            position=0,
            content="Biuro Albertos jest otwarte od poniedziałku do piątku.",
            embedding=fake_embedding_provider.embed_query(question),
        )
    )
    db_session.flush()

    fake_llm_provider.response = LLMResult(
        answer="Biuro jest otwarte od poniedziałku do piątku.",
        supported=True,
        model="qwen3:4b",
        input_tokens=20,
        output_tokens=12,
        latency_ms=7,
        provider_metrics={
            "total_duration_ns": 1_000_000_000,
            "load_duration_ns": 200_000_000,
            "prompt_eval_duration_ns": 50_000_000,
            "eval_duration_ns": 750_000_000,
        },
    )

    response = await db_async_client.post("/api/v1/chat", json={"question": question})
    assert response.status_code == 200

    llm_row = (
        db_session.execute(select(UsageRecord).where(UsageRecord.provider_kind == ProviderKind.llm))
        .scalars()
        .one()
    )
    assert llm_row.provider_metrics == {
        "total_duration_ns": 1_000_000_000,
        "load_duration_ns": 200_000_000,
        "prompt_eval_duration_ns": 50_000_000,
        "eval_duration_ns": 750_000_000,
    }


@pytest.mark.asyncio
async def test_llm_usage_row_provider_metrics_is_null_when_provider_reports_none(
    db_async_client, db_session, fake_embedding_provider
) -> None:
    """The default `FakeLLMProvider` response (and, in practice, every
    Anthropic-backed call) has `provider_metrics=None` — the column must
    stay `NULL`, never a fabricated/empty dict (FR-019)."""
    question = "Jakie są godziny otwarcia biura Albertos?"
    admin = Administrator(username=f"seed-{uuid.uuid4()}", password_hash="x")
    db_session.add(admin)
    db_session.flush()
    document = KnowledgeDocument(
        original_filename="godziny.txt",
        uploaded_by_admin_id=admin.id,
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            position=0,
            content="Biuro Albertos jest otwarte od poniedziałku do piątku.",
            embedding=fake_embedding_provider.embed_query(question),
        )
    )
    db_session.flush()

    response = await db_async_client.post("/api/v1/chat", json={"question": question})
    assert response.status_code == 200

    llm_row = (
        db_session.execute(select(UsageRecord).where(UsageRecord.provider_kind == ProviderKind.llm))
        .scalars()
        .one()
    )
    assert llm_row.provider_metrics is None
