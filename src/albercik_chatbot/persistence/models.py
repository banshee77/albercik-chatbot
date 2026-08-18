"""ORM models — data-model.md.

Single-tenant per constitution Principle II: no `organization_id` or tenant
column appears anywhere below.
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


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("administrators.id"), nullable=False
    )
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateLimitWindow(Base):
    """Postgres-backed fixed-window rate-limit counter (research.md §2)."""

    __tablename__ = "rate_limit_windows"
    __table_args__ = (PrimaryKeyConstraint("source_key", "window_start"),)

    source_key: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
