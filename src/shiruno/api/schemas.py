"""Pydantic request/response models — mirrors contracts/openapi.yaml."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shiruno.config import get_settings


class ChatRequest(BaseModel):
    # extra="forbid" (Phase 5, T061, FR-035): a client cannot smuggle a
    # model/max-tokens/system-prompt/etc. override into the body — an
    # unknown field fails validation outright (400) instead of being
    # silently ignored. `question` is, and stays, the only field this
    # endpoint accepts from a caller.
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def _enforce_configured_max_length(cls, value: str) -> str:
        # Read dynamically (not a fixed Field(max_length=...)) so the
        # limit tracks settings.MAX_QUESTION_LENGTH_CHARS at request time,
        # per contracts/openapi.yaml and Phase 5's "question length
        # validation" pipeline step (tasks.md T057) — this is pure,
        # side-effect-free Pydantic validation, so it always runs before
        # the route body (and therefore before rate limiting, the kill
        # switch, budget, etc.) regardless of dependency resolution order.
        limit = get_settings().MAX_QUESTION_LENGTH_CHARS
        if len(value) > limit:
            raise ValueError(f"question must be at most {limit} characters.")
        return value


class SourceReferenceOut(BaseModel):
    document_id: uuid.UUID
    label: str


class ChatResponse(BaseModel):
    outcome: Literal[
        "grounded", "insufficient_information", "out_of_scope", "unavailable", "small_talk"
    ]
    answer: str
    sources: list[SourceReferenceOut] = Field(default_factory=list)
    # Correlation id for this request, also stored on the corresponding
    # `usage_records` row — non-sensitive, enables dev tooling (e.g.
    # scripts/run_eval.py) to look up per-request token/latency/telemetry
    # data without exposing it directly in this public response
    # (contracts/chat-endpoint-delta.md, feature
    # 004-rag-answerability-and-ollama-performance).
    request_id: uuid.UUID


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class DocumentSummary(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    status: Literal["processing", "ready", "failed"]
    uploaded_at: datetime
    updated_at: datetime
    indexed_at: datetime | None
    error_message: str | None


class DocumentCountsOut(BaseModel):
    total: int
    ready: int
    processing: int
    failed: int


class KnowledgeHealthResponse(BaseModel):
    documents: DocumentCountsOut
    chunks: int
    ready_for_chat: bool
    last_indexed_at: datetime | None


class AdministratorOut(BaseModel):
    """Safe administrator identity fields only — never a password hash or
    token internal (feature 009-admin-platform-foundation, FR-020)."""

    id: uuid.UUID
    username: str


class TenantOut(BaseModel):
    """Safe tenant identity fields only, and always the caller's own
    tenant — never another tenant's (FR-019)."""

    id: uuid.UUID
    name: str
    slug: str


class AdminMeResponse(BaseModel):
    administrator: AdministratorOut
    tenant: TenantOut


_ConversationOutcomeLiteral = Literal[
    "grounded", "insufficient_information", "out_of_scope", "unavailable", "small_talk"
]


class ConversationSummary(BaseModel):
    """Lightweight list item (feature 011-conversations-analytics,
    contracts/conversations-api.md) — deliberately excludes answer/sources/
    provider detail, which only the detail endpoint exposes."""

    id: uuid.UUID
    request_id: uuid.UUID
    question: str
    outcome: _ConversationOutcomeLiteral
    created_at: datetime
    latency_ms: int


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int


class SourceSnapshotOut(BaseModel):
    document_id: uuid.UUID
    label: str


class ConversationDetail(BaseModel):
    """Full detail (feature 011-conversations-analytics, US2,
    contracts/conversations-api.md). Every field is an immutable,
    at-write-time snapshot (research.md §2a) — never reconstructed from
    current `KnowledgeDocument` state or current provider configuration."""

    id: uuid.UUID
    request_id: uuid.UUID
    question: str
    answer: str
    outcome: _ConversationOutcomeLiteral
    created_at: datetime
    latency_ms: int
    sources: list[SourceSnapshotOut] | None
    provider_name: str | None
    provider_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    provider_metrics: dict | None
    safe_failure_category: (
        Literal["provider_error", "budget_exceeded", "kill_switch", "concurrency_limit"] | None
    )


class DateRangeOut(BaseModel):
    start: datetime
    end: datetime


class OutcomeStatsOut(BaseModel):
    count: int
    rate: float


class OutcomeBreakdownOut(BaseModel):
    grounded: OutcomeStatsOut
    insufficient_information: OutcomeStatsOut
    out_of_scope: OutcomeStatsOut
    unavailable: OutcomeStatsOut
    small_talk: OutcomeStatsOut


class LatencyStatsOut(BaseModel):
    average: float | None
    p50: float | None
    p95: float | None


class TokenTotalsOut(BaseModel):
    input_total: int
    output_total: int


class ProviderUsageOut(BaseModel):
    provider_name: str
    provider_model: str
    request_count: int
    input_tokens: int
    output_tokens: int


class AnalyticsSummaryResponse(BaseModel):
    range: DateRangeOut
    total_requests: int
    outcomes: OutcomeBreakdownOut
    latency_ms: LatencyStatsOut
    tokens: TokenTotalsOut
    providers: list[ProviderUsageOut]


class QuestionFrequencyItem(BaseModel):
    """Shared shape for both knowledge-gaps (US4) and most-common-questions
    (US5) — identical fields, different grouping filter (research.md §6)."""

    normalized_question: str
    example_question: str
    count: int
    last_seen_at: datetime


class KnowledgeGapsResponse(BaseModel):
    range: DateRangeOut
    items: list[QuestionFrequencyItem]
