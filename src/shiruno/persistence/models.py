"""ORM models — data-model.md.

Multi-tenant per constitution Principle II (amended 2026-08-19, v4.0.0):
`Tenant` is a first-class security boundary. `Administrator`,
`KnowledgeDocument`, and `ConversationRecord` (feature
011-conversations-analytics) carry a required `tenant_id` FK — see feature
009-admin-platform-foundation's data-model.md and feature
011-conversations-analytics's data-model.md. `DocumentChunk`,
`UsageRecord`, and `RateLimitWindow` remain tenant-unaware (Principle II
Rule 10 — not retroactively tenant-owned; neither has an admin-facing
per-tenant view today).
"""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Fixed by the local intfloat/multilingual-e5-small model (research.md §4).
# Changing the configured model to a different output dimension requires a
# migration (data-model.md "Cross-cutting rules").
EMBEDDING_DIMENSIONS = 384


class Base(DeclarativeBase):
    pass


class DocumentStatus(enum.StrEnum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class ProviderKind(enum.StrEnum):
    """Distinguishes LLM (budget-counted) from embedding (operational-only,
    never budget-counted) usage — Design Constraint 3 / tasks.md T063."""

    llm = "llm"
    embedding = "embedding"


class ProviderName(enum.StrEnum):
    """Which concrete backend served a `UsageRecord` row — orthogonal to
    `ProviderKind` (feature 002-add-ollama-provider, data-model.md). Always
    populated, including on `embedding`-kind rows (today always the local
    `sentence-transformers` model, `local_sentence_transformer` — never
    `anthropic`/`ollama`, which are `llm`-kind-only values). Never inferred
    from `provider_model`'s free-text value — set explicitly by the caller
    from its own known-active backend, so `infra/budget.py`'s
    `provider_name='anthropic'` filter is a structural guarantee, not a
    string-matching heuristic (research.md §4)."""

    anthropic = "anthropic"
    ollama = "ollama"
    local_sentence_transformer = "local_sentence_transformer"


class TenantStatus(enum.StrEnum):
    active = "active"
    inactive = "inactive"


class Tenant(Base):
    """A customer of the Shiruno platform — first-class security boundary
    (constitution Principle II, feature 009-admin-platform-foundation).
    Albertos is tenant #1. No supported operation in this feature
    transitions `status` from `active` to `inactive` — see data-model.md.
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=TenantStatus.active,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("administrators.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=DocumentStatus.processing,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaces_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("knowledge_documents.id"), nullable=True
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "position", name="uq_document_chunks_document_id_position"),
        Index("ix_document_chunks_document_id", "document_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_documents.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # MUST match whatever EmbeddingProvider implementation is active
    # (FR-024) — currently intfloat/multilingual-e5-small, 384 dims.
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class UsageRecord(Base):
    """One row per LLM or embedding provider call (FR-047).

    `provider_kind` is the field the budget query (infra/budget.py, T063)
    filters on: only `llm` rows count toward the configured monetary/token
    budget. `embedding` rows are operational visibility only (Design
    Constraint 3) — local embedding calls have no per-call provider cost.
    """

    __tablename__ = "usage_records"
    __table_args__ = (Index("ix_usage_records_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    provider_kind: Mapped[ProviderKind] = mapped_column(
        Enum(ProviderKind, name="provider_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # NOT NULL from the start in this model definition — safe for a fresh
    # schema (`Base.metadata.create_all`, used by every test). The
    # corresponding Alembic migration against a database that may already
    # hold historical rows backfills deterministically before adding this
    # constraint (see alembic/versions/, data-model.md Migration).
    provider_name: Mapped[ProviderName] = mapped_column(
        Enum(ProviderName, name="provider_name", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    provider_model: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # NEW (feature 004-rag-answerability-and-ollama-performance,
    # data-model.md "UsageRecord (extended)"). Verbatim copy of
    # `LLMResult.provider_metrics` when a provider returns one — Ollama
    # populates `*_duration_ns` keys (native nanoseconds, no conversion);
    # Anthropic and every `embedding`-kind row leave this `NULL`. Written
    # exactly once, opaquely, by `_record_usage()` — no other layer reads
    # or branches on its keys (research.md §8).
    provider_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationOutcome(enum.StrEnum):
    """Mirrors `application.ask_question.Outcome` exactly (feature
    011-conversations-analytics, data-model.md)."""

    grounded = "grounded"
    insufficient_information = "insufficient_information"
    out_of_scope = "out_of_scope"
    unavailable = "unavailable"
    small_talk = "small_talk"


class FailureCategory(enum.StrEnum):
    """Only set when `ConversationRecord.outcome == unavailable`
    (research.md §5) — distinguishes *why* the assistant was unavailable
    without ever exposing raw provider exception detail."""

    provider_error = "provider_error"
    budget_exceeded = "budget_exceeded"
    kill_switch = "kill_switch"
    concurrency_limit = "concurrency_limit"


class ConversationRecord(Base):
    """A durable, tenant-owned record of one public chat request that
    reached one of the five outcomes above (feature
    011-conversations-analytics, data-model.md). Every operational field
    below is an immutable, at-write-time snapshot (research.md §2a) —
    never recomputed from current `KnowledgeDocument` state or current
    provider configuration, and never updated after creation.
    """

    __tablename__ = "conversation_records"
    __table_args__ = (
        Index("ix_conversation_records_tenant_id_created_at", "tenant_id", "created_at"),
        Index(
            "ix_conversation_records_tenant_id_outcome_created_at",
            "tenant_id",
            "outcome",
            "created_at",
        ),
        Index(
            "ix_conversation_records_tenant_id_normalized_question",
            "tenant_id",
            "normalized_question",
        ),
        UniqueConstraint("request_id", name="uq_conversation_records_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[ConversationOutcome] = mapped_column(
        Enum(
            ConversationOutcome,
            name="conversation_outcome",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    safe_failure_category: Mapped[FailureCategory | None] = mapped_column(
        Enum(
            FailureCategory,
            name="conversation_failure_category",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    provider_name: Mapped[ProviderName | None] = mapped_column(
        Enum(ProviderName, name="provider_name", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    provider_model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateLimitWindow(Base):
    """Postgres-backed fixed-window rate-limit counter (research.md §2)."""

    __tablename__ = "rate_limit_windows"
    __table_args__ = (PrimaryKeyConstraint("source_key", "window_start"),)

    source_key: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
