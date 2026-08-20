# Feature Specification: LLM / RAG Observability

**Feature Branch**: `012-rag-observability`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Feature 012 — LLM / RAG Observability: structured, vendor-neutral end-to-end tracing of the Shiruno chat/RAG pipeline for operator/developer diagnosis, built on OpenTelemetry with Phoenix as the first local-development backend, strictly separate from Feature 011's customer-facing Conversations & Analytics, disabled by default, never able to affect chat behavior or reliability, and never exposing sensitive content or hidden model reasoning by default."

## Clarifications

### Session 2026-08-20

- Q: Should content capture be a single on/off setting covering visitor questions, assistant answers, and retrieved document text together, or should visitor question/answer text be controlled separately from retrieved document/prompt content? → A: Two separate toggles — one for visitor question/answer content, one for retrieved document/prompt content. An operator with tracing-backend access has no tenant boundary at all (unlike Feature 011's tenant-scoped Conversation Record access), so this lets an operator enable document-content capture to debug retrieval quality across all tenants without also exposing free-form visitor question/answer text, a materially more sensitive and different category of data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator traces a grounded request end-to-end (Priority: P1)

An operator investigating a specific chat request opens its trace and sees the full execution path — from the request arriving, through the security/cost gates, classification, retrieval, context assembly, and the LLM call, to the final outcome and its recording — each stage showing how long it took.

**Why this priority**: This is the entire reason the feature exists — without a genuinely followable end-to-end path, nothing else in this feature has value.

**Independent Test**: With observability enabled, send a chat request that produces a grounded answer; retrieve its trace and confirm every pipeline stage that actually ran appears, in order, each with plausible timing.

**Acceptance Scenarios**:

1. **Given** observability is enabled, **When** a chat request produces a grounded answer, **Then** its trace shows one root entry for the request and one child entry for each pipeline stage that genuinely executed, in execution order.
2. **Given** a trace for a grounded request, **When** an operator inspects it, **Then** each stage shows how long that stage took.
3. **Given** observability is enabled, **When** a chat request completes with any outcome, **Then** the trace's root entry shows the final outcome and the request's correlation identifier.

---

### User Story 2 - Operator inspects retrieval evidence and similarity scores (Priority: P1)

An operator debugging why an answer was grounded, ungrounded, or used the "wrong" source opens the retrieval portion of a trace and sees exactly what was found: how many candidates were considered, their similarity scores, which ones were selected into the final answer, which were dropped, and whether the assembled context was truncated.

**Why this priority**: Retrieval quality is the most common source of "why did the assistant say that" investigations; without this, an operator is back to reconstructing retrieval behavior from database queries.

**Independent Test**: With observability enabled, send a question that retrieves multiple candidate chunks; confirm the trace shows candidate counts, similarity scores, which chunks were selected versus dropped, and the source each selected chunk came from — without needing to query the database directly.

**Acceptance Scenarios**:

1. **Given** a grounded or insufficient-information request that reached retrieval, **When** an operator inspects its trace, **Then** they can see how many candidates were retrieved, how many passed relevance filtering, and how many were ultimately used.
2. **Given** a retrieval trace, **When** an operator inspects a selected chunk, **Then** they can see its similarity score and a safe label identifying its source document.
3. **Given** a request where context was truncated before reaching the model, **When** an operator inspects the trace, **Then** truncation is visibly indicated.

---

### User Story 3 - Operator diagnoses failures and unavailable outcomes safely (Priority: P1)

An operator investigating a failed or unavailable response can see which stage failed and a safe, categorized reason, without needing raw provider error text or credentials to ever leave the system.

**Why this priority**: Diagnosing failures is one of the two or three most common reasons an operator opens a trace at all; it must work without becoming a new place secrets or raw provider detail can leak.

**Independent Test**: With observability enabled, force a provider failure and confirm the trace clearly identifies the failing stage and a safe failure category, while containing no raw exception text, credentials, or internal connection detail anywhere in the trace.

**Acceptance Scenarios**:

1. **Given** a request that fails because the assistant is unavailable, **When** an operator inspects its trace, **Then** they can see which stage failed and a safe, human-meaningful failure category.
2. **Given** any failed request's trace, **When** an operator inspects it, **Then** no raw provider exception text, credential, or internal connection detail is present anywhere in it.
3. **Given** a request that is rejected before reaching the assistant's core decision logic (e.g., rate-limited), **When** an operator inspects its trace, **Then** the trace reflects that rejection without fabricating downstream stages that never ran.

---

### User Story 4 - Sensitive content and hidden reasoning are never exported by default (Priority: P1)

An operator using the default configuration can fully debug pipeline behavior — timing, retrieval evidence, outcomes, provider/token metadata — without the visitor's actual question text, the assistant's actual answer text, the full retrieved document content, or any hidden model reasoning ever leaving the system.

**Why this priority**: This is the non-negotiable privacy guarantee the entire feature must hold inside of; every other story's value depends on this never being compromised, especially since traces may leave the system boundary toward a third-party backend.

**Independent Test**: With observability enabled and content capture left at its default setting, send requests covering every outcome type and confirm the full visitor question, the full assistant answer, full retrieved document text, and any hidden model reasoning are absent from every trace produced, while the trace remains useful for diagnosing what happened.

**Acceptance Scenarios**:

1. **Given** the default configuration, **When** any chat request is traced, **Then** the full visitor question text does not appear anywhere in the trace.
2. **Given** the default configuration, **When** any chat request is traced, **Then** the full assistant answer text does not appear anywhere in the trace.
3. **Given** the default configuration, **When** a grounded request is traced, **Then** the full text of retrieved document chunks does not appear anywhere in the trace — only safe metadata such as identifiers, labels, and scores.
4. **Given** any request answered by a provider capable of returning hidden reasoning content, **When** the request is traced, **Then** that hidden reasoning content is absent from the trace regardless of configuration.
5. **Given** any request, **When** it is traced, **Then** no raw embedding vector values appear anywhere in the trace.

---

### User Story 5 - Non-grounded outcomes show only the stages that actually ran (Priority: P1)

An operator inspecting a small-talk or out-of-scope request's trace sees exactly the stages that ran for that request — never a fabricated retrieval or generation stage that the request never actually reached.

**Why this priority**: A trace that shows stages which never ran would actively mislead an operator during debugging, which is worse than having no trace at all.

**Independent Test**: With observability enabled, send a small-talk message and a clearly out-of-scope question; confirm each trace contains only the stages that outcome's own pipeline path actually executes.

**Acceptance Scenarios**:

1. **Given** a message classified as small talk, **When** an operator inspects its trace, **Then** it shows only the request/security gates, the small-talk classification stage, and conversation recording — never embedding, retrieval, or generation.
2. **Given** a question classified as out of scope, **When** an operator inspects its trace, **Then** it shows the classification stages that ran but never embedding, retrieval, or generation.

---

### User Story 6 - Observability never breaks or influences public chat (Priority: P1)

Whether observability is turned off, turned on, or its backend is completely unreachable, every visitor's chat experience — the answer they receive, how long it takes, and whether it succeeds — remains identical.

**Why this priority**: This is the core principle the entire feature exists inside of: observability may only ever watch the system, never participate in it. A violation here would turn a diagnostic feature into a reliability risk.

**Independent Test**: Run the same set of requests three times — with observability disabled, with observability enabled and a working backend, and with observability enabled and an unreachable backend — and confirm every response's outcome, answer, and success/failure status is identical across all three runs.

**Acceptance Scenarios**:

1. **Given** observability is disabled, **When** any chat request is made, **Then** its outcome and answer are identical to what they would be if observability had never been introduced.
2. **Given** observability is enabled but its backend is unreachable, slow, or misconfigured, **When** a chat request is made, **Then** the visitor still receives their normal, successful answer.
3. **Given** any chat request, **When** it is processed, **Then** no part of the assistant's decision-making (retrieval, scope, answerability, provider selection, tenant resolution) is influenced by whether observability is enabled.
4. **Given** a public client, **When** it sends any request field intended to influence tracing, **Then** that field has no effect.

---

### User Story 7 - Operator correlates a conversation record with its trace (Priority: P1)

An operator looking at a specific entry in a tenant's conversation history (from Feature 011) can find the matching trace using only the identifier already visible on that conversation record.

**Why this priority**: Without this, the two systems are diagnostically disconnected — an operator would have no reliable way to move from "a customer reported this specific conversation" to "here is what actually happened internally."

**Independent Test**: Generate a chat request with observability enabled, then confirm the request's correlation identifier appears both on its stored conversation record and on its trace, and can be used to find one from the other.

**Acceptance Scenarios**:

1. **Given** a chat request processed with observability enabled, **When** an operator has its correlation identifier, **Then** they can locate both its conversation record and its trace using that identifier.
2. **Given** a trace, **When** an operator inspects its root entry, **Then** the same correlation identifier used elsewhere in the system for this request is present.

---

### User Story 8 - Developer runs a local trace-visualization backend (Priority: P2)

A developer working locally starts an optional trace-visualization backend alongside the normal development stack, sends a chat request, and sees that request's full trace rendered visually — without this backend being required for normal day-to-day development.

**Why this priority**: Valuable for productive local RAG debugging, but the feature already delivers its core diagnostic value through the underlying trace data itself; visualization is a developer-experience enhancement on top, not the foundation.

**Independent Test**: Start the normal local development stack without the visualization backend and confirm everything works exactly as before; separately, start the visualization backend, send a chat request, and confirm the request's trace appears in it with the expected stages.

**Acceptance Scenarios**:

1. **Given** the normal local development stack, **When** it is started without the optional trace-visualization backend, **Then** every existing capability works exactly as before this feature.
2. **Given** the optional trace-visualization backend is started and observability is enabled and pointed at it, **When** a real chat request is made, **Then** the operator can find and inspect that request's trace in the visualization backend's interface.

---

### User Story 9 - Everything that already worked keeps working (Priority: P1)

Every visitor chatting with the assistant, every tenant administrator using conversation history and analytics, every knowledge-base management operation, and every existing security and isolation guarantee continues to behave exactly as before — this feature only adds an optional, invisible diagnostic layer alongside the existing system.

**Why this priority**: This feature touches the most heavily-used code path in the entire system (every chat request) and introduces a new optional external dependency; regressing any previously-shipped capability would be a failure regardless of how good the new tracing is.

**Independent Test**: Run the full existing automated suite (public chat outcomes, small talk, source hiding, tenant isolation, knowledge administration, conversation analytics) unmodified in intent and confirm every test still passes, both with observability disabled and enabled.

**Acceptance Scenarios**:

1. **Given** the public assistant, **When** a visitor asks a question that previously produced any existing outcome, **Then** the same question produces the same outcome and the same visible answer as before this feature.
2. **Given** a tenant administrator, **When** they browse conversation history or analytics, **Then** the data and behavior are unchanged by this feature.
3. **Given** the existing tenant-isolation, knowledge-administration, rate-limit, budget, and provider tests, **When** the full automated suite runs, **Then** all of them still pass, unmodified in intent.

---

### Edge Cases

- What happens when observability is enabled but the trace backend is completely unreachable for an entire request? → The visitor's chat response is unaffected; the export failure is handled the same way any other best-effort, non-blocking background operation is — it does not surface to the caller and does not retry indefinitely.
- What happens when a request is rejected by rate limiting before reaching the assistant's core decision logic? → It still produces a trace showing the gate that rejected it, without fabricating any stage beyond that point.
- What happens when the public reference tenant cannot be resolved for a given request (see Feature 011)? → The trace reflects what actually happened; it does not fabricate tenant identity, and this has no bearing on whether the visitor's answer succeeds.
- What happens when a request fails partway through a stage (e.g., the embedding call itself fails)? → The trace shows that stage as failed with a safe category, and no later stage that never ran is fabricated.
- What happens when only document/prompt content capture is explicitly enabled, but not question/answer capture? → Retrieved document and prompt-context content appears in the trace as configured, while the visitor's question and the assistant's answer remain absent, exactly as if question/answer capture had never been discussed — the two settings are fully independent.
- What happens when content capture (either setting) is explicitly enabled for local development and then a request is traced? → The richer content is captured only because an operator explicitly and deliberately enabled that specific setting; the default behavior for every other installation, and for the other content-capture setting if left off, remains unaffected.
- What happens if two chat requests are in flight at the same time? → Each produces its own independent, correctly-attributed trace; concurrent requests never cross-contaminate each other's trace data.
- What happens to trace data when the trace-visualization backend restarts or is not running at feature-install time? → Normal chat operation is completely unaffected; only trace visualization is unavailable.

## Requirements *(mandatory)*

### Functional Requirements

**Tracing foundation and configuration**

- **FR-001**: The system MUST support emitting structured, end-to-end diagnostic traces of the chat/RAG pipeline through a vendor-neutral tracing standard, not a proprietary backend-specific API called directly from application/domain code.
- **FR-002**: Tracing MUST be disabled by default; an operator MUST explicitly enable it through server configuration.
- **FR-003**: No field in the public chat request MUST be able to enable, disable, or otherwise influence tracing behavior.
- **FR-004**: Trace export destination and any associated credentials MUST be configured server-side only; missing or invalid trace-backend configuration MUST fail safely (tracing simply does not export) rather than affecting the chat response.
- **FR-005**: Any credential or header used to authenticate to a trace backend MUST NOT appear in application logs.

**Root trace and pipeline stages**

- **FR-006**: When tracing is enabled, every chat request that reaches the assistant's own processing logic (i.e., is not rejected earlier by request-level validation) MUST produce exactly one root trace entry for that request.
- **FR-007**: The root trace entry MUST carry the request's correlation identifier, its final outcome, and, when applicable, the provider/model that handled it.
- **FR-008**: A trace MUST contain a distinct entry for each pipeline stage that genuinely executed for that request (e.g., security/cost gates, small-talk classification, scope classification, query embedding, retrieval, context assembly, LLM generation, conversation recording) and MUST NOT contain an entry for any stage the request's outcome path did not reach.
- **FR-009**: Each stage entry MUST reflect how long that stage took to execute.

**Retrieval observability**

- **FR-010**: When retrieval executes, its trace entry MUST expose the configured retrieval parameters (result limit, relevance threshold), how many candidates were retrieved, how many passed relevance filtering, and how many were ultimately used.
- **FR-011**: For each chunk selected into the final answer, the trace MUST expose its similarity score and a safe label identifying its source document, without exposing the full text of that chunk by default.
- **FR-012**: The trace MUST make it possible to determine whether the assembled context was truncated before being sent to the model.

**Content and privacy policy**

- **FR-013**: By default, the full text of the visitor's question MUST NOT appear anywhere in a trace.
- **FR-014**: By default, the full text of the assistant's answer MUST NOT appear anywhere in a trace.
- **FR-015**: By default, the full text of any retrieved document chunk MUST NOT appear anywhere in a trace.
- **FR-016**: The complete assembled prompt/system-context sent to the model MUST NOT appear in a trace by default; safe structural metadata (such as context size and chunk count) MAY appear instead.
- **FR-017**: Content capture MUST be controlled by two independent, separately-documented, off-by-default settings — one governing visitor question/assistant answer capture, and one governing retrieved document/prompt-context capture — so an operator can enable one category (e.g., document content, to debug retrieval quality) without also enabling the other (visitor question/answer text, a materially more sensitive category since an operator viewing traces has no tenant boundary limiting which tenant's content they can see). Neither setting MUST be on unless an operator deliberately enables it.
- **FR-018**: No raw embedding vector values MUST ever appear in a trace, regardless of configuration.
- **FR-019**: No hidden model reasoning/chain-of-thought content MUST ever appear in a trace, regardless of configuration and regardless of whether the active provider is capable of returning it.
- **FR-020**: No credential, authentication token, or database connection secret MUST ever appear in a trace.

**Generation and embedding metadata**

- **FR-021**: When a generation call is attempted, its trace entry MUST expose the provider and model identity, input/output token counts where available, and timing information, without exposing raw provider response bodies.
- **FR-022**: The generation trace entry MUST expose the structured answerability decision (whether the model judged the retrieved context sufficient) as a direct signal, not something inferred by parsing the answer text.
- **FR-023**: Provider-specific performance metrics MAY be included as clearly-namespaced supplementary data without introducing provider-specific branching in the pipeline's own decision logic.
- **FR-024**: When embedding generation executes, its trace entry MUST expose the embedding provider, how many texts were embedded, timing, and success/failure — never the resulting vectors and never full document text captured solely for this purpose.

**Failure and outcome visibility**

- **FR-025**: An operator MUST be able to distinguish, from trace data alone, at least: no usable context was found, the model judged context insufficient, the model judged context sufficient, the assistant was unavailable (which, per the existing `FailureCategory` taxonomy from feature 004-rag-answerability-and-ollama-performance, covers both a genuine provider/network failure and a structured response that failed to parse — these two are not separately distinguishable today, and this feature does not add new plumbing to split them), the request was out of scope, and the request was small talk.
- **FR-026**: A failed stage's trace entry MUST record a safe, human-meaningful failure category and MUST NOT record raw exception text, provider response bodies, or connection details that could reveal internal infrastructure.
- **FR-027**: A request rejected before reaching the assistant's core decision logic (e.g., by rate limiting) MUST be reflected in its trace without fabricating any later stage that never executed.

**Tenant metadata**

- **FR-028**: Tenant identity attached to a trace MUST be derived the same way it already is for conversation recording (server-resolved) — never from any client-supplied value.
- **FR-029**: When the reference tenant cannot be resolved for a request, the trace MUST NOT fabricate a tenant identity.

**Correlation**

- **FR-030**: The same correlation identifier already used for a request's conversation record and usage accounting MUST also be attached to that request's trace, so an operator can move between them.
- **FR-031**: This correlation MUST NOT require the trace backend and the application database to depend on each other's availability.

**Reliability (never breaks chat)**

- **FR-032**: A failure to export, record, or otherwise deliver trace data MUST NOT change the chat response returned to the visitor, its outcome, or its success/failure status.
- **FR-033**: Trace delivery MUST NOT block the visitor-facing response beyond what the underlying tracing mechanism's normal non-blocking/background delivery already involves.
- **FR-034**: No part of retrieval, scope classification, answerability, provider selection, cost/abuse enforcement, or tenant resolution MUST behave differently depending on whether tracing is enabled or whether its backend is reachable.

**Sampling**

- **FR-035**: Trace sampling MUST be configurable by an operator; a reasonable default MUST be provided for local development without requiring configuration.

**Local development trace visualization**

- **FR-036**: A local trace-visualization backend MUST be runnable as an optional addition to the existing local development stack, never as a requirement for normal day-to-day operation.
- **FR-037**: Normal local development startup MUST continue to work unchanged when the optional trace-visualization backend is not started.
- **FR-038**: Documentation MUST explain how to start the optional trace-visualization backend, where to view it, and how to locate a specific request's trace within it.

**Preserving existing behavior**

- **FR-039**: The public chat request and response contract MUST remain unchanged by this feature.
- **FR-040**: Existing tenant conversation history, analytics, knowledge-base administration, and tenant-isolation behavior (Features 009, 010, 011) MUST remain unchanged by this feature.
- **FR-041**: Public source-hiding behavior MUST remain unchanged by this feature.
- **FR-042**: This feature MUST NOT introduce a tenant-administrator-facing or customer-facing view of trace data.

### Key Entities

- **Trace**: The complete diagnostic record of one chat request's execution path, produced only when tracing is enabled. Distinct from, and never a replacement for, the tenant-owned Conversation Record from Feature 011 — a trace is operator/developer-facing diagnostic data, not durable customer product data.
- **Pipeline Stage Entry**: One segment of a trace representing a single stage of the pipeline (request gates, classification, embedding, retrieval, context assembly, generation, conversation recording) that genuinely executed for that request, with its own timing and safe metadata. Never created for a stage the request's outcome path did not reach.
- **Retrieval Evidence**: Metadata attached to a trace's retrieval stage — candidate/selected/dropped counts, similarity scores, safe source labels, truncation status — deliberately excluding full chunk text by default.
- **Generation Metadata**: Metadata attached to a trace's generation stage — provider/model identity, token counts, timing, and the structured answerability decision — deliberately excluding raw provider responses and hidden reasoning.
- **Correlation Identifier**: The identifier already used to tie a request's Conversation Record and usage accounting together, also attached to that request's Trace, so an operator can move between the two.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of grounded chat requests made while tracing is enabled, an operator can retrieve a trace showing every pipeline stage that actually executed, in order, each with timing, verified by automated tests.
- **SC-002**: For 100% of traced requests that reach retrieval, similarity scores and selected/dropped chunk evidence are inspectable without querying the database directly.
- **SC-003**: 0% of traces produced under the default configuration contain the full visitor question, the full assistant answer, full retrieved document text, or any hidden model reasoning content, verified by automated tests across every outcome type.
- **SC-004**: 100% of chat requests succeed with identical outcome and answer whether tracing is disabled, enabled with a working backend, or enabled with a completely unreachable backend, verified by automated tests.
- **SC-005**: An operator can locate the trace for a specific conversation history entry using only the identifier already visible on that entry, verified by an automated test.
- **SC-006**: 0% of traces for small-talk or out-of-scope requests contain a retrieval, embedding, or generation stage entry.
- **SC-007**: A developer can start the optional local trace-visualization backend and, without any change to normal development startup, see a real chat request's full trace appear in it.
- **SC-008**: The full pre-existing automated suite (public chat, tenant isolation, knowledge administration, conversation analytics) passes unmodified in intent, both with tracing disabled and enabled.

## Assumptions

- Tracing is implemented on a vendor-neutral, industry-standard tracing foundation (OpenTelemetry), with the initial local-development trace-visualization backend being Phoenix, per this feature's explicit architectural direction — this is treated as a settled constraint of the feature, not an open product question. Other trace backends remain viable later without re-instrumenting the application, since instrumentation is expressed only in vendor-neutral terms.
- "Every accepted chat request" (for root-trace purposes) means every request that reaches the assistant's own request-handling logic — i.e., has already passed basic HTTP-level payload/schema validation. Requests rejected purely at that earlier validation layer are not traced, since instrumenting that layer would mean instrumenting shared web-framework internals rather than the Shiruno-owned pipeline this feature targets.
- Content-capture configuration is two independent, explicit, off-by-default settings (question/answer content; document/prompt content — see Clarifications) an operator deliberately enables wherever richer local debugging is wanted, rather than being inferred from an environment/deployment-stage concept, which does not otherwise exist in this system today. The safety property that matters is "off unless deliberately turned on, per category," not which specific environment happens to be running.
- A reasonable default sample rate is applied when tracing is enabled and no explicit rate is configured, favoring complete visibility for local development; production operators are expected to configure a lower rate deliberately for their own traffic volume.
- Whether a durable, persisted correlation field is added to the existing Conversation Record, or the correlation is achieved some other way, is a planning-phase architecture decision — this specification only requires that an operator can move from a conversation record to its trace and back using an identifier already common to both.
- The optional local trace-visualization backend runs only in local/development contexts in this feature; production trace-backend deployment, retention automation, and access-control policy are explicitly out of scope and deferred.
- This feature's own automated verification does not require a real trace-visualization backend, real Ollama, GPU resources, or Anthropic credentials; an in-memory or equivalent test-only trace capture mechanism is used instead. Live end-to-end verification may additionally use the local Docker Compose stack with the optional backend running.
- No new administrator role, tenant-facing UI, or customer-visible capability is introduced; this feature is exclusively an operator/developer-facing diagnostic capability layered alongside the existing system.
