"""User Story 1 core use case (T037), extended by Phase 5 / User Story 3
(T065) with the full public-endpoint cost/abuse pipeline (research.md
§2-3,7; tasks.md T054-T068):

    rate limit -> LLM kill switch -> budget check -> concurrency guard ->
    scope evaluation -> embedding/retrieval -> context size limit ->
    LLM call -> usage accounting

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
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from albercik_chatbot.api.errors import RateLimitedError
from albercik_chatbot.domain.prompting import SourceReference, assemble_prompt, extract_sources
from albercik_chatbot.domain.retrieval import limit_context_chars, select_sufficient_chunks
from albercik_chatbot.domain.scope import is_albertos_scope
from albercik_chatbot.infra.budget import check_llm_budget
from albercik_chatbot.infra.concurrency import ChatConcurrencyGuard
from albercik_chatbot.infra.rate_limit import check_and_increment
from albercik_chatbot.persistence.models import ProviderKind, UsageRecord
from albercik_chatbot.persistence.repositories import search_similar_chunks
from albercik_chatbot.providers.embedding.protocol import EmbeddingProvider
from albercik_chatbot.providers.llm.protocol import LLMProvider, LLMProviderError

Outcome = Literal["grounded", "insufficient_information", "out_of_scope", "unavailable"]

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


@dataclass(frozen=True)
class ChatSafetyConfig:
    """Server-controlled cost/abuse settings for one `/chat` request. Never
    influenced by request-body content (FR-035) — every field here is
    sourced exclusively from `config.Settings` by the caller (`chat.py`)."""

    rate_limit_per_minute: int
    llm_enabled: bool
    budget_max_llm_requests_per_hour: int
    max_context_chars: int


def _record_usage(
    session: Session,
    *,
    request_id: uuid.UUID,
    provider_kind: ProviderKind,
    provider_model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    success: bool,
    latency_ms: int,
) -> None:
    # Deliberately only these fields: no prompt/question/document/system-
    # instruction text is ever passed in here, and `UsageRecord` has no
    # column that could hold it even by mistake (FR-052, Principle IX).
    session.add(
        UsageRecord(
            request_id=request_id,
            provider_kind=provider_kind,
            provider_model=provider_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
            latency_ms=latency_ms,
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
    safety: ChatSafetyConfig,
    rate_limit_source_key: str,
    concurrency_guard: ChatConcurrencyGuard,
    request_id: uuid.UUID,
) -> AskQuestionResult:
    # --- rate limit ---
    rate_result = check_and_increment(
        session, source_key=rate_limit_source_key, limit_per_minute=safety.rate_limit_per_minute
    )
    if not rate_result.allowed:
        raise RateLimitedError(headers={"Retry-After": str(rate_result.retry_after_seconds)})

    # --- LLM kill switch + budget (fail closed) ---
    budget_result = check_llm_budget(
        session,
        llm_enabled=safety.llm_enabled,
        max_requests_per_hour=safety.budget_max_llm_requests_per_hour,
    )
    if not budget_result.allowed:
        return AskQuestionResult(outcome="unavailable", answer=_UNAVAILABLE_MESSAGE)

    # --- concurrency guard (paid LLM calls) ---
    with concurrency_guard.try_acquire() as acquired:
        if not acquired:
            return AskQuestionResult(outcome="unavailable", answer=_UNAVAILABLE_MESSAGE)

        # --- scope evaluation ---
        if not is_albertos_scope(question):
            return AskQuestionResult(outcome="out_of_scope", answer=_OUT_OF_SCOPE_MESSAGE)

        # --- embedding / retrieval ---
        embed_start = time.monotonic()
        query_embedding = embedding_provider.embed_query(question)
        embed_latency_ms = int((time.monotonic() - embed_start) * 1000)
        _record_usage(
            session,
            request_id=request_id,
            provider_kind=ProviderKind.embedding,
            provider_model=embedding_model_name,
            input_tokens=None,
            output_tokens=None,
            success=True,
            latency_ms=embed_latency_ms,
        )

        candidates = search_similar_chunks(session, query_embedding, top_k=top_k)
        grounding_chunks = select_sufficient_chunks(
            candidates, relevance_threshold=relevance_threshold
        )

        if not grounding_chunks:
            return AskQuestionResult(
                outcome="insufficient_information", answer=_INSUFFICIENT_INFORMATION_MESSAGE
            )

        # --- context size limit (before the LLM call) ---
        limited_chunks = limit_context_chars(
            grounding_chunks, max_context_chars=safety.max_context_chars
        )

        # --- LLM call ---
        prompt = assemble_prompt(question, limited_chunks)
        llm_start = time.monotonic()
        try:
            result = llm_provider.complete(
                system_prompt=prompt.system_prompt,
                user_message=prompt.user_message,
                max_tokens=max_answer_tokens,
            )
        except LLMProviderError:
            _record_usage(
                session,
                request_id=request_id,
                provider_kind=ProviderKind.llm,
                provider_model=llm_model_name,
                input_tokens=None,
                output_tokens=None,
                success=False,
                latency_ms=int((time.monotonic() - llm_start) * 1000),
            )
            return AskQuestionResult(outcome="unavailable", answer=_UNAVAILABLE_MESSAGE)

        # --- usage accounting ---
        _record_usage(
            session,
            request_id=request_id,
            provider_kind=ProviderKind.llm,
            provider_model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            success=True,
            latency_ms=result.latency_ms,
        )

        return AskQuestionResult(
            outcome="grounded", answer=result.text, sources=extract_sources(limited_chunks)
        )
