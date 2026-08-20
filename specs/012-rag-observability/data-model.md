# Phase 1 Data Model: LLM / RAG Observability

**Feature**: `012-rag-observability` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## No new database entities

This feature introduces **no new SQLAlchemy models, tables, columns, or
Alembic migrations**. `ConversationRecord`, `UsageRecord`, `Tenant`, and
every other existing persisted entity are unchanged (spec FR-039–FR-042;
research.md R9 — `trace_id` is deliberately not added as a persisted
column). The "entities" this feature actually introduces are in-memory
OpenTelemetry spans, which exist only for the lifetime of one request (plus
async export) and are never queried by Shiruno's own application code —
they are written to an OTLP backend and read back only through that
backend's own UI (Phoenix). The schema for those spans is documented below
in place of a conventional data model, since it plays the same "what shape
is this data, what are its fields and constraints" role for this feature.

## Span schema

### Root span: `shiruno.chat`

One per chat request that reaches `ask_question()` (FR-006 — a request
rejected earlier by request-body-size validation is not traced at all, per
spec Assumptions).

| Attribute | Type | Always present? | Notes |
|---|---|---|---|
| `shiruno.request_id` | `string` (UUID) | always | Correlation identifier (FR-007, FR-030) |
| `shiruno.outcome` | `string` | always, set once `ask_question()` returns | One of `grounded`, `insufficient_information`, `out_of_scope`, `unavailable`, `small_talk` (`AskQuestionResult.outcome`) |
| `shiruno.provider` | `string` | when `AskQuestionResult.provider_name` is not `None` | FR-007 |
| `shiruno.model` | `string` | when `AskQuestionResult.provider_model` is not `None` | FR-007 |
| `shiruno.failure_category` | `string` | when `AskQuestionResult.failure_category` is not `None` | Same literal values as `ask_question.FailureCategory` |

### Child span: `shiruno.security_or_cost_gates`

Present on every traced request (it is the first stage `ask_question()`
always runs). No attributes beyond span status; a rejection is represented
by `span.set_status(ERROR, description=<gate name>)` and no further child
spans are created for that request (FR-027, US3.3).

### Child span: `shiruno.small_talk_classification`

Present whenever the gates above pass.

| Attribute | Type | Notes |
|---|---|---|
| `shiruno.small_talk` | `bool` | `True` when `classify_small_talk()` matched |

### Child span: `shiruno.scope_classification`

Present only when small-talk classification did **not** match (US5.1 — a
small-talk request's trace never contains this span).

| Attribute | Type | Notes |
|---|---|---|
| `shiruno.in_scope` | `bool` | Result of `is_albertos_scope()` |

### Child span: `shiruno.query_embedding`

Present only when scope classification passed (never for `small_talk` or
`out_of_scope` outcomes — US5).

| Attribute | Type | Notes |
|---|---|---|
| `shiruno.embedding.provider` | `string` | Always `local_sentence_transformer` today (Design Constraint 3) |
| `shiruno.embedding.model` | `string` | `embedding_model_name` |
| `shiruno.embedding.duration_ms` | `int` | Already computed today for `UsageRecord` |
| `shiruno.embedding.text_count` | `int` | Always `1` for `embed_query()` — not a diagnostic signal, included only to satisfy FR-024's literal wording (research.md R7a) |

No embedding vector values ever appear here (FR-018, FR-024). This span's
mere presence with a positive duration signals success; there is no
"failure" state to represent, since `ask_question.py` has no `try`/`except`
around the embedding call — a failure propagates as an unhandled exception
instead (research.md R7a).

### Child span: `shiruno.retrieval`

Present whenever embedding succeeded.

| Attribute | Type | Notes |
|---|---|---|
| `shiruno.retrieval.top_k` | `int` | Configured `RETRIEVAL_TOP_K` |
| `shiruno.retrieval.relevance_threshold` | `float` | Configured `RETRIEVAL_RELEVANCE_THRESHOLD` |
| `shiruno.retrieval.candidate_count` | `int` | `len(candidates)` |
| `shiruno.retrieval.passed_filter_count` | `int` | `len(grounding_chunks)` |
| `shiruno.retrieval.selected_count` | `int` | `len(limited_chunks)` |
| `shiruno.retrieval.selected.document_ids` | `list[string]` | Parallel arrays, one entry per selected chunk |
| `shiruno.retrieval.selected.similarities` | `list[float]` | |
| `shiruno.retrieval.selected.labels` | `list[string]` | Safe source label (`document.original_filename`) |
| `shiruno.retrieval.selected.contents` | `list[string]` | **Only** when `OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT=true` |

When `passed_filter_count == 0`, the request short-circuits to
`insufficient_information` and no further child spans are created
(`shiruno.context_assembly`, `shiruno.llm_generation` are absent — FR-008).

### Child span: `shiruno.context_assembly`

Present only when at least one chunk passed relevance filtering.

| Attribute | Type | Notes |
|---|---|---|
| `shiruno.context.truncated` | `bool` | `len(limited_chunks) < len(grounding_chunks)` (FR-012) |
| `shiruno.context.selected_chunk_count` | `int` | `len(limited_chunks)` |
| `shiruno.context.char_count` | `int` | Sum of `len(chunk.content)` over `limited_chunks` |
| `shiruno.context.prompt` | `string` | **Only** when `OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT=true` (FR-016) |

### Child span: `shiruno.llm_generation`

Present whenever a real `llm_provider.complete()` call was attempted.

| Attribute | Type | Always present? | Notes |
|---|---|---|---|
| `shiruno.llm.provider` | `string` | always | |
| `shiruno.llm.model` | `string` | always | |
| `shiruno.llm.input_tokens` | `int` | when available | |
| `shiruno.llm.output_tokens` | `int` | when available | |
| `shiruno.llm.latency_ms` | `int` | always | |
| `shiruno.llm.supported` | `bool` | only on success | FR-022 — direct from `LLMResult.supported`, never inferred |
| `shiruno.llm.provider_metrics.<key>` | opaque primitive | when present | Flattened from `LLMResult.provider_metrics`, namespaced (FR-023) |
| `shiruno.llm.answer` | `string` | **Only** when `OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT=true` and the call succeeded | FR-014 |
| span status | — | on `LLMProviderError` | `ERROR`, `description=<FailureCategory string>`, never `record_exception()` (research.md R7) |

Ollama's `message.thinking` field is never read by `OllamaLLMProvider` in
the first place (pre-existing invariant) and therefore structurally cannot
appear on this span (FR-019).

### Child span: `shiruno.conversation_recording`

Present on every traced request (it always runs in `chat.py`, wrapping the
existing `record_conversation()` call, regardless of outcome).

| Attribute | Type | Notes |
|---|---|---|
| `shiruno.tenant_id` | `string` (UUID) | Set only if `resolve_public_tenant()` resolved a tenant (research.md R8); never fabricated (FR-029) |
| `shiruno.tenant_slug` | `string` | Same condition |
| `shiruno.question` | `string` | **Only** when `OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT=true` (FR-013) |

## Configuration entity: `Settings` additions

See research.md R4 for the full table of seven new `Settings` fields
(`OBSERVABILITY_ENABLED`, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_TRACE_SAMPLE_RATE`,
`OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT`,
`OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT`). All are plain
`pydantic-settings` fields on the existing `Settings` class in
`src/shiruno/config.py` — no new settings class or file.
