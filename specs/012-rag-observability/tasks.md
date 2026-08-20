# Tasks: LLM / RAG Observability

**Input**: Design documents from `/specs/012-rag-observability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — the spec's own 32-item Testing Requirements section and
Success Criteria (SC-001–SC-008) explicitly require automated coverage, and
research.md R12 defines the exact mechanism (`InMemorySpanExporter` +
`SimpleSpanProcessor`, no real Phoenix/Ollama/Anthropic/network dependency).

**Organization**: Tasks are grouped by user story from spec.md, in the same
priority order. Nearly every story in this feature is P1 — this reflects
that tracing correctness, privacy defaults, and reliability are facets of
one shared instrumentation mechanism, not independently optional slices;
US8 (local Phoenix visualization) is the sole P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task in the same phase)
- **[Story]**: Which user story this task belongs to (US1–US9, matching
  spec.md)
- Every task names its exact file path(s)

## Path Conventions

Single-project layout (plan.md's Structure Decision) — `src/shiruno/`,
`tests/` at the repository root. No new top-level directory.

---

## Phase 1: Setup

**Purpose**: Add the three new dependencies this feature needs.

- [X] T001 Add `opentelemetry-api`, `opentelemetry-sdk`, and
      `opentelemetry-exporter-otlp-proto-http` to `pyproject.toml`
      dependencies (research.md R3)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared `Tracer`-construction/injection mechanism every user
story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Create `src/shiruno/infra/observability.py` with
      `configure_observability(settings: Settings) -> Tracer`: returns
      `opentelemetry.trace.NoOpTracer()` when
      `settings.OBSERVABILITY_ENABLED` is `False`; otherwise builds a real
      `opentelemetry.sdk.trace.TracerProvider` with resource attribute
      `service.name=settings.OTEL_SERVICE_NAME`, a
      `ParentBased(TraceIdRatioBased(settings.OTEL_TRACE_SAMPLE_RATE))`
      sampler, and — only when `settings.OTEL_EXPORTER_OTLP_ENDPOINT` is
      non-empty — a `BatchSpanProcessor(OTLPSpanExporter(endpoint=...,
      headers=<parsed OTEL_EXPORTER_OTLP_HEADERS>))`; when enabled but the
      endpoint is empty, logs one safe warning (endpoint/headers never
      logged) and skips adding a processor, returning a
      `TracerProvider.get_tracer("shiruno")` that creates spans nobody
      exports. Never calls `trace.set_tracer_provider()` (research.md R1,
      R3, R4)
- [X] T003 Add `traced_stage(tracer, name, **attributes)` context manager
      and an internal `_sanitize(attributes)` helper (coerces `uuid.UUID`
      and enum values to `str`; drops non-primitive/non-list values) to
      `src/shiruno/infra/observability.py`; the context manager wraps
      `tracer.start_as_current_span(name,
      attributes=_sanitize(attributes))` in `try`/`except Exception`,
      logging at `DEBUG` and yielding a no-op span on failure, so a bug in
      this module's own callers can never propagate into the request path
      (research.md R2)
- [X] T004 [P] Add 7 new `Settings` fields under a new `# --- Observability
      (feature 012-rag-observability) ---` section in `src/shiruno/config.py`:
      `OBSERVABILITY_ENABLED: bool = False`, `OTEL_SERVICE_NAME: str =
      "shiruno"`, `OTEL_EXPORTER_OTLP_ENDPOINT: str = ""`,
      `OTEL_EXPORTER_OTLP_HEADERS: str = ""`, `OTEL_TRACE_SAMPLE_RATE: float
      = 1.0`, `OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT: bool = False`,
      `OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT: bool = False`
      (research.md R4)
- [X] T005 Add a `get_tracer(request: Request) -> Tracer` dependency to
      `src/shiruno/api/deps.py`, mirroring the existing
      `get_llm_provider`/`get_embedding_provider` pattern (reads
      `request.app.state.tracer`)
- [X] T006 Wire tracer construction into `src/shiruno/main.py::create_app()`:
      add a `tracer: Tracer | None = None` parameter; set
      `app.state.tracer = tracer or configure_observability(settings)`,
      constructed once at factory-call time like every other provider; log
      one safe startup line naming only whether observability is enabled
      (never the endpoint or headers)
- [X] T007 [P] Document the 7 new settings in `.env.example`, all
      commented out / `false` / empty by default, with a one-line note that
      this feature is opt-in and each setting's purpose (research.md R4)
- [X] T008 [P] Create `tests/unit/test_observability.py` covering
      `configure_observability()` (disabled → `NoOpTracer`; enabled with a
      valid endpoint → a real `Tracer` backed by a `TracerProvider`;
      enabled with a missing endpoint → no processor attached, one safe
      warning logged, no crash) and `traced_stage()` (produces a span with
      the given, sanitized attributes via `InMemorySpanExporter` +
      `SimpleSpanProcessor`; swallows an injected exception from a broken
      attribute value and still yields a usable span) (research.md R12)
- [X] T008a [P] Unit test in `tests/unit/test_observability.py`:
      `configure_observability()` with `OTEL_TRACE_SAMPLE_RATE=0.0`
      produces a `Tracer` whose spans never reach the in-memory exporter;
      `OTEL_TRACE_SAMPLE_RATE=1.0` produces spans that always do (FR-035)

**Checkpoint**: Foundation ready — every user story below can now begin.

---

## Phase 3: User Story 1 - Operator traces a grounded request end-to-end (Priority: P1) 🎯 MVP

**Goal**: A root `shiruno.chat` span plus one child span per pipeline stage
that genuinely executes, each with real timing, wired into the actual
`chat.py` → `ask_question.py` → `record_conversation.py` call chain.

**Independent Test**: With observability enabled, send a grounded chat
request; retrieve its trace and confirm every pipeline stage that actually
ran appears, in order, each with plausible timing (spec US1).

### Tests for User Story 1

- [X] T009 [P] [US1] Integration test in
      `tests/integration/test_chat_tracing.py`: a grounded chat request (via
      the existing fake LLM/embedding providers, `create_app(tracer=<in-
      memory Tracer>)`) produces one root `shiruno.chat` span and child
      spans `shiruno.security_or_cost_gates`,
      `shiruno.small_talk_classification`, `shiruno.scope_classification`,
      `shiruno.query_embedding`, `shiruno.retrieval`,
      `shiruno.context_assembly`, `shiruno.llm_generation`,
      `shiruno.conversation_recording`, in that order, each with a positive
      duration; the root span's `shiruno.outcome`/`shiruno.provider`/
      `shiruno.model` attributes match the `AskQuestionResult` returned for
      this request; and the `shiruno.llm_generation` span carries a
      namespaced `shiruno.llm.provider_metrics.<key>` attribute when the
      fake provider returns `provider_metrics` (SC-001; FR-007, FR-023;
      spec Testing Requirements #2, #5)

### Implementation for User Story 1

- [X] T010 [US1] Add a `tracer: Tracer` parameter to `ask_question()` in
      `src/shiruno/application/ask_question.py`
- [X] T011 [US1] In `src/shiruno/api/routers/chat.py`, inject the tracer via
      `Depends(get_tracer)`, open a root `shiruno.chat` span (via
      `traced_stage`) wrapping the existing `ask_question()` and
      `record_conversation()` calls, set `shiruno.request_id` immediately
      and `shiruno.outcome`/`shiruno.provider`/`shiruno.model`/
      `shiruno.failure_category` once `ask_question()` returns, and pass
      `tracer` into `ask_question()` (research.md R5; data-model.md root
      span)
- [X] T012 [US1] Wrap the rate-limit/budget/concurrency-guard block in
      `ask_question()` with `traced_stage(tracer,
      "shiruno.security_or_cost_gates")` in
      `src/shiruno/application/ask_question.py`
- [X] T013 [US1] Wrap the `classify_small_talk()` call with
      `traced_stage(tracer, "shiruno.small_talk_classification",
      shiruno_small_talk=...)` in `src/shiruno/application/ask_question.py`
- [X] T014 [US1] Wrap the `is_albertos_scope()` call with
      `traced_stage(tracer, "shiruno.scope_classification",
      shiruno_in_scope=...)` in `src/shiruno/application/ask_question.py`
- [X] T015 [US1] Wrap the `embedding_provider.embed_query()` call with
      `traced_stage(tracer, "shiruno.query_embedding", provider=...,
      model=..., duration_ms=..., text_count=1)` in
      `src/shiruno/application/ask_question.py` (research.md R7a; FR-024)
- [X] T016 [US1] Wrap `search_similar_chunks()` + `select_sufficient_chunks()`
      with `traced_stage(tracer, "shiruno.retrieval", top_k=...,
      relevance_threshold=..., candidate_count=len(candidates),
      passed_filter_count=len(grounding_chunks))` in
      `src/shiruno/application/ask_question.py` (per-chunk enrichment
      deferred to US2)
- [X] T017 [US1] Wrap `limit_context_chars()` + `assemble_prompt()` with
      `traced_stage(tracer, "shiruno.context_assembly",
      selected_chunk_count=len(limited_chunks), char_count=...)` in
      `src/shiruno/application/ask_question.py` (truncation flag deferred to
      US2)
- [X] T018 [US1] Wrap the `llm_provider.complete()` call with
      `traced_stage(tracer, "shiruno.llm_generation", provider=...,
      model=..., input_tokens=..., output_tokens=..., latency_ms=...,
      supported=...)` in `src/shiruno/application/ask_question.py`, and
      also add one `shiruno.llm.provider_metrics.<key>` attribute per entry
      in `result.provider_metrics`, opaquely flattened with no branching on
      key names (error status handling deferred to US3; FR-023)
- [X] T019 [US1] Wrap the existing `record_conversation()` call in
      `src/shiruno/api/routers/chat.py` with `traced_stage(tracer,
      "shiruno.conversation_recording")`
- [X] T020 [US1] Thread the injected `tracer` from `chat.py`'s
      `post_chat()` into its `ask_question(...)` call in
      `src/shiruno/api/routers/chat.py`

**Checkpoint**: A grounded request now produces a complete, correctly-
ordered, timed span tree — the feature's core diagnostic value exists.

---

## Phase 4: User Story 6 - Observability never breaks or influences public chat (Priority: P1)

**Goal**: Prove, not merely assume, that tracing is inert with respect to
chat correctness, availability, and latency.

**Independent Test**: Run the same requests with observability disabled,
enabled with a working backend, and enabled with an unreachable backend;
confirm identical outcome/answer/success across all three (spec US6).

### Tests for User Story 6

- [X] T021 [P] [US6] Integration test in
      `tests/integration/test_chat_tracing.py`: for each outcome type
      (grounded, small_talk, out_of_scope, insufficient_information,
      unavailable), assert `ChatResponse` (status code + body) is
      byte-for-byte identical whether `create_app()` is given no tracer
      override (no-op), a working in-memory `Tracer`, or a `Tracer` built
      against a `TracerProvider` whose sole processor is a fake exporter
      that always raises (FR-032–034; SC-004)
- [X] T022 [P] [US6] Unit test in `tests/unit/test_observability.py`:
      `traced_stage()` swallows an exception raised from
      `tracer.start_as_current_span` (simulated via a fake `Tracer`) and
      the `with` block's body still executes normally
- [X] T023 [US6] Unit test in `tests/unit/test_observability.py`: a
      `traced_stage()` call against a `Tracer` whose processor's exporter
      blocks/raises on export returns to its caller without waiting on
      that exporter (confirms `BatchSpanProcessor`'s async, non-blocking
      behavior is what's actually in effect) (FR-033)
- [X] T023a [P] [US6] Integration test in
      `tests/integration/test_chat_tracing.py`: a chat request body
      containing an unrecognized extra field (e.g. `{"question": "...",
      "trace": true}`) produces an identical trace and response to the same
      request without that field — proving no client-supplied field can
      influence tracing (FR-003)

**Checkpoint**: Tracing is now provably unable to change chat behavior,
availability, or latency — the feature's core safety guarantee is verified,
not assumed.

---

## Phase 5: User Story 5 - Non-grounded outcomes show only the stages that actually ran (Priority: P1)

**Goal**: Confirm no span is ever fabricated for a stage a request's outcome
path never reached.

**Independent Test**: Send a small-talk message and a clearly out-of-scope
question; confirm each trace contains only the stages that outcome's own
pipeline path actually executes (spec US5).

### Tests for User Story 5

- [X] T024 [US5] Integration test in `tests/integration/test_chat_tracing.py`:
      a small-talk message's trace contains exactly
      `shiruno.security_or_cost_gates`, `shiruno.small_talk_classification`,
      `shiruno.conversation_recording` — no scope/embedding/retrieval/
      context/generation spans (SC-006)
- [X] T025 [US5] Integration test in `tests/integration/test_chat_tracing.py`:
      an out-of-scope question's trace contains exactly
      `shiruno.security_or_cost_gates`, `shiruno.small_talk_classification`,
      `shiruno.scope_classification`, `shiruno.conversation_recording` — no
      embedding/retrieval/context/generation spans (SC-006)
- [X] T026 [US5] Integration test in `tests/integration/test_chat_tracing.py`:
      a request with zero chunks passing relevance filtering
      (`insufficient_information`) produces a trace with no
      `shiruno.context_assembly` or `shiruno.llm_generation` span

**Checkpoint**: Span fabrication is proven absent for every short-circuit
outcome — no new implementation was needed, only verification that US1's
placement of `traced_stage()` calls at existing branch points already
guarantees this.

---

## Phase 6: User Story 2 - Operator inspects retrieval evidence and similarity scores (Priority: P1)

**Goal**: Enrich the `shiruno.retrieval` and `shiruno.context_assembly`
spans from US1 with the specific evidence an operator needs to debug RAG
quality.

**Independent Test**: Send a question that retrieves multiple candidate
chunks; confirm the trace shows candidate counts, similarity scores, which
chunks were selected versus dropped, and truncation status (spec US2).

### Implementation for User Story 2

- [X] T027 [US2] Extend the `shiruno.retrieval` span from T016 with
      `shiruno.retrieval.selected_count`,
      `shiruno.retrieval.selected.document_ids` (`list[str]`),
      `.selected.similarities` (`list[float]`), `.selected.labels`
      (`list[str]`) — one entry per selected chunk, in order — in
      `src/shiruno/application/ask_question.py` (data-model.md retrieval
      span; FR-010, FR-011)
- [X] T028 [US2] Add `shiruno.context.truncated` (`bool`,
      `len(limited_chunks) < len(grounding_chunks)`) to the
      `shiruno.context_assembly` span from T017 in
      `src/shiruno/application/ask_question.py` (FR-012)

### Tests for User Story 2

- [X] T029 [US2] Integration test in `tests/integration/test_chat_tracing.py`:
      a grounded request's `shiruno.retrieval` span exposes
      candidate/passed-filter/selected counts and, per selected chunk, a
      similarity score and source label — with no chunk content present by
      default (SC-002)
- [X] T030 [US2] Integration test in `tests/integration/test_chat_tracing.py`:
      a request whose relevant chunks exceed `MAX_CONTEXT_CHARS` produces a
      trace with `shiruno.context.truncated=true`; a request that fits
      entirely shows `false` (FR-012)

**Checkpoint**: Retrieval quality is now fully debuggable from trace data
alone, without querying the database.

---

## Phase 7: User Story 3 - Operator diagnoses failures and unavailable outcomes safely (Priority: P1)

**Goal**: Every failure path records a safe, categorized reason — never raw
exception text, provider bodies, or connection detail.

**Independent Test**: Force a provider failure and confirm the trace
clearly identifies the failing stage and a safe failure category, with no
raw exception text, credentials, or internal connection detail anywhere in
the trace (spec US3).

### Implementation for User Story 3

- [X] T031 [US3] On `LLMProviderError`, set the `shiruno.llm_generation`
      span (from T018) status to `ERROR` with
      `description=<FailureCategory string>` only — never
      `span.record_exception()` — in
      `src/shiruno/application/ask_question.py` (research.md R7; FR-025,
      FR-026)
- [X] T032 [US3] Set the `shiruno.security_or_cost_gates` span (from T012)
      status to `ERROR` with the safe gate name (`rate_limited`,
      `budget_exceeded`, `kill_switch`, `concurrency_limit`) on rejection,
      in `src/shiruno/application/ask_question.py` (FR-027)

### Tests for User Story 3

- [X] T033 [US3] Integration test in `tests/integration/test_chat_tracing.py`:
      a forced `LLMProviderError` produces a trace whose
      `shiruno.llm_generation` span shows `ERROR` status and a safe
      `failure_category`, with no raw exception text, credential, or
      connection detail anywhere in the span tree (FR-025, FR-026)
- [X] T034 [US3] Integration test in `tests/integration/test_chat_tracing.py`:
      budget-exceeded, kill-switch, and concurrency-limit rejections each
      produce a trace showing only the gate that rejected — no embedding,
      retrieval, or generation span (US3.3, FR-027)

**Checkpoint**: Every failure mode this system can produce is diagnosable
from safe trace data alone.

---

## Phase 8: User Story 4 - Sensitive content and hidden reasoning are never exported by default (Priority: P1)

**Goal**: The two independent content-capture toggles (FR-017) gate every
piece of potentially-sensitive text; everything else stays absent
regardless of configuration.

**Independent Test**: With content capture left at its default setting,
send requests covering every outcome type and confirm the full visitor
question, the full assistant answer, full retrieved document text, and any
hidden model reasoning are absent from every trace produced (spec US4).

### Implementation for User Story 4

- [X] T035 [US4] Gate a `shiruno.question` attribute on the
      `shiruno.conversation_recording` span behind
      `settings.OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT` in
      `src/shiruno/application/record_conversation.py` (FR-013, FR-017)
- [X] T036 [US4] Gate a `shiruno.llm.answer` attribute on the successful
      `shiruno.llm_generation` span (from T018) behind
      `settings.OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT` in
      `src/shiruno/application/ask_question.py` (FR-014, FR-017)
- [X] T037 [US4] Gate `shiruno.retrieval.selected.contents` (on the
      `shiruno.retrieval` span from T027) and `shiruno.context.prompt` (on
      the `shiruno.context_assembly` span from T017) behind
      `settings.OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT` in
      `src/shiruno/application/ask_question.py` (FR-015, FR-016, FR-017)
- [X] T038 [US4] Set `shiruno.tenant_id`/`shiruno.tenant_slug` on the
      `shiruno.conversation_recording` span, inside
      `record_conversation()`, only when `resolve_public_tenant()` resolves
      a tenant — never fabricated — in
      `src/shiruno/application/record_conversation.py` (research.md R8;
      FR-028, FR-029)

### Tests for User Story 4

- [X] T038a [US4] Integration test in `tests/integration/test_chat_tracing.py`:
      using the existing missing/inactive public-tenant fixture (Feature
      011), confirm the `shiruno.conversation_recording` span carries no
      `shiruno.tenant_id`/`shiruno.tenant_slug` attribute (FR-029)
- [X] T039 [US4] Integration test in `tests/integration/test_chat_tracing.py`:
      with default configuration, send one request per outcome type
      (grounded, insufficient_information, out_of_scope, unavailable,
      small_talk) and assert full question/answer/document/prompt text is
      absent from every span attribute across all of them (SC-003)
- [X] T040 [US4] Integration test in `tests/integration/test_chat_tracing.py`:
      enabling `OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT` alone reveals
      question/answer text but not document/prompt content, and vice versa
      for `OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT` — the two toggles
      are fully independent (spec Edge Cases; FR-017)
- [X] T041 [US4] Integration test in `tests/integration/test_chat_tracing.py`:
      no raw embedding vector value ever appears on the
      `shiruno.query_embedding` span, regardless of content-capture
      configuration (FR-018)
- [X] T042 [US4] Integration test in `tests/integration/test_chat_tracing.py`:
      using the existing fake/Ollama-shaped provider fixture, confirm
      `message.thinking`-equivalent content is absent from the
      `shiruno.llm_generation` span regardless of configuration (FR-019)
- [X] T043 [P] [US4] Unit test in `tests/unit/test_observability.py`: a
      `Settings` instance with a non-empty `OTEL_EXPORTER_OTLP_HEADERS`
      never has that value appear in any log record emitted by
      `configure_observability()` (FR-005)
- [X] T043a [P] [US4] Integration test in
      `tests/integration/test_chat_tracing.py`: serialize every span
      attribute produced by one grounded request and one forced-failure
      request, and assert none of `settings.DATABASE_URL`,
      `settings.AUTH_JWT_SECRET`, or `settings.ANTHROPIC_API_KEY` appear as
      a substring anywhere (FR-020)

**Checkpoint**: Privacy defaults are proven, not merely assumed, across
every outcome type and both content-capture toggles.

---

## Phase 9: User Story 7 - Operator correlates a conversation record with its trace (Priority: P1)

**Goal**: Confirm `request_id` — already set on the root span by US1 — is
sufficient to move between a `ConversationRecord` and its trace.

**Independent Test**: Generate a chat request with observability enabled,
then confirm the request's correlation identifier appears both on its
stored conversation record and on its trace (spec US7).

### Tests for User Story 7

- [X] T044 [US7] Integration test in `tests/integration/test_chat_tracing.py`:
      after a traced request, the resulting `ConversationRecord.request_id`
      (queried via the existing `db_session` fixture) matches the
      `shiruno.request_id` attribute on that request's captured root span
      (SC-005; FR-030)
- [X] T045 [US7] Integration test in `tests/integration/test_chat_tracing.py`:
      for one request, `UsageRecord.request_id`,
      `ConversationRecord.request_id`, and the root span's
      `shiruno.request_id` are all identical (FR-030, FR-031)

**Checkpoint**: An operator can move from a conversation record to its
trace and back using only `request_id` — no new implementation was needed
beyond what US1 already attached to the root span (research.md R9).

---

## Phase 10: User Story 9 - Everything that already worked keeps working (Priority: P1)

**Goal**: Prove zero regression anywhere else in the system.

**Independent Test**: Run the full existing automated suite unmodified in
intent and confirm every test still passes, both with observability
disabled and enabled (spec US9).

- [X] T046 [US9] Run the full existing automated suite
      (`uv run pytest`) with `OBSERVABILITY_ENABLED` left at its default
      (`false`) and confirm every pre-existing test still passes unmodified
      in intent (spec Testing Requirements #24–29)
- [X] T047 [US9] Run the full existing automated suite a second time with
      `OBSERVABILITY_ENABLED=true` set via test environment override and
      confirm identical pass results (SC-008)
- [X] T048 [P] [US9] Contract test in `tests/contract/` confirming the
      `ChatRequest`/`ChatResponse` JSON schema (fields, types, required-ness)
      is unchanged by this feature, alongside Feature 011's existing chat
      contract tests (FR-039)

**Checkpoint**: This feature has introduced zero regressions anywhere else
in the system.

---

## Phase 11: User Story 8 - Developer runs a local trace-visualization backend (Priority: P2)

**Goal**: An optional, fully opt-in Phoenix backend for local RAG-trace
visualization.

**Independent Test**: Start the normal local stack without the
visualization backend and confirm everything works exactly as before;
separately, start the visualization backend, send a chat request, and
confirm the request's trace appears in it with the expected stages (spec
US8).

- [X] T049 [US8] Add a `phoenix` service to `docker-compose.yml`, gated
      behind `profiles: ["observability"]`, using the official
      `arizephoenix/phoenix` image, exposing `6006` (UI + OTLP/HTTP) and
      `4317` (OTLP/gRPC) on the host, with a named volume for local trace
      storage; the existing `app` service remains outside this profile
      (research.md R10; FR-036, FR-037)
- [X] T050 [P] [US8] Document
      `OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006/v1/traces` (commented
      out, matching the empty default) in `.env.example`, referencing the
      `phoenix` service added in T049 (research.md R10)
- [X] T051 [P] [US8] Add a documentation section (README or `docs/`)
      explaining how to start Phoenix (`docker compose --profile
      observability up -d`), where the UI is (`http://localhost:6006`), how
      to locate a specific request's trace by `shiruno.request_id`, and how
      to inspect retrieval/generation spans (FR-038)
- [X] T052 [US8] Manually execute `specs/012-rag-observability/quickstart.md`
      end-to-end against the live local Docker stack with Phoenix running,
      confirming a real chat request's trace appears with the expected
      stage structure (SC-007; spec Testing Requirements #31, #32)

**Checkpoint**: A developer can visually debug RAG behavior locally,
entirely through an opt-in profile that never affects normal `docker
compose up -d`.

---

## Phase 12: Polish & Cross-Cutting Concerns

- [X] T053 Run `ruff check` and `mypy` across every new/modified file
      (`src/shiruno/infra/observability.py`, `api/deps.py`,
      `api/routers/chat.py`, `application/ask_question.py`,
      `application/record_conversation.py`, `config.py`, `main.py`,
      `docker-compose.yml` where applicable, and all new/modified test
      files) and fix any findings
- [X] T054 [P] Add a module docstring to
      `src/shiruno/infra/observability.py` documenting the
      no-op-tracer/dependency-injection pattern and the failure-isolation
      contract, matching this codebase's existing per-module docstring
      convention (research.md R1, R2)
- [X] T055 Review `tests/integration/test_chat_tracing.py` in full for
      redundant setup/fixture duplication across the US1/US2/US3/US4/US5/
      US6/US7/US9 test tasks above and consolidate shared fixtures
      (e.g., a helper that builds `create_app(tracer=...)` with an
      in-memory exporter) consistent with the rest of `tests/integration/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story.
- **User Story 1 (Phase 3)**: Depends on Foundational only. This is the
  feature's actual instrumentation backbone — every later story extends
  spans US1 creates.
- **User Stories 6, 5 (Phases 4–5)**: Depend on Foundational + US1 (they
  test/verify spans US1 created); no dependency on each other.
- **User Story 2 (Phase 6)**: Depends on US1 (extends the retrieval/
  context_assembly spans T016/T017 create).
- **User Story 3 (Phase 7)**: Depends on US1 (extends the
  security_or_cost_gates/llm_generation spans T012/T018 create).
- **User Story 4 (Phase 8)**: Depends on US1 (gates attributes on spans
  T017/T018/T019/T027 create) and, for T037, on US2's T027/T017 having run.
- **User Story 7 (Phase 9)**: Depends on US1 only (`request_id` is already
  on the root span from T011).
- **User Story 9 (Phase 10)**: Should run last among the P1 stories — it is
  the regression gate over everything above.
- **User Story 8 (Phase 11)**: Depends on Foundational only (Compose/docs
  work); independent of every other story's spans, but least valuable to
  verify before the span tree it visualizes actually exists — recommended
  last.
- **Polish (Phase 12)**: Depends on all desired stories being complete.

### Within Each User Story

- Where tests are listed, they exercise the implementation tasks in the
  same phase (not strict TDD order, since most of these tests need US1's
  already-built span tree as scaffolding — see the Foundational→US1→
  everything-else dependency above).
- Implementation tasks touching the same file (`ask_question.py`,
  `chat.py`) within a phase are sequential.

### Parallel Opportunities

- T004 and T007 (Foundational) can run in parallel with each other and
  with T002/T003 (different files: `config.py`, `.env.example` vs.
  `observability.py`).
- T008 (Foundational) can run in parallel with T004/T007 (a new,
  independent test file).
- Once Foundational is complete, US1 must land before any other story, but
  T009 (its test file) can be drafted in parallel with T010–T020 (a
  different file).
- After US1, Phases 4–10 (US6, US5, US2, US3, US4, US7, US9) touch largely
  disjoint attribute sets on the same shared files — recommended
  sequentially in the order listed above rather than by parallel staffing,
  since most edit the same few functions in `ask_question.py`.
- US8 (Phase 11) is fully independent of Phases 4–10 and can be staffed in
  parallel with any of them once US1 is done.

---

## Parallel Example: Foundational Phase

```bash
# Launch these together — different files, no dependency between them:
Task: "Add 7 new Settings fields in src/shiruno/config.py"
Task: "Document the 7 new settings in .env.example"
Task: "Create tests/unit/test_observability.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run T009, confirm a grounded request produces the
   full expected span tree via the in-memory exporter
5. This alone already delivers the feature's core diagnostic value (spec
   US1's own "Why this priority": "the entire reason the feature exists")

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → the span tree exists → **first checkpoint with real diagnostic
   value**
3. US6 → prove tracing cannot break chat (do this early — it's the
   feature's core safety invariant, and every later story adds more
   surface area this must keep holding for)
4. US5 → prove no span fabrication for short-circuit outcomes
5. US2 → retrieval evidence enrichment
6. US3 → safe failure/error representation
7. US4 → privacy-default proof + the two content-capture toggles
8. US7 → correlation proof
9. US9 → full regression gate
10. US8 (P2) → optional local Phoenix visualization, whenever convenient

### Recommended Team Strategy

Given how much of this feature shares `ask_question.py`/`chat.py` edits
(US1, US2, US3, US4 all touch the same functions at different points), this
feature is better suited to sequential single-developer implementation in
priority order than to parallel multi-developer staffing — the exception is
US8 (Phase 11), which is fully independent Compose/documentation work and
can proceed in parallel with any of Phases 4–10 once US1 exists.

---

## Notes

- `[P]` tasks touch different files with no dependency on an incomplete
  task in the same phase; tasks sharing a file within a phase are
  deliberately left sequential even when logically independent, to avoid
  merge conflicts in `ask_question.py` and
  `tests/integration/test_chat_tracing.py`.
- `[Story]` labels map every user-story-phase task back to spec.md's US1–US9
  for traceability.
- No task in this list adds a new database table/column, a new HTTP
  endpoint, or changes the public `/chat` contract — verified explicitly by
  T048/T046/T047 (US9).
- Commit after each task or logical group; verify tests fail before their
  corresponding implementation task lands, where a test task precedes its
  implementation task in the same phase.
- Constitution gate: Principle XIV was amended (v4.0.0 → v4.1.0, see
  `.specify/memory/constitution.md`) specifically to approve OpenTelemetry
  and a narrowly-scoped Phoenix before this tasks.md was generated — no
  further constitutional action is needed to implement this list.
