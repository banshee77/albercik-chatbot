"""POST /api/v1/chat — User Story 1 (Phase 3), hardened by Phase 5 / User
Story 3 with the full cost/abuse pipeline (research.md §2-3,7; tasks.md
T054-T068):

    request -> HTTP/payload validation -> question length validation ->
    rate limit -> LLM kill switch -> budget check -> concurrency guard ->
    scope evaluation -> embedding/retrieval -> context size limit ->
    LLM call -> usage accounting -> response

Public, no authentication (FR-002) — and deliberately identical controls
apply to every caller, admin or not; an authenticated Administrator gets
no exemption from any of the above (US3.7).

Only the request-body-size check
(`api.deps.require_bounded_request_body`) is a FastAPI `Depends()`: it
must run before the body is parsed, which is exactly what FastAPI
guarantees for every `Depends()` relative to body validation. Everything
from question length onward either lives in `ChatRequest`'s own Pydantic
validation (which FastAPI also guarantees runs before this function's
body) or, from rate limiting onward, in `ask_question.py` as strictly
sequential imperative code — see that module's docstring for why
independent `Depends()` cannot reproduce this pipeline's required order.

Feature 011-conversations-analytics (research.md §3, §9): after
`ask_question()` returns, this handler measures the end-to-end elapsed
time and calls `record_conversation()`, wrapped in `try`/`except
Exception` so a recording failure can never turn this otherwise-successful
response into an error (FR-003) — the failure is logged with only
`request_id` as context (FR-004, FR-038) and execution always falls
through to building and returning `ChatResponse` below.

Feature 012-rag-observability (research.md R5): the injected `tracer`
(a no-op `Tracer` unless `OBSERVABILITY_ENABLED` is true) opens exactly
one root `shiruno.chat` span per request that reaches this function,
wrapping both the `ask_question()` call and the `record_conversation()`
call — the only two places that together cover every pipeline stage that
can genuinely execute (FR-006). `shiruno.outcome`/`.provider`/`.model`/
`.failure_category` are set from `AskQuestionResult` once `ask_question()`
returns; they are never set before that, so a request that raises before
returning (e.g. `RateLimitedError`) never gets a fabricated outcome.
"""

import time
import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from opentelemetry.trace import Tracer
from sqlalchemy.orm import Session

from shiruno.api.deps import (
    get_chat_concurrency_guard,
    get_embedding_provider,
    get_llm_model_name,
    get_llm_provider,
    get_llm_provider_name,
    get_tracer,
    require_bounded_request_body,
)
from shiruno.api.schemas import ChatRequest, ChatResponse, SourceReferenceOut
from shiruno.application.ask_question import ChatSafetyConfig, ask_question
from shiruno.application.record_conversation import record_conversation
from shiruno.config import get_settings
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.infra.logging import get_logger
from shiruno.infra.observability import safe_set_attribute, traced_stage
from shiruno.infra.rate_limit import resolve_client_ip
from shiruno.persistence.database import get_session
from shiruno.providers.embedding.protocol import EmbeddingProvider
from shiruno.providers.llm.protocol import LLMProvider

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post(
    "/chat", response_model=ChatResponse, dependencies=[Depends(require_bounded_request_body)]
)
def post_chat(
    payload: ChatRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    concurrency_guard: ChatConcurrencyGuard = Depends(get_chat_concurrency_guard),
    llm_provider_name: str = Depends(get_llm_provider_name),
    llm_model_name: str = Depends(get_llm_model_name),
    tracer: Tracer = Depends(get_tracer),
) -> ChatResponse:
    settings = get_settings()
    source_key = resolve_client_ip(request, trusted_proxy_count=settings.TRUSTED_PROXY_COUNT)
    safety = ChatSafetyConfig(
        rate_limit_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        llm_enabled=settings.LLM_ENABLED,
        budget_max_llm_requests_per_hour=settings.BUDGET_MAX_LLM_REQUESTS_PER_HOUR,
        max_context_chars=settings.MAX_CONTEXT_CHARS,
        capture_question_answer_content=settings.OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT,
        capture_document_prompt_content=settings.OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT,
    )
    request_id = uuid.uuid4()
    request_start = time.monotonic()

    with traced_stage(tracer, "shiruno.chat") as chat_span:
        safe_set_attribute(chat_span, "shiruno.request_id", request_id)

        result = ask_question(
            payload.question,
            session=session,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            top_k=settings.RETRIEVAL_TOP_K,
            relevance_threshold=settings.RETRIEVAL_RELEVANCE_THRESHOLD,
            max_answer_tokens=settings.LLM_MAX_ANSWER_TOKENS,
            embedding_model_name=settings.EMBEDDING_MODEL_NAME,
            llm_model_name=llm_model_name,
            llm_provider_name=llm_provider_name,
            safety=safety,
            rate_limit_source_key=source_key,
            concurrency_guard=concurrency_guard,
            request_id=request_id,
            tracer=tracer,
        )
        latency_ms = int((time.monotonic() - request_start) * 1000)

        safe_set_attribute(chat_span, "shiruno.outcome", result.outcome)
        if result.provider_name is not None:
            safe_set_attribute(chat_span, "shiruno.provider", result.provider_name)
        if result.provider_model is not None:
            safe_set_attribute(chat_span, "shiruno.model", result.provider_model)
        if result.failure_category is not None:
            safe_set_attribute(chat_span, "shiruno.failure_category", result.failure_category)

        with traced_stage(tracer, "shiruno.conversation_recording") as conv_span:
            try:
                record_conversation(
                    session=session,
                    tenant_slug=settings.PUBLIC_CHAT_TENANT_SLUG,
                    request_id=request_id,
                    question=payload.question,
                    result=result,
                    latency_ms=latency_ms,
                    span=conv_span,
                    capture_question_answer_content=safety.capture_question_answer_content,
                )
            except Exception:
                logger.exception(
                    "Conversation recording failed", extra={"request_id": str(request_id)}
                )

    if result.outcome == "unavailable":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ChatResponse(
        outcome=result.outcome,
        answer=result.answer,
        sources=[
            SourceReferenceOut(document_id=source.document_id, label=source.label)
            for source in result.sources
        ],
        request_id=request_id,
    )
