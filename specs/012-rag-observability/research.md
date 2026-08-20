# Phase 0 Research: LLM / RAG Observability

**Feature**: `012-rag-observability` | **Spec**: [spec.md](./spec.md)

## R1. Tracer acquisition model — DI-injected `Tracer`, never the OTel global

**Decision**: `infra/observability.py` exposes one function,
`configure_observability(settings: Settings) -> Tracer`, called exactly once
in `main.py::create_app()` — mirroring how `_build_configured_llm_provider()`
already builds the LLM provider once and stores it on `app.state`. The
returned `Tracer` is stored as `app.state.tracer` and injected into
`chat.py`'s handler (and from there passed into `ask_question()`, alongside
the existing `llm_provider`/`embedding_provider` parameters) via a new
`Depends(get_tracer)` in `api/deps.py`. Application code never calls
`opentelemetry.trace.get_tracer(__name__)` or
`opentelemetry.trace.set_tracer_provider()` directly.

When `OBSERVABILITY_ENABLED=false` (the default), `configure_observability()`
returns `opentelemetry.trace.NoOpTracer()` directly — it never touches the
OTel global tracer-provider registry at all. When enabled, it builds a real
`opentelemetry.sdk.trace.TracerProvider` (with the resource/sampler from R3
below) and returns `provider.get_tracer("shiruno")`, again without calling
the global `set_tracer_provider()`.

**Rationale**:
- **Structural safety, not conditional safety** (FR-002, FR-032, FR-033,
  FR-034): with a no-op `Tracer` in the disabled case, every
  `tracer.start_as_current_span(...)` call in `ask_question.py` is
  genuinely a no-op (the OTel API guarantees this) — there is no `if
  settings.OBSERVABILITY_ENABLED:` branch anywhere in domain/application
  code that could be gotten wrong or skipped. Whether tracing is enabled
  becomes a fact about which `Tracer` object `create_app()` constructed
  once, not a runtime branch repeated at every pipeline stage.
- **Testability matches the existing codebase pattern exactly**
  (Principle XI, Design Constraint 2 from Feature 001's tasks.md): tests
  already inject `FakeLLMProvider`/`FakeEmbeddingProvider` via
  `create_app(llm_provider=..., embedding_provider=...)` and never construct
  the real provider classes. `create_app(tracer=...)` follows the same
  shape — a test that wants to assert span structure builds its own
  `TracerProvider(sampler=ALWAYS_ON) + SimpleSpanProcessor(InMemorySpanExporter())`
  (both shipped in `opentelemetry-sdk` itself, no extra test dependency) and
  injects `provider.get_tracer("test")`.
- **Rejected alternative — global `trace.set_tracer_provider()` +
  module-level `trace.get_tracer(__name__)` at each call site**: this is
  OTel's own "getting started" idiom, but `set_tracer_provider()` is
  designed to be called at most once per process (a private
  `_TRACER_PROVIDER_SET_ONCE` guard silently no-ops and warns on a second
  call). A `pytest` process runs many tests in one interpreter; the first
  test to enable observability would permanently "stick" for every
  subsequent test in the same run, making tests order-dependent — a subtle,
  hard-to-debug flake risk this project has no reason to accept when
  dependency injection already solves it cleanly.

## R2. Failure isolation — a defensive wrapper, not a SAVEPOINT-analogue

**Decision**: `infra/observability.py` provides one context manager,
`traced_stage(tracer, name, **attributes)`, used at every pipeline stage
(`with traced_stage(tracer, "shiruno.retrieval", top_k=..., ...):`). Its body
calls `tracer.start_as_current_span(name, attributes=_sanitize(attributes))`
wrapped in a `try`/`except Exception` that logs at `DEBUG` and yields a
no-op span object on failure, so a bug in Shiruno's own instrumentation code
(e.g. a caller accidentally passing a non-primitive attribute value) can
never propagate into the request path it wraps. `_sanitize()` coerces
`uuid.UUID`/enum values to `str` before they reach the OTel SDK, since OTel
attribute values must be a primitive or a homogeneous array of primitives.

Export failures (an unreachable Phoenix backend, a timed-out OTLP call) are
a materially different failure mode from the above and are already isolated
by the OTel SDK itself, by construction: `BatchSpanProcessor` exports on a
dedicated background thread and swallows/logs exporter exceptions — it never
raises into the thread that produced the span. No Shiruno-specific
mechanism is needed for this half of FR-032; it is a property of using the
SDK's own batch processor rather than writing a custom one.

**Rationale**: Feature 011's `SAVEPOINT`-scoped `record_conversation()` call
solves a genuinely different problem — isolating one *database write's*
failure from an outer transaction that must still commit. There is no
transaction here to protect; a trace is inherently a fire-and-forget,
best-effort side channel with no durability contract of its own (Key
Entities: "operator/developer diagnostic data, not durable customer product
data"). Building a SAVEPOINT-shaped abstraction for tracing would be
solving a problem this feature doesn't have (Principle XIII) — the actual
risk (a bug in *our* instrumentation code) is fully addressed by a five-line
`try`/`except` at one shared call site, and the actual risk of *export*
failure is already handled by the SDK's documented background-thread
design.

## R3. OpenTelemetry package choice and OTLP transport

**Decision**: `opentelemetry-api`, `opentelemetry-sdk`, and
`opentelemetry-exporter-otlp-proto-http` (the OTLP/HTTP exporter, not gRPC).
Sampler: `opentelemetry.sdk.trace.sampling.ParentBased(TraceIdRatioBased(rate))`,
`rate` from `OTEL_TRACE_SAMPLE_RATE` (default `1.0`).

**Rationale**: The official OpenTelemetry Python SDK is the only
"vendor-neutral tracing standard" implementation the spec's Assumptions
name, so this isn't an open choice among tracing libraries — only among
*within-OTel* options (HTTP vs. gRPC transport). HTTP is chosen over gRPC
because it is pure Python plus `requests`-shaped HTTP calls with no
`grpcio` C-extension build step, which keeps the Dockerfile's
`python:3.14-slim` build simple and matches this project's existing
preference for minimal native-dependency surface (`psycopg[binary]` is
already the binary-wheel variant for the same reason). Phoenix accepts
OTLP/HTTP at `/v1/traces` on its default port `6006` alongside OTLP/gRPC on
`4317`, so no capability is lost by preferring HTTP.
**Alternative considered**: `opentelemetry-exporter-otlp` (the combined
gRPC+HTTP package) — rejected as unnecessarily pulling in the gRPC
dependency this project doesn't need.

## R4. Configuration surface

New `Settings` fields (added under a new `# --- Observability
(feature 012-rag-observability) ---` section, following this file's existing
per-feature grouping convention):

| Setting | Type | Default | Notes |
|---|---|---|---|
| `OBSERVABILITY_ENABLED` | `bool` | `False` | FR-002. Server-side only. |
| `OTEL_SERVICE_NAME` | `str` | `"shiruno"` | Resource attribute `service.name`. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `str` | `""` | Full traces endpoint URL, e.g. `http://phoenix:6006/v1/traces`. Empty while enabled → exporter setup is skipped and a single safe warning is logged at startup (FR-004); tracing stays a no-op rather than crashing startup. |
| `OTEL_EXPORTER_OTLP_HEADERS` | `str` | `""` | Raw `key1=value1,key2=value2` form (matches the upstream `OTEL_EXPORTER_OTLP_HEADERS` env var shape). Parsed into request headers only; never logged (FR-005). |
| `OTEL_TRACE_SAMPLE_RATE` | `float` | `1.0` | FR-035. `1.0` favors complete local-dev visibility per spec Assumptions; production operators set this explicitly. |
| `OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT` | `bool` | `False` | FR-017 toggle 1 (visitor question / assistant answer text). |
| `OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT` | `bool` | `False` | FR-017 toggle 2 (retrieved document / assembled-prompt text). |

**Rationale**: Names follow the upstream OpenTelemetry env-var convention
(`OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_EXPORTER_OTLP_HEADERS`) where a direct upstream equivalent exists —
an operator who already knows OTel conventions from other systems can
reuse that knowledge — and this project's own `OBSERVABILITY_`/feature-
prefixed convention (matching `PUBLIC_CHAT_TENANT_SLUG`,
`CHAT_CONCURRENCY_LIMIT`, etc.) for everything Shiruno-specific with no
OTel-standard name. The two content-capture toggles are intentionally
separate settings per the Clarifications session already recorded in
spec.md, not a single enum, so each can be independently off.

## R5. Span topology and where each span is created

The root span `shiruno.chat` is opened in `chat.py::post_chat()`, wrapping
both the `ask_question()` call and the later `record_conversation()` call —
the only two places that together cover "every pipeline stage that genuinely
executed" (FR-006). It is **not** opened inside `ask_question()` itself,
since `record_conversation()` (the `shiruno.conversation_recording` child
stage) runs in `chat.py` after `ask_question()` returns.

Every child span is created with `traced_stage()` (R2) at the exact point
each corresponding code block in `ask_question.py` already executes today —
no new stages are invented and no stage is pre-created "just in case" a
later branch needs it, so a request that short-circuits (e.g. small talk)
naturally produces only the spans for code that actually ran (FR-008, US5).
This requires passing the injected `Tracer` (R1) as a new parameter into
`ask_question()`, alongside the existing `llm_provider`/`embedding_provider`
parameters — no other signature or control-flow change.

| Span | Opened at (existing code location) | Key attributes |
|---|---|---|
| `shiruno.chat` (root) | `chat.py::post_chat()`, wraps the whole handler body | `shiruno.request_id`, `shiruno.outcome` (set after `ask_question()` returns), `shiruno.provider`, `shiruno.model` |
| `shiruno.security_or_cost_gates` | `ask_question.py`, wraps rate-limit + budget + concurrency-guard block | outcome of each gate only if it rejected the request |
| `shiruno.small_talk_classification` | around `classify_small_talk()` | `shiruno.small_talk` (bool) |
| `shiruno.scope_classification` | around `is_albertos_scope()` | result (bool) |
| `shiruno.query_embedding` | around `embedding_provider.embed_query()` | `shiruno.embedding.provider`, `.model`, `.duration_ms` |
| `shiruno.retrieval` | around `search_similar_chunks()` + `select_sufficient_chunks()` | see R6 |
| `shiruno.context_assembly` | around `limit_context_chars()` + `assemble_prompt()` | `shiruno.context.truncated` (bool), `.selected_chunk_count`, `.char_count` |
| `shiruno.llm_generation` | around `llm_provider.complete()` | see R7 |
| `shiruno.conversation_recording` | `chat.py`, wraps the existing `record_conversation()` call | `shiruno.tenant_id`, `.tenant_slug` (set inside `record_conversation()` once the tenant resolves — see R8) |

## R6. Retrieval span attributes

Flat, OTel-attribute-shaped (no nested objects — arrays of primitives only):

- `shiruno.retrieval.top_k`, `.relevance_threshold` (configured values)
- `shiruno.retrieval.candidate_count` (`len(candidates)` from
  `search_similar_chunks()`)
- `shiruno.retrieval.passed_filter_count` (`len(grounding_chunks)`)
- `shiruno.retrieval.selected_count` (`len(limited_chunks)`)
- `shiruno.retrieval.selected.document_ids` (`list[str]`),
  `.selected.similarities` (`list[float]`), `.selected.labels` (`list[str]`)
  — one entry per selected chunk, in order, satisfying FR-011/US2 without
  ever including chunk `content`.
- `shiruno.retrieval.selected.contents` (`list[str]`) — **only** when
  `OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT=true` (FR-015/FR-017).

`search_similar_chunks()` already returns candidates in the shape needed
here (`persistence/repositories.py`); no query changes are required — the
counts above are ordinary Python `len()` calls on lists `ask_question.py`
already computes.

## R7. LLM generation span attributes

- `shiruno.llm.provider`, `.model`, `.input_tokens`, `.output_tokens`,
  `.latency_ms`, `.supported` (bool, FR-022 — read directly from
  `LLMResult.supported`, never inferred from `answer` text)
- `shiruno.llm.provider_metrics.<key>` — one attribute per key in
  `LLMResult.provider_metrics`, flattened with this prefix (FR-023:
  "clearly-namespaced supplementary data," opaque, no branching on keys)
- On `LLMProviderError`: `span.set_status(StatusCode.ERROR,
  description=<safe failure_category string>)` — **never**
  `span.record_exception()`, since that OTel convenience method captures the
  raw exception message and stack trace as span attributes by default,
  which would violate FR-026's "no raw exception text" rule. Only the same
  small, pre-existing `FailureCategory` literal strings
  (`ask_question.py`'s `"provider_error"` / `"budget_exceeded"` /
  `"kill_switch"` / `"concurrency_limit"`) are ever recorded.
- Full `answer` text and full assembled prompt: gated behind the two
  content-capture toggles exactly as in R6, never on by default (FR-013,
  FR-014, FR-016).
- Chain-of-thought / Ollama's `message.thinking` field
  (`providers/llm/ollama_provider.py`): remains completely untouched by
  this feature. `OllamaLLMProvider.complete()` already never reads or
  returns that field to its caller (pre-existing invariant) — `ask_question.py`
  and the tracing code added here only ever see the `LLMResult` this
  provider already returns, which structurally cannot contain it (FR-019).

## R7a. Embedding span — `text_count`/`success` intentionally omitted

FR-024 asks the embedding span to expose "how many texts were embedded"
and "success/failure." Neither is a separate span attribute in this
feature's design: `embed_query()` always embeds exactly one text (the
query itself), so a count attribute would be a constant, not diagnostic
information; and `ask_question.py` has no `try`/`except` around the
embedding call today — a failure there propagates as an unhandled
exception, unchanged by this feature — so there is no code path where the
`shiruno.query_embedding` span would ever observe a "failure" outcome. The
span's mere presence with a completed, positive duration already signals
success by construction. This is a deliberate omission, not an oversight
(analyze-report finding C2, 2026-08-20).

## U1 note — FR-025's unparseable-vs-unavailable distinction

`ask_question.py`'s pre-existing `FailureCategory` type (introduced by
feature 004-rag-answerability-and-ollama-performance) records a single
`"provider_error"` value for both a genuine provider/network failure and a
structured response that failed schema validation (`LLMProviderError` is
raised for both — see `providers/llm/protocol.py`). This feature's
`shiruno.llm_generation` span surfaces whatever `failure_category` value
already exists; it does not add new plumbing to split this pre-existing
category further. spec.md's FR-025 was narrowed accordingly (analyze-report
finding U1, 2026-08-20) rather than this plan inventing a new distinction
Feature 004 itself never modeled.

## R8. Tenant metadata placement — on `conversation_recording`, not root

**Decision**: `shiruno.tenant_id`/`shiruno.tenant_slug` are set on the
`shiruno.conversation_recording` child span, inside
`record_conversation()`, immediately after `resolve_public_tenant()`
resolves (or fails to resolve) the tenant — not by adding a second,
tracing-only tenant resolution earlier in `chat.py`.

**Rationale**: `resolve_public_tenant()` is already called exactly once per
request, inside `record_conversation()`; duplicating that DB lookup solely
so the root span could carry the same attribute a few microseconds earlier
would be tracing *causing* an extra query, a small but real violation of
"observability must observe the system, never participate in it" (spec
Core Principle) taken literally as "never add work the system wouldn't
otherwise do." FR-007 (what the root span MUST carry) does not list tenant
metadata; FR-028/FR-029 only require that wherever tenant identity is
attached, it is server-derived and never fabricated when unresolvable —
both hold on `conversation_recording`. When `resolve_public_tenant()`
returns `None`, no tenant attribute is set at all (never fabricated),
matching the existing `record_conversation()` early-return behavior for
that case.

## R9. `trace_id` on `ConversationRecord` — not added

**Decision**: No new column is added to `ConversationRecord`. Correlation
(US7, FR-030) is achieved entirely through `shiruno.request_id`, already set
on the root span (R5) — the same `request_id` already visible on every
`ConversationRecord` row and every `UsageRecord` row today. Phoenix (and any
OTLP-compatible backend) supports filtering/searching spans by attribute
value, so "find the trace for conversation X" is "search traces by
`shiruno.request_id = <that row's request_id>` in the backend's UI" — no
database schema change needed to make that search possible.

**Rationale**: The spec's own Assumptions section frames this explicitly as
open ("Whether a durable, persisted correlation field is added ... is a
planning-phase architecture decision — this specification only requires
that an operator can move from a conversation record to its trace and back
using an identifier already common to both"). A persisted `trace_id` column
would require a migration, a new nullable write on every recorded
conversation, and a new coupling from the durable `ConversationRecord`
table to whatever OTel trace-ID format is in play — for zero additional
capability, since `request_id`-based search already satisfies FR-030/SC-005
end to end. Rejected per Principle XIII (Simplicity for MVP): this is
exactly "a new dependency that doesn't solve an immediate, present
requirement."

## R10. Docker Compose — optional `observability` profile

**Decision**: Add one new service, `phoenix`, gated behind Compose's
`profiles: ["observability"]` (Compose's native opt-in mechanism, already
proven at this project's scale — no new tooling), using the official
`arizephoenix/phoenix` image, exposing `6006` (UI + OTLP/HTTP collector) and
`4317` (OTLP/gRPC, unused by this feature's exporter choice but harmless to
expose for a local-only container) on the host, with a named volume for
Phoenix's own local trace storage. Start it with `docker compose --profile
observability up -d`, exactly as the spec brief's own example. The existing
`app` service is **not** added to the `observability` profile — it remains
part of the default `docker compose up -d` set regardless (FR-037), and
`OBSERVABILITY_ENABLED` defaults to `false` regardless of whether Phoenix
happens to be running, so a plain `docker compose up -d` is entirely
unaffected by this feature (FR-036).

**Rationale**: This is the same pattern this compose file already uses for
`db-test` (a service that exists but isn't required for normal operation) —
no new Compose feature is introduced. `OTEL_EXPORTER_OTLP_ENDPOINT`'s
documented local-dev value (`http://phoenix:6006/v1/traces`, set in
`.env.example`, commented out / left blank by default) resolves correctly
whether or not the `phoenix` service is actually running, because Compose's
internal DNS only needs the service to be *reachable*, not started, for the
name to resolve within the network — and if it isn't running at all, the
exporter's connection attempt simply fails and is swallowed by
`BatchSpanProcessor` (R1/R2), producing no visible effect on `/chat`
(FR-032, Edge Cases).

## R11. Phoenix vs. Langfuse (spec brief §18) — Phoenix chosen, OTel boundary keeps Langfuse viable later

| | Phoenix (arize-phoenix) | Langfuse |
|---|---|---|
| OTel/OTLP support | Native OTLP receiver (HTTP + gRPC); this is its primary ingestion path | OTLP-compatible ingestion also available, but its primary integration story is SDK/decorator-based |
| RAG/LLM trace visualization | Purpose-built for RAG: retrieval span visualization, embeddings/similarity inspection, first-class "OpenInference" semantic conventions for retriever/LLM spans | General LLM observability UI; less RAG-specific visualization out of the box |
| Self-hosting | Single Docker image, no external dependencies for local dev | Also self-hostable, but a heavier stack (its own Postgres/ClickHouse-backed services) — more than this feature's local-dev-only scope needs |
| Evaluation features | Built-in eval tooling exists but is explicitly out of scope for this feature (spec Explicit Non-Goals) | Similarly has eval/prompt-management features, also out of scope here |

**Decision**: Phoenix is the first local-development backend, exactly as
the spec's Assumptions treat as a settled constraint — this table documents
*why* it's a reasonable choice given what was actually needed (single-
container local RAG trace visualization), not a re-litigation of the
decision. Because instrumentation is expressed only in OTel's vendor-neutral
API (R1, R3) — application code never imports a Phoenix-specific or
Langfuse-specific SDK — switching or adding Langfuse later is purely a
`configure_observability()`-level change (a different `OTEL_EXPORTER_OTLP_ENDPOINT`
and, if needed, a second exporter attached to the same
`BatchSpanProcessor`), never an application/domain-code change.

## R12. Testing strategy

- **Unit-level**: `infra/observability.py`'s `configure_observability()` and
  `traced_stage()` are tested directly with a `TracerProvider` +
  `InMemorySpanExporter` (`opentelemetry.sdk.trace.export.in_memory_span_exporter`,
  shipped inside `opentelemetry-sdk`, zero extra dependency) —
  `SimpleSpanProcessor` (synchronous) rather than `BatchSpanProcessor`, so
  spans are readable immediately after the `with` block exits, with no
  flush/sleep needed in tests.
- **Integration-level**: `db_async_client`/`create_app()`-based tests
  (mirroring the existing `tests/integration/` and `tests/contract/`
  fixtures) inject `create_app(tracer=<TracerProvider+InMemorySpanExporter
  tracer>)` and assert on the exporter's captured spans after issuing a real
  `/chat` request through the existing fake LLM/embedding providers — this
  proves span topology end-to-end (spec's Testing Requirements items 2–21)
  without any real Ollama/Anthropic/Phoenix/network dependency, matching
  every existing test in this suite.
  `create_app()`'s default (`tracer=None`) continues to resolve to
  `configure_observability(get_settings())`, so existing tests that don't
  care about tracing at all (the overwhelming majority) need no changes —
  `OBSERVABILITY_ENABLED` defaults to `False` in the test environment
  exactly like everywhere else, giving them the no-op `Tracer` for free.
- **Reliability proof (US6, FR-032/033/034)**: one test parametrizes the
  same request three ways — no `tracer` override (no-op), a working
  in-memory tracer, and a `Tracer` built against a `TracerProvider` whose
  single processor is a fake exporter that always raises — and asserts
  `ChatResponse` is byte-for-byte identical across all three, proving
  tracing failure cannot change chat behavior at the exact boundary FR-032
  describes.
