"""User Story 1 core use case (T037), extended by Phase 5 / User Story 3
(T065) with the full public-endpoint cost/abuse pipeline (research.md
§2-3,7; tasks.md T054-T068):

    rate limit -> LLM kill switch -> budget check -> concurrency guard ->
    small-talk classification -> scope evaluation -> embedding/retrieval ->
    context size limit -> LLM call -> usage accounting

(feature 007-conversational-chat-ux, research.md §4: small-talk
classification runs after every existing safeguard above, unchanged, and
before scope evaluation — a matched message short-circuits with the
additive `small_talk` outcome and never reaches embedding/retrieval/the
LLM at all.)

("HTTP/payload validation" and "question length validation" happen
earlier, before this function is ever called — request-body-size in
`api/deps.py::require_bounded_request_body` and question length in
`api/schemas.py::ChatRequest`'s dynamic validator, both of which FastAPI
guarantees run before a route/application function's own code.)

This entire sequence is implemented as one strictly-ordered imperative
function rather than a chain of independent FastAPI dependencies:
FastAPI resolves ALL `Depends()` for a route before it validates/parses
the request body, and does not otherwise guarantee relative ordering
across independent dependencies — neither guarantee is strong enough to
reproduce the specific order the cost/abuse pipeline requires. Doing it
here, in plain sequential code, makes that order a simple, obviously
correct fact about the source rather than something dependent on
framework internals.

No retry loop here — retries belong solely to `AnthropicLLMProvider`
(Design Constraint 1, tasks.md). Out-of-scope and insufficient-information
outcomes never reach the LLM at all: both are domain decisions made by
this application before any provider call, which is both cheaper
(Principle X) and structurally guarantees FR-028/FR-030 ("does not invent
an answer" / "does not answer the underlying question") rather than
relying on the model to follow that instruction.

Feature 011-conversations-analytics (research.md §5) additionally surfaces
`provider_name`/`provider_model`/`input_tokens`/`output_tokens`/
`provider_metrics`/`failure_category` on `AskQuestionResult` — data this
function already computes internally for `_record_usage()`/the budget
check, now also returned so `record_conversation()` can snapshot it onto a
`ConversationRecord`. No new decision logic: each field is populated with
whatever is actually known at that return site, `None` otherwise.

Feature 012-rag-observability (research.md R5-R7) adds a `tracer:
Tracer` parameter and wraps each stage boundary above in
`infra.observability.traced_stage()`, purely additively: every
`traced_stage()` call is a structural no-op when tracing is disabled
(research.md R1), and no branch, return value, or outcome below depends on
whether `tracer` is a real or no-op `Tracer` (FR-034). The one exception to
"span boundaries mirror the list above exactly" is `security_or_cost_gates`
vs. the concurrency guard: a concurrency-limit rejection is deliberately
NOT given its own child span (see the inline comment at that call site) to
avoid either re-opening an already-closed span or acquiring the
concurrency slot earlier than this code already does — the latter would
change request-rejection behavior under load, which tracing must never do.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from opentelemetry.trace import StatusCode, Tracer
from sqlalchemy.orm import Session

from shiruno.api.errors import RateLimitedError
from shiruno.domain.prompting import SourceReference, assemble_prompt, extract_sources
from shiruno.domain.retrieval import limit_context_chars, select_sufficient_chunks
from shiruno.domain.scope import is_albertos_scope
from shiruno.domain.small_talk import classify_small_talk, small_talk_reply
from shiruno.infra.budget import check_llm_budget
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.infra.observability import safe_set_attribute, safe_set_status, traced_stage
from shiruno.infra.rate_limit import check_and_increment
from shiruno.persistence.models import ProviderKind, ProviderName, UsageRecord
from shiruno.persistence.repositories import search_similar_chunks
from shiruno.providers.embedding.protocol import EmbeddingProvider
from shiruno.providers.llm.protocol import LLMProvider, LLMProviderError

Outcome = Literal[
    "grounded", "insufficient_information", "out_of_scope", "unavailable", "small_talk"
]
FailureCategory = Literal["provider_error", "budget_exceeded", "kill_switch", "concurrency_limit"]

_OUT_OF_SCOPE_MESSAGE = (
    "Odpowiadam wyłącznie na pytania związane z Albertos. Nie mogę pomóc z tym pytaniem."
)
_INSUFFICIENT_INFORMATION_MESSAGE = (
    "Nie mam wystarczających informacji w bazie wiedzy Albertos, aby odpowiedzieć na to pytanie."
)
_UNAVAILABLE_MESSAGE = "Chatbot jest obecnie niedostępny. Spróbuj ponownie później."


@dataclass(frozen=True)
class AskQuestionResult:
    outcome: Outcome
    answer: str
    sources: list[SourceReference] = field(default_factory=list)
    # Feature 011-conversations-analytics additions below — all optional,
    # populated only when real data exists for this specific request
    # (research.md §5). Never influences `outcome`/`answer`/`sources`
    # above; purely additive surface area for conversation recording.
    provider_name: str | None = None
    provider_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_metrics: dict[str, int] | None = None
    failure_category: FailureCategory | None = None


@dataclass(frozen=True)
class ChatSafetyConfig:
    """Server-controlled cost/abuse settings for one `/chat` request. Never
    influenced by request-body content (FR-035) — every field here is
    sourced exclusively from `config.Settings` by the caller (`chat.py`)."""

    rate_limit_per_minute: int
    llm_enabled: bool
    budget_max_llm_requests_per_hour: int
    max_context_chars: int
    # Feature 012-rag-observability (research.md R4, FR-017): two
    # independent, off-by-default content-capture toggles, threaded
    # through the same way every other safety setting is — never read
    # directly from `get_settings()` inside this module.
    capture_question_answer_content: bool = False
    capture_document_prompt_content: bool = False


def _record_usage(
    session: Session,
    *,
    request_id: uuid.UUID,
    provider_kind: ProviderKind,
    provider_name: ProviderName,
    provider_model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    success: bool,
    latency_ms: int,
    provider_metrics: dict[str, int] | None = None,
) -> None:
    # Deliberately only these fields: no prompt/question/document/system-
    # instruction text is ever passed in here, and `UsageRecord` has no
    # column that could hold it even by mistake (FR-052, Principle IX).
    # `provider_metrics` is threaded through opaquely — this function never
    # reads or branches on its keys (research.md §8); it is whatever
    # `LLMResult.provider_metrics` the provider returned, or `None`.
    session.add(
        UsageRecord(
            request_id=request_id,
            provider_kind=provider_kind,
            provider_name=provider_name,
            provider_model=provider_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
            latency_ms=latency_ms,
            provider_metrics=provider_metrics,
        )
    )
    session.flush()


def ask_question(
    question: str,
    *,
    session: Session,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    top_k: int,
    relevance_threshold: float,
    max_answer_tokens: int,
    embedding_model_name: str,
    llm_model_name: str,
    llm_provider_name: str,
    safety: ChatSafetyConfig,
    rate_limit_source_key: str,
    concurrency_guard: ChatConcurrencyGuard,
    request_id: uuid.UUID,
    tracer: Tracer,
) -> AskQuestionResult:
    # --- rate limit + LLM kill switch + budget (fail closed) ---
    with traced_stage(tracer, "shiruno.security_or_cost_gates") as gates_span:
        rate_result = check_and_increment(
            session, source_key=rate_limit_source_key, limit_per_minute=safety.rate_limit_per_minute
        )
        if not rate_result.allowed:
            safe_set_status(gates_span, StatusCode.ERROR, "rate_limited")
            raise RateLimitedError(headers={"Retry-After": str(rate_result.retry_after_seconds)})

        budget_result = check_llm_budget(
            session,
            llm_enabled=safety.llm_enabled,
            llm_provider_name=llm_provider_name,
            max_requests_per_hour=safety.budget_max_llm_requests_per_hour,
        )
        if not budget_result.allowed:
            safe_set_status(gates_span, StatusCode.ERROR, budget_result.reason)
            return AskQuestionResult(
                outcome="unavailable",
                answer=_UNAVAILABLE_MESSAGE,
                failure_category=budget_result.reason,
            )

    # --- concurrency guard (paid LLM calls) ---
    # See module docstring: a concurrency-limit rejection is reflected only
    # via the root shiruno.chat span's shiruno.failure_category attribute
    # (chat.py), not a dedicated child span here.
    with concurrency_guard.try_acquire() as acquired:
        if not acquired:
            return AskQuestionResult(
                outcome="unavailable",
                answer=_UNAVAILABLE_MESSAGE,
                failure_category="concurrency_limit",
            )

        # --- small-talk short-circuit (feature 007; must run after every
        # safeguard above, unchanged, and before scope/retrieval/LLM) ---
        with traced_stage(tracer, "shiruno.small_talk_classification") as small_talk_span:
            small_talk_category = classify_small_talk(question)
            safe_set_attribute(
                small_talk_span, "shiruno.small_talk", small_talk_category is not None
            )
        if small_talk_category is not None:
            return AskQuestionResult(
                outcome="small_talk", answer=small_talk_reply(small_talk_category)
            )

        # --- scope evaluation ---
        with traced_stage(tracer, "shiruno.scope_classification") as scope_span:
            in_scope = is_albertos_scope(question)
            safe_set_attribute(scope_span, "shiruno.in_scope", in_scope)
        if not in_scope:
            return AskQuestionResult(outcome="out_of_scope", answer=_OUT_OF_SCOPE_MESSAGE)

        # --- embedding / retrieval ---
        embed_start = time.monotonic()
        with traced_stage(tracer, "shiruno.query_embedding") as embedding_span:
            safe_set_attribute(
                embedding_span,
                "shiruno.embedding.provider",
                ProviderName.local_sentence_transformer.value,
            )
            safe_set_attribute(embedding_span, "shiruno.embedding.model", embedding_model_name)
            safe_set_attribute(embedding_span, "shiruno.embedding.text_count", 1)
            query_embedding = embedding_provider.embed_query(question)
        embed_latency_ms = int((time.monotonic() - embed_start) * 1000)
        # One row for this batched passage-embedding call (T065) —
        # operational visibility only (Design Constraint 3): local
        # embedding calls have no per-call provider cost and MUST NEVER be
        # counted toward, or reduce, the LLM budget (infra/budget.py only
        # ever queries provider_kind='llm' rows).
        _record_usage(
            session,
            request_id=request_id,
            provider_kind=ProviderKind.embedding,
            # Always the local sentence-transformers model, regardless of
            # which LLM backend is configured — embeddings are not
            # affected by LLM_PROVIDER at all (spec: "Do not add Ollama
            # embeddings"; Design Constraint 3).
            provider_name=ProviderName.local_sentence_transformer,
            provider_model=embedding_model_name,
            input_tokens=None,
            output_tokens=None,
            success=True,
            latency_ms=embed_latency_ms,
        )

        with traced_stage(tracer, "shiruno.retrieval") as retrieval_span:
            safe_set_attribute(retrieval_span, "shiruno.retrieval.top_k", top_k)
            safe_set_attribute(
                retrieval_span, "shiruno.retrieval.relevance_threshold", relevance_threshold
            )
            candidates = search_similar_chunks(session, query_embedding, top_k=top_k)
            grounding_chunks = select_sufficient_chunks(
                candidates, relevance_threshold=relevance_threshold
            )
            safe_set_attribute(retrieval_span, "shiruno.retrieval.candidate_count", len(candidates))
            safe_set_attribute(
                retrieval_span, "shiruno.retrieval.passed_filter_count", len(grounding_chunks)
            )
            safe_set_attribute(
                retrieval_span,
                "shiruno.retrieval.selected.document_ids",
                [str(chunk.document_id) for chunk in grounding_chunks],
            )
            safe_set_attribute(
                retrieval_span,
                "shiruno.retrieval.selected.similarities",
                [chunk.similarity for chunk in grounding_chunks],
            )
            safe_set_attribute(
                retrieval_span,
                "shiruno.retrieval.selected.labels",
                [chunk.document_label for chunk in grounding_chunks],
            )
            if safety.capture_document_prompt_content:
                safe_set_attribute(
                    retrieval_span,
                    "shiruno.retrieval.selected.contents",
                    [chunk.content for chunk in grounding_chunks],
                )

        if not grounding_chunks:
            return AskQuestionResult(
                outcome="insufficient_information", answer=_INSUFFICIENT_INFORMATION_MESSAGE
            )

        # --- context size limit (before the LLM call) ---
        with traced_stage(tracer, "shiruno.context_assembly") as context_span:
            limited_chunks = limit_context_chars(
                grounding_chunks, max_context_chars=safety.max_context_chars
            )
            prompt = assemble_prompt(question, limited_chunks)
            safe_set_attribute(
                context_span,
                "shiruno.context.truncated",
                len(limited_chunks) < len(grounding_chunks),
            )
            safe_set_attribute(
                context_span, "shiruno.context.selected_chunk_count", len(limited_chunks)
            )
            safe_set_attribute(
                context_span,
                "shiruno.context.char_count",
                sum(len(chunk.content) for chunk in limited_chunks),
            )
            if safety.capture_document_prompt_content:
                safe_set_attribute(context_span, "shiruno.context.prompt", prompt.system_prompt)

        # --- LLM call ---
        llm_start = time.monotonic()
        with traced_stage(tracer, "shiruno.llm_generation") as llm_span:
            safe_set_attribute(llm_span, "shiruno.llm.provider", llm_provider_name)
            safe_set_attribute(llm_span, "shiruno.llm.model", llm_model_name)
            try:
                result = llm_provider.complete(
                    system_prompt=prompt.system_prompt,
                    user_message=prompt.user_message,
                    max_tokens=max_answer_tokens,
                )
            except LLMProviderError:
                safe_set_status(llm_span, StatusCode.ERROR, "provider_error")
                _record_usage(
                    session,
                    request_id=request_id,
                    provider_kind=ProviderKind.llm,
                    provider_name=ProviderName(llm_provider_name),
                    provider_model=llm_model_name,
                    input_tokens=None,
                    output_tokens=None,
                    success=False,
                    latency_ms=int((time.monotonic() - llm_start) * 1000),
                )
                return AskQuestionResult(
                    outcome="unavailable",
                    answer=_UNAVAILABLE_MESSAGE,
                    failure_category="provider_error",
                    provider_name=llm_provider_name,
                    provider_model=llm_model_name,
                )

            safe_set_attribute(llm_span, "shiruno.llm.model", result.model)
            safe_set_attribute(llm_span, "shiruno.llm.supported", result.supported)
            safe_set_attribute(llm_span, "shiruno.llm.latency_ms", result.latency_ms)
            if result.input_tokens is not None:
                safe_set_attribute(llm_span, "shiruno.llm.input_tokens", result.input_tokens)
            if result.output_tokens is not None:
                safe_set_attribute(llm_span, "shiruno.llm.output_tokens", result.output_tokens)
            for key, value in (result.provider_metrics or {}).items():
                safe_set_attribute(llm_span, f"shiruno.llm.provider_metrics.{key}", value)
            if safety.capture_question_answer_content and result.supported:
                safe_set_attribute(llm_span, "shiruno.llm.answer", result.answer)

        # --- usage accounting ---
        _record_usage(
            session,
            request_id=request_id,
            provider_kind=ProviderKind.llm,
            provider_name=ProviderName(llm_provider_name),
            provider_model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            success=True,
            latency_ms=result.latency_ms,
            provider_metrics=result.provider_metrics,
        )

        if not result.supported:
            # A genuine, successfully-parsed "the context does not support
            # an answer" decision (FR-001/FR-003) — `result.answer`'s
            # content is deliberately never surfaced here, even though the
            # model produced text; a malformed/unparseable structured
            # response never reaches this branch at all, since the
            # provider raises `LLMProviderError` for that case instead
            # (handled above), never a `LLMResult(supported=False, ...)`.
            #
            # A real LLM call genuinely happened here (unlike the
            # zero-chunk insufficient_information branch above), so real
            # provider/token data exists — it is returned honestly rather
            # than suppressed, since real cost was incurred either way
            # (feature 011-conversations-analytics, research.md §5).
            return AskQuestionResult(
                outcome="insufficient_information",
                answer=_INSUFFICIENT_INFORMATION_MESSAGE,
                provider_name=llm_provider_name,
                provider_model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                provider_metrics=result.provider_metrics,
            )

        return AskQuestionResult(
            outcome="grounded",
            answer=result.answer,
            sources=extract_sources(limited_chunks),
            provider_name=llm_provider_name,
            provider_model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            provider_metrics=result.provider_metrics,
        )
