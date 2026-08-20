"""Best-effort, SAVEPOINT-isolated conversation recording (feature
011-conversations-analytics, research.md §2a, §3, §4).

Called once per public chat request that reached one of the five defined
outcomes (FR-001/FR-001a — a caller never invokes this for a request
rejected earlier by rate limiting or payload/question-length validation).

Resolves the public reference tenant first (a plain `SELECT`, no
transactional isolation needed for a non-mutating read). If it cannot be
resolved (missing/inactive — `resolve_public_tenant.py`'s fail-closed
contract), logs a single safe line naming only the configured slug and
returns immediately — there is no valid tenant to attribute a row to, so
no insert is attempted.

If a tenant does resolve, the `ConversationRecord` insert runs inside
`session.begin_nested()` (a PostgreSQL `SAVEPOINT`) nested within the
request's own existing transaction — never a second session, connection,
queue, or background worker. A `SAVEPOINT` has no independent durability:
on success it is released and the row becomes durable only later, together
with the rest of the request, when the outer transaction commits; on
failure only the savepoint rolls back, the outer transaction (and any
`UsageRecord` rows already flushed in it) is left untouched, and this
function propagates the exception so the caller (`api/routers/chat.py`)
can log it and continue building a normal `ChatResponse` regardless
(FR-003, FR-004).

Every operational field on the row is an immutable, at-write-time snapshot
of `AskQuestionResult` — never recomputed later from current
`KnowledgeDocument` state or current provider configuration (research.md
§2a).

Feature 012-rag-observability (research.md R8): the caller (`chat.py`)
already has the `shiruno.conversation_recording` span open around this
call, so it is passed in explicitly (`span`) rather than resolved via
OpenTelemetry's implicit "current span" context — consistent with this
feature's DI-everywhere approach (research.md R1). `shiruno.tenant_id`/
`.tenant_slug` are set here, once the tenant actually resolves, since this
is the one place tenant resolution genuinely happens; when it does not
resolve, no tenant attribute is set at all (never fabricated, FR-029).
"""

import uuid

from opentelemetry.trace import Span
from sqlalchemy.orm import Session

from shiruno.application.ask_question import AskQuestionResult
from shiruno.application.resolve_public_tenant import resolve_public_tenant
from shiruno.domain.question_normalization import normalize_question
from shiruno.infra.logging import get_logger
from shiruno.infra.observability import safe_set_attribute
from shiruno.persistence.models import ConversationOutcome, ConversationRecord, ProviderName

logger = get_logger(__name__)


def record_conversation(
    *,
    session: Session,
    tenant_slug: str,
    request_id: uuid.UUID,
    question: str,
    result: AskQuestionResult,
    latency_ms: int,
    span: Span,
    capture_question_answer_content: bool = False,
) -> None:
    tenant = resolve_public_tenant(session, slug=tenant_slug)
    if tenant is None:
        logger.warning(
            "Public reference tenant unavailable for conversation recording",
            extra={"configured_slug": tenant_slug},
        )
        return

    safe_set_attribute(span, "shiruno.tenant_id", tenant.id)
    safe_set_attribute(span, "shiruno.tenant_slug", tenant.slug)
    if capture_question_answer_content:
        safe_set_attribute(span, "shiruno.question", question)

    with session.begin_nested():
        session.add(
            ConversationRecord(
                tenant_id=tenant.id,
                request_id=request_id,
                question=question,
                normalized_question=normalize_question(question),
                outcome=ConversationOutcome(result.outcome),
                answer=result.answer,
                sources=[
                    {"document_id": str(source.document_id), "label": source.label}
                    for source in result.sources
                ]
                or None,
                safe_failure_category=result.failure_category,
                provider_name=ProviderName(result.provider_name)
                if result.provider_name is not None
                else None,
                provider_model=result.provider_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                provider_metrics=result.provider_metrics,
                latency_ms=latency_ms,
            )
        )
        session.flush()
