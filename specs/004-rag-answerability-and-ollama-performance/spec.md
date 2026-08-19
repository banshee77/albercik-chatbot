# Feature Specification: RAG Answerability & Ollama Performance

**Feature Branch**: `004-rag-answerability-and-ollama-performance`

**Created**: 2026-08-18

**Status**: Complete (2026-08-19) — all success criteria met against the
amended SC-001 (see "SC-001 acceptance-criterion amendment" under Success
Criteria); question #6 retained as a known, documented MVP limitation.

**Input**: User description: "Improve Albercik's answerability classification and Ollama latency without changing the retrieval architecture. The current evaluation shows grounded accuracy 20/20, out-of-scope accuracy 3/3, insufficient-information rejection 0/7, false-grounded rate 7/7 — the LLM often correctly recognizes context does not support an answer, or wrongly infers a negative fact from absent evidence, but the application still marks the outcome as grounded. Ollama grounded calls take 4–19s. Fix answerability classification after retrieval (structured LLM result, not string matching), add an explicit no-negative-inference rule, keep both LLM providers on one shared contract, add a server-controlled Ollama thinking toggle and measure its latency impact via A/B evaluation, and extend the evaluation tooling to report the new metrics — all without changing retrieval architecture, adding new components (reranking, hybrid search, agents, frameworks), or touching the frozen eval dataset's expected outcomes."

## Clarifications

### Session 2026-08-18

- Q: Should the insufficient-information rejection floor (SC-002) and false-grounded ceiling (SC-003) stay at the ≥85% / ≤15% numbers guessed when writing the spec, or should they be different? → A: Keep ≥85% / ≤15%.
- Q: When the model's structured answerability output is malformed or fails to parse, should the chatbot show the normal insufficient-information message, or a distinct service-error message? → A: Insufficient-information message. **Superseded during `/speckit-plan` (2026-08-18):** malformed/schema-invalid/unparseable structured output now maps to the existing `unavailable` outcome (a provider/protocol failure), not `insufficient_information` — see FR-008. Rationale: a parse failure is not evidence about the knowledge base one way or the other, and silently reporting it as "insufficient information" would hide real provider/protocol failures behind a misleading, confidence-bearing business outcome. `insufficient_information` is reserved for a genuine, successfully-parsed `supported=false` decision.
- Q: Do the accuracy acceptance targets (SC-001 through SC-003) need to pass on the Ollama backend only, or on both the Ollama and Anthropic backends? → A: Ollama only.

### Session 2026-08-19

- Q: The deterministic `qwen3:8b` evaluation reaches 19/20 (95%) grounded accuracy, one short of SC-001's original 20/20 target, with the single remaining case (#6) being a semantic-inference/negation edge case rather than a retrieval or safety failure — and a prior targeted prompt fix for this class of case caused a severe measured regression elsewhere. Should the feature keep chasing 20/20, or should SC-001 be amended to accept 19/20 for the MVP? → A: Amend SC-001 to grounded accuracy ≥19/20 (≥95%); accept #6 as a known, documented MVP limitation; do not attempt further prompt tuning to close it. See "SC-001 acceptance-criterion amendment" under Success Criteria for the full decision record.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chatbot honestly admits when it doesn't know (Priority: P1)

An Albertos website visitor asks Albercik a question that is on-topic (about
Albertos) but not actually answered by anything in the knowledge base — for
example, asking about a service, policy, or fact the retrieved documents
never mention. Today the chatbot frequently answers anyway, presenting a
fabricated or unsupported claim as if it were grounded fact. This story
delivers the core fix: when the retrieved context does not actually support
an answer, the chatbot must say it doesn't have enough information instead
of presenting an ungrounded answer as if it were reliable.

**Why this priority**: This is the dominant failure mode today (0/7
insufficient-information cases correctly rejected, 7/7 falsely marked
grounded). It is a trust and correctness problem for a customer-support
chatbot: confidently wrong answers are worse than admitting "I don't know."
Fixing this delivers value on its own, independent of any latency work.

**Independent Test**: Run the frozen 30-question evaluation benchmark against
the updated system. Can be fully tested by confirming that questions
previously misclassified as "grounded" with no real supporting context are
now classified as "insufficient information," while genuinely answerable
and out-of-scope questions remain correctly classified.

**Acceptance Scenarios**:

1. **Given** a question about Albertos for which retrieval returns
   context that does not actually contain the answer, **When** the chatbot
   processes the question, **Then** it responds with the standard
   insufficient-information message rather than a fabricated answer.
2. **Given** a question for which retrieval returns context that does
   contain the answer, **When** the chatbot processes the question,
   **Then** it returns the grounded answer along with its supporting
   sources, unchanged from current behavior.
3. **Given** a question that is out of scope for Albertos, **When** the
   chatbot processes the question, **Then** it is still correctly
   classified as out-of-scope, unaffected by this change.

---

### User Story 2 - Chatbot never invents a negative fact from silence (Priority: P2)

A visitor asks whether Albertos offers or allows something specific (e.g.,
"Does Albertos offer online training?" or "Can I rent a karate-gi?"). The
retrieved context simply doesn't mention it either way. Today the model
sometimes converts that silence into a confident "No, Albertos does not
offer/allow that" — which is a fabricated negative claim, not something the
knowledge base actually states. This story ensures the chatbot instead
recognizes it lacks the information, rather than asserting a negative it
cannot support.

**Why this priority**: This is a specific, higher-risk sub-case of Story 1 —
a confidently wrong "no" is worse for a customer-support bot than a generic
non-answer. It depends on the same structured-answerability mechanism as
Story 1, so it is naturally delivered second.

**Independent Test**: Using targeted example questions where context is
silent on the asked-about topic (not merely context-free, but topically
adjacent and silent), confirm the chatbot responds with
insufficient-information rather than a fabricated negative statement.

**Acceptance Scenarios**:

1. **Given** retrieved context that discusses a topic area but never states
   that a specific thing is unavailable, not offered, prohibited, or
   nonexistent, **When** the chatbot answers a question asking about that
   specific thing, **Then** it does not state a negative conclusion and
   instead reports insufficient information.
2. **Given** retrieved context that explicitly states something is
   unavailable, not offered, or prohibited, **When** the chatbot answers a
   related question, **Then** it may state that explicit negative fact,
   grounded in the source.

---

### User Story 3 - Faster answers from the local model (Priority: P3)

An operator running Albercik on the local Ollama backend wants grounded
answers to come back noticeably faster. Today grounded Ollama responses
commonly take 4–19 seconds because the model's internal reasoning/thinking
mode is enabled by default. This story gives the operator a server-side
setting to disable that mode, backed by a measured comparison so the
decision is evidence-based rather than assumed.

**Why this priority**: Valuable but independent of correctness — it improves
user-perceived responsiveness without changing what the chatbot decides to
answer. It is naturally third because the answerability fix (Stories 1–2)
must be in place before latency numbers are compared, so the comparison
reflects the corrected behavior.

**Independent Test**: With the answerability change already deployed, run
the same frozen 30-question benchmark once with the model's thinking mode
on and once with it off, and produce a report comparing accuracy and
latency between the two runs. Can be fully tested by inspecting that report
and confirming the configuration is applied server-side only.

**Acceptance Scenarios**:

1. **Given** the local model backend configured with thinking mode
   disabled, **When** a grounded question is answered, **Then** the
   response is produced without the model's extended reasoning step.
2. **Given** the same 30-question benchmark run twice (thinking on vs.
   off), **When** results are compared, **Then** a report shows accuracy
   and latency (average, p50, p95) for both configurations side by side.
3. **Given** a public chatbot request, **When** the request attempts to
   influence the thinking-mode setting, **Then** the attempt has no effect
   — the setting remains whatever the server operator configured.

---

### Edge Cases

- What happens when the language model's structured answerability response
  is malformed, incomplete, or fails to parse? The system must fail safely
  to the existing "provider unavailable" outcome — never "grounded," and
  never "insufficient information" either, since a parse failure is not
  actual evidence about the knowledge base (see FR-008).
- What happens when retrieved content itself contains text engineered to
  make the model claim "supported: true" regardless of actual relevance
  (prompt injection via ingested documents)? The final outcome must still
  be decided by the application, not dictated by retrieved or user content.
- What happens when the language model provider is unavailable or times out
  while producing the structured result? The existing "provider unavailable"
  behavior must still apply.
- What happens when a question is answerable from context but the answer is
  partially supported (some sub-claims grounded, others not)? The system
  is only required to produce a single supported/not-supported judgment for
  the overall answer, per this feature's scope — partial-support nuance is
  not required.
- What happens when the local model backend does not return the optional
  performance telemetry fields (e.g., token counts) for a given response?
  Reporting must omit or clearly mark those fields as unavailable rather
  than displaying fabricated numbers.
- What happens when out-of-scope classification and answerability
  classification would both apply to the same question? Out-of-scope
  classification (a pre-existing, separate step) still takes precedence and
  is unaffected by this feature.

## Requirements *(mandatory)*

### Functional Requirements

**Answerability correctness**

- **FR-001**: The system MUST determine, as part of answering a question,
  whether the retrieved context actually supports answering it, and MUST
  base the "grounded" vs. "insufficient information" outcome on that
  determination rather than merely on whether the model produced text.
- **FR-002**: When the context is judged to support an answer, the system
  MUST return the answer together with its supporting sources, as it does
  today.
- **FR-003**: When the context is judged not to support an answer, the
  system MUST return the standard insufficient-information response and
  MUST NOT present the answer text or retrieved sources as if they were a
  factual answer.
- **FR-004**: The answerability determination and the answer text MUST be
  produced together from a single reasoning step per question — the system
  MUST NOT issue a second, separate call solely to check answerability.
- **FR-005**: The system MUST NOT infer a negative factual claim (e.g.,
  "X is not offered/available/allowed") solely because the retrieved
  context is silent on the topic. A negative claim MAY only be presented
  when the retrieved context explicitly states it.
- **FR-006**: The rule in FR-005 MUST be enforced as an instruction the
  system itself supplies to the model, not as something dependent on the
  content of retrieved documents.
- **FR-007**: The system MUST NOT determine the grounded/insufficient
  outcome by pattern-matching or scanning the natural-language answer text
  for specific phrases; the determination must come from a distinct,
  explicit answerability signal.
- **FR-008**: If the model's answerability signal is missing, malformed, or
  unparseable, the system MUST NOT default to "grounded," and MUST NOT
  report it as "insufficient information" either — a parse failure is a
  provider/protocol failure, not evidence about the knowledge base, so it
  MUST be treated as a provider failure and produce the existing
  `unavailable` outcome (the same outcome an outright provider error
  already produces). "Insufficient information" is reserved for a
  successfully-parsed, explicit `supported=false` decision.

**Provider consistency**

- **FR-009**: Both the local model backend and the hosted model backend
  MUST support the same answerability-plus-answer behavior, producing
  outcomes through one shared, provider-independent contract.
- **FR-010**: Logic that decides whether an outcome is grounded or
  insufficient MUST NOT vary by which model backend produced the answer,
  and MUST NOT need to know backend-specific response formats.
- **FR-011**: Existing retrieval behavior (what gets retrieved, current
  similarity threshold, current result count, existing scope
  classification, existing chunking, existing context-size limit) MUST
  remain unchanged by this feature.

**Local-model responsiveness**

- **FR-012**: The system MUST provide a server-side, operator-controlled
  setting for whether the local model's extended reasoning ("thinking")
  mode is used when generating grounded answers.
- **FR-013**: A public chatbot request MUST NOT be able to change or
  override the thinking-mode setting; it is controlled only by server
  configuration.
- **FR-014**: Changing the thinking-mode setting MUST require only a
  configuration change, not a code change.
- **FR-015**: The hosted model backend's behavior MUST be unaffected by the
  thinking-mode setting.
- **FR-016**: The system MUST NOT surface the model's internal
  reasoning/thinking content to end users, and MUST NOT persist it in usage
  or telemetry records.

**Performance visibility**

- **FR-017**: For local-model responses, the system MUST capture available
  native performance information (e.g., total time, time spent loading vs.
  generating, and token counts) when the backend provides it, without
  requiring core question-answering logic to depend on backend-specific
  data.
- **FR-018**: The system MUST continue to record usage per request
  (provider identity, model identity, and token counts where semantically
  available) consistent with current usage-accounting behavior, and MUST
  continue to exclude local-model usage from the hosted-provider monetary
  budget.
- **FR-019**: The system MUST NOT fabricate token counts or performance
  figures when a backend does not report them; missing data must be shown
  as missing, not estimated.
- **FR-020**: The system MUST NOT persist reasoning/thinking text, full
  prompts, retrieved document content, or secrets for the sole purpose of
  performance telemetry.

**Evaluation & measurement**

- **FR-021**: The evaluation tooling MUST continue to run the existing
  frozen benchmark question set without modifying its expected outcomes,
  and MUST continue reporting, per question: expected outcome, actual
  outcome, pass/fail, and latency.
- **FR-022**: The evaluation tooling MUST additionally report, where the
  data is available: input token count, output token count, generation
  tokens-per-second (`output tokens / generation time`), prompt-eval
  tokens-per-second (`input tokens / prompt-processing time`), and model
  load duration, per question and/or in aggregate.
- **FR-023**: The evaluation tooling MUST continue reporting the aggregate
  summary metrics: overall pass rate, grounded accuracy, insufficient-
  information rejection rate, out-of-scope accuracy, and false-grounded
  count/rate.
- **FR-024**: The evaluation tooling MUST support running and comparing two
  configurations of the local model backend (thinking mode on vs. off)
  against the same benchmark, reporting accuracy and latency
  (average, p50, p95) for each.
- **FR-025**: The evaluation report MUST reflect actual measured results,
  including any regressions, rather than being adjusted to show a
  favorable outcome.

**Security preservation**

- **FR-026**: All existing public-endpoint protections (rate limiting, kill
  switch, monetary budget enforcement, concurrency limits, request/question
  size limits, context-size limits, output-token limits, prompt-injection
  defenses, admin authorization, and protection against client override of
  provider/model selection) MUST remain intact and unweakened by this
  feature.
- **FR-027**: The application, not the model's output or retrieved content,
  MUST decide how an answerability signal maps to the public-facing
  outcome; malformed or adversarial provider responses MUST fail to a safe,
  pre-existing outcome (`unavailable`, per FR-008) rather than an
  uncontrolled one, and never to `grounded`.

### Key Entities

- **Answerability Result**: The outcome of a single question-answering
  request — whether the supplied context actually supports an answer, and
  the answer text itself. Produced together, per question, by whichever
  model backend handled the request.
- **Application Outcome**: The public-facing classification of a chatbot
  response — grounded, insufficient information, or out-of-scope — derived
  by the application from the Answerability Result (and the pre-existing
  scope classification), never taken directly from raw model text.
- **Performance Telemetry**: Optional, per-request timing and token
  information (e.g., total time, model load time, prompt-processing time,
  generation time, token counts) captured when a model backend provides
  it, used for evaluation and reporting only.
- **Evaluation Report**: The output of running the frozen benchmark —
  per-question results (expected/actual outcome, pass/fail, latency, token
  usage where available) plus aggregate accuracy and latency summaries,
  including the thinking-mode A/B comparison.
- **Thinking-Mode Configuration**: The server-controlled setting
  determining whether the local model backend's extended reasoning mode is
  used during answer generation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

SC-001 through SC-003 are acceptance gates for the Ollama backend running
whatever model is currently configured as the default (`qwen3:4b` at this
spec's original authoring; `qwen3:8b` as of 2026-08-19 — research.md §17,
`eval/README.md`'s "Model selection: qwen3:8b adopted as default"), since
that is the backend on which the baseline numbers are measured and where
this feature's evaluation focus lies. The Anthropic backend must implement
the same behavioral contract (FR-009/FR-010) but is not gated by these
specific numeric targets.

- **SC-001**: On the frozen 30-question benchmark run against the Ollama
  backend, grounded accuracy is **at least 19/20 (≥95%)** and out-of-scope
  accuracy remains at 100% (3/3). **Amended 2026-08-19** from the original
  100% (20/20) grounded-accuracy target — see "SC-001 acceptance-criterion
  amendment" below for the full decision record.
- **SC-002**: On the frozen 30-question benchmark run against the Ollama
  backend, the insufficient-information rejection rate rises from the
  current 0% (0/7) to at least 85% — concretely, at least 6 of the 7
  `insufficient_information`-expected questions in this small, frozen
  benchmark. This is an MVP acceptance gate sized to the current fixture
  set, not a statistically powered production quality guarantee — 7 items
  is too small a sample for a tight confidence interval; it exists to
  catch a regression back toward the current 0/7 failure mode, not to
  certify a precise population rejection rate.
- **SC-003**: On the frozen 30-question benchmark run against the Ollama
  backend, the false-grounded rate falls from the current 100% (7/7) to
  15% or lower.
- **SC-004**: A documented side-by-side comparison exists showing accuracy
  and latency (average, p50, p95) for the local model backend with its
  extended reasoning mode on versus off, on the same benchmark, and the
  chosen default setting is explicitly justified by that comparison.
- **SC-005**: Every previously-passing automated test that does not depend
  on the changed answer-outcome contract continues to pass; every test
  touching that contract is deliberately and visibly updated, not silently
  broken.
- **SC-006**: No automated test requires a real local-model server, a real
  hosted-model API call, or GPU access to run.
- **SC-007**: A person reviewing the evaluation report for a single
  question can determine, without reading source code, why it passed or
  failed and how long it took.

### SC-001 acceptance-criterion amendment (2026-08-19)

- **Original target**: grounded accuracy 100% (20/20) on the frozen
  30-question benchmark.
- **Measured result**: the deterministic `qwen3:8b` evaluation
  (`OLLAMA_THINK=false`, `OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42` — the
  current default configuration) achieves **19/20 (95%)** grounded
  accuracy — see `research.md` §17 and `eval/README.md`'s "Model
  selection: qwen3:8b adopted as default" section.
- **Single remaining case**: question #6, "Czy na treningach ćwiczy się
  w butach?" ("Do you train in shoes?"). The retrieved context explicitly
  contains "Ćwiczenia odbywają się na boso" ("Training is done
  barefoot") — a semantic-inference/negation edge case, not a retrieval
  or safety failure.
- **Decision**: this case is **intentionally accepted for the MVP**, and
  SC-001 is amended from an absolute 20/20 requirement to **grounded
  accuracy ≥19/20 (≥95%)**, effective immediately. This is a deliberate
  acceptance-criteria change, made explicitly — **not** a claim that the
  original 20/20 target was achieved.
- **Why no further tuning was attempted**: a prior targeted prompt
  clarification aimed narrowly at this same class of case (rule 8, added
  2026-08-19, since reverted — research.md §16) caused a severe,
  measured regression in grounded accuracy (35%, 7/20 — down from an
  85%/17/20 deterministic baseline) when tried against the `qwen3:4b`
  backend, despite being carefully scoped to the diagnosed failure
  pattern. That result is treated as evidence that further global prompt
  calibration aimed at isolated semantic-inference cases carries a real,
  demonstrated risk of broad regression, and is not justified to close
  one remaining edge case when every safety metric (false-grounded,
  insufficient-information rejection, out-of-scope) is already at its
  target.
- **Safety criteria unchanged and preserved**: SC-002 (insufficient-
  information rejection ≥6/7) and SC-003 (false-grounded ≤15%/1-in-7) are
  **not** weakened by this amendment — both remain exactly as originally
  specified, and both are independently met (7/7 and 0/7 respectively) on
  the same `qwen3:8b` run.
- **Status**: question #6 is retained in `eval/questions.jsonl` with its
  original `grounded` expected outcome, unchanged — it is not removed
  from the benchmark, and it is documented as a known, accepted MVP
  limitation (see `eval/README.md`, `research.md` §17, `README.md`), not
  silently dropped.

## Assumptions

- The numeric targets in SC-002 and SC-003 operationalize the feature
  description's "materially improve" and "reduce substantially" language;
  they are floors, not ceilings — exceeding them (e.g., 100% rejection, 0%
  false-grounded) is success, not failure. Confirmed via clarification
  (see Clarifications).
- "Same benchmark, two configurations" (Story 3 / FR-024) assumes the
  benchmark and its evaluation harness can be re-run twice against a
  differently-configured local backend without any other variable (model
  version, knowledge base, retrieval settings) changing between runs.
- The exact technical mechanism for obtaining a structured, machine-
  readable answerability signal from each model backend is a technical
  design decision left to the implementation plan; this specification only
  requires that the signal exist, be explicit, and not depend on scanning
  natural-language answer text.
- Retrieval similarity thresholds and Top-K are assumed to remain exactly
  as currently configured; this feature does not tune them, even if doing
  so might further improve benchmark scores.
- "Server-controlled" (FR-012/013) assumes the existing configuration
  mechanism used for other non-client-overridable settings (e.g., model
  selection) is reused for the thinking-mode setting.
- Out-of-scope classification is treated as an existing, separate
  mechanism that this feature does not modify; it is only referenced here
  where it interacts with the new answerability outcome.
