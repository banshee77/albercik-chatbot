# Phase 0 Research: RAG Answerability & Ollama Performance

No `[NEEDS CLARIFICATION]` markers remain in the Technical Context — this
feature reuses the existing stack end-to-end (Design Constraint reminder:
Constitution Principle XIV — no new technology). Each section below is a
concrete decision the implementation plan depends on.

## 1. Shape of the structured answerability contract

- **Decision**: Extend the existing `LLMResult` dataclass
  (`providers/llm/protocol.py`) rather than introduce a second, parallel
  result type. Two changes to the dataclass:
  - Add a required `supported: bool` field.
  - Rename `text: str` → `answer: str` (same field, clarified name — see
    rationale).
  - Add an optional `provider_metrics: dict[str, int] | None = None` field
    (§8).
- **Rationale**: `complete()` has exactly one call site's worth of meaning
  in this codebase — "produce the grounded answer for this question" — so
  there is no second use case that would justify a parallel
  `AnswerabilityResult` wrapper type alongside `LLMResult`. Folding
  `supported` directly into the existing return type is the smallest change
  that satisfies FR-004 ("one reasoning step... not a second call") and
  keeps the `LLMProvider` Protocol itself completely unchanged (still one
  method, same signature) — only what it returns gains a field. The
  `text`→`answer` rename is a small, deliberate clarity fix: before this
  feature, "the text the model returned" and "the answer" were the same
  thing by definition; after this feature they are only the same thing
  *when `supported=True`*, and calling the field `answer` matches the
  ubiquitous language already established in spec.md's Key Entities
  ("Answerability Result... answer text") and Requirements (FR-002/003).
  Every call site is touched by this feature's provider changes anyway
  (both providers' parsing logic, `ask_question.py`'s branch,
  `FakeLLMProvider`, and the provider/contract tests), so the rename adds
  no extra migration surface beyond what already has to change.
- **Alternatives considered**: A new `AnswerabilityResult` type wrapping or
  replacing `LLMResult` — rejected: two result types for one call site is
  needless indirection (Principle XIII), and would force
  `application/ask_question.py` to juggle two shapes for no behavioral
  gain. Keeping the field named `text` — rejected per the rationale above;
  a stale name here is exactly the kind of thing a future reader would
  trip on ("why is `result.text` sometimes not the answer?").

## 2. Where the shared JSON schema lives

- **Decision**: Define one module-level constant,
  `ANSWERABILITY_JSON_SCHEMA` (a plain JSON Schema `dict`), in
  `providers/llm/protocol.py` — the same module that already defines the
  shared `LLMProvider` Protocol and `LLMResult`. Both providers import and
  adapt this single schema to their own wire format (§3, §4); neither
  provider redefines the field names or types independently.
- **Rationale**: This is the concrete mechanism behind FR-009 ("one
  shared, provider-independent contract") — a single source of truth for
  what "supported" and "answer" mean, structurally, not just by
  convention. Putting it in `protocol.py` (not a new module) matches
  Principle XIII: this is one small constant, not a framework.
- **Alternatives considered**: Defining the schema twice, once per
  provider file, each hand-adapted to that provider's wire shape —
  rejected: two independently-maintained copies of "the same contract"
  are exactly the kind of drift FR-009/FR-010 are trying to prevent.

## 3. Ollama structured output mechanism

- **Decision**: Pass `ANSWERABILITY_JSON_SCHEMA` as the `format` field on
  the existing `POST {OLLAMA_BASE_URL}/api/chat` request (already used,
  research.md §2 of feature 002). Ollama constrains `message.content` to a
  JSON string matching the given schema; the provider `json.loads()`s that
  string and reads `supported`/`answer` from it, instead of treating
  `message.content` as free-form answer text.
- **Rationale**: `format` (accepting a JSON Schema, not just the literal
  string `"json"`) is Ollama's own supported structured-output mechanism
  for exactly this purpose, requires no new dependency (still the same
  `httpx` POST this codebase already makes), and is testable with the
  existing `httpx.MockTransport` pattern (`tests/unit/test_ollama_provider.py`)
  by returning a canned JSON-string body — no real Ollama process needed,
  satisfying spec Testing item 9 and the "no real Ollama... in automated
  tests" constraint.
- **Alternatives considered**: Prompt-only JSON instructions with regex/
  substring parsing of the answer for a sentinel phrase — explicitly
  forbidden by FR-007 and spec section 5 ("do not rely on fragile string
  matching"). A two-call design (one call to classify, one to answer) —
  forbidden by FR-004.

## 4. Anthropic structured output mechanism

- **Decision**: Use the `anthropic` SDK's native, stable (non-beta)
  structured-outputs parameter on the existing `messages.create(...)`
  call: `output_config={"format": {"type": "json_schema", "schema":
  ANSWERABILITY_JSON_SCHEMA}}` — the same shared schema Ollama uses (§2),
  not a separate Anthropic-shaped schema. The API constrains the
  response's text content to a JSON string matching the schema; the
  provider `json.loads()`s it and reads `supported`/`answer` — the same
  parsing shape as `OllamaLLMProvider` (§3), not a tool-use/`input` dict.
  No forced tool-use, no synthetic tool definition. All of this — the
  `output_config` construction and the response parsing — stays entirely
  inside `AnthropicLLMProvider`; nothing about it leaks into
  `providers/llm/protocol.py` beyond the shared schema constant itself.
- **Rationale**: Confirmed present and stable in the installed SDK
  (`anthropic==0.122.0`): `anthropic/types/output_config_param.py`
  (`OutputConfigParam`, with a `format: JSONOutputFormatParam` field) and
  `anthropic/types/json_output_format_param.py`
  (`{"type": "json_schema", "schema": ...}`) both live under the
  package's non-beta `types/` tree and are accepted as a top-level
  `messages.create()` parameter (`anthropic/resources/messages/messages.py`)
  — this is "the simplest reliable structured-output approach compatible
  with the current provider implementation" the spec asks for (section 5),
  and it is Anthropic's own purpose-built mechanism for this exact
  problem, not a repurposed tool-calling workaround. Reusing the identical
  schema both providers already share (§2) — rather than one schema
  wrapped as a `format` and a second, differently-shaped one wrapped as a
  tool's `input_schema` — is a stronger, more literal reading of FR-009's
  "one shared, provider-independent contract" than forced tool-use would
  have been. Both providers now parse a JSON *string* the same way,
  making the two implementations more structurally parallel, not less.
  Testable via the exact same `_AnthropicClientLike`/fake-transport
  pattern `test_anthropic_provider_retries.py` already established
  (inject a fake `messages.create` returning a canned text content block
  whose `.text` is a JSON string — satisfies spec Testing item 11, no
  real Anthropic call, no SDK upgrade).
- **Alternatives considered**: Forced single-tool-use (`tool_choice`
  pinned to one synthetic `provide_answer` tool) — rejected: it works, but
  it is a repurposing of function-calling for a problem the SDK now has a
  dedicated, purpose-built parameter for; using it here would also give
  Anthropic a different response shape (a `tool_use` block's pre-parsed
  `input` dict) than Ollama's raw JSON string, weakening the "one shared
  contract" story for no benefit. Asking the model to emit raw JSON in
  plain text and parsing it — rejected: reintroduces the fragile-parsing
  risk FR-007 forbids, which `output_config`/`json_schema` exists
  specifically to avoid.

## 5. Malformed structured output → fail-safe mapping

- **Decision**: A structured-output parse failure (Ollama:
  `json.loads()` failure, missing `supported`/`answer` key, wrong type;
  Anthropic: response content is not parseable as JSON matching
  `ANSWERABILITY_JSON_SCHEMA`, or a missing/mistyped field within it) is
  caught **inside the provider**, logged as a warning (mirroring the
  existing malformed-envelope warning in `ollama_provider.py`), and raises
  `LLMProviderError` — it does **not** synthesize an
  `LLMResult(supported=False, ...)`. A structured response that *parses
  successfully* and yields `supported=false` is an ordinary
  `LLMResult(supported=False, answer=..., ...)` and is **not** an error —
  it flows through `ask_question.py`'s existing `if result.supported`
  check (FR-001) to `insufficient_information` exactly like any other
  `False` decision, needing no new branching there either.
- **Rationale**: Per Clarifications (2026-08-18, **superseded during
  `/speckit-plan`** — see spec.md), a parse failure is a provider/protocol
  failure, not evidence about the knowledge base, so it must not be
  reported as `insufficient_information` — doing so would hide a real
  provider/protocol failure behind a misleading, confidence-bearing
  business outcome (FR-008/FR-027). `LLMProviderError` already means
  "provider call failed" and `ask_question.py` already maps it to
  `unavailable` — reusing that existing path for this new failure class
  requires **zero new exception types and zero new branches** in
  `ask_question.py`: its existing `except LLMProviderError` handling
  already produces `unavailable` for free. This keeps the two outcomes
  cleanly separated by construction: `insufficient_information` means "the
  model looked at the context and explicitly judged it insufficient";
  `unavailable` means "the provider/protocol did not produce a usable
  answerability decision at all" (envelope failure or schema-invalid
  content — the same bucket). This is a fully provider-local decision — no
  Anthropic/Ollama branching leaks into `ask_question.py` (FR-010).
- **Envelope-level failures are unchanged, and this feature folds a second
  failure class into the same path**: a non-2xx status, connection/timeout
  exhausted after bounded retries, or a response body that isn't valid
  JSON *at all* already raised `LLMProviderError` → `unavailable` before
  this feature. This feature adds schema-invalid/unparseable *message
  content* (an otherwise-successful provider response whose payload
  doesn't match `ANSWERABILITY_JSON_SCHEMA`) to that same
  `LLMProviderError` → `unavailable` path, rather than giving it different
  treatment — there is exactly one failure outcome for "the provider did
  not give us a usable structured answerability decision," regardless of
  which layer detected the problem.
- **Alternatives considered**: Returning a synthesized
  `LLMResult(supported=False, ...)` for a parse failure instead of raising
  — rejected (this was the design before the 2026-08-18 correction):
  it conflates a provider/protocol failure with a genuine "no evidence"
  judgment, silently hides real failures behind a confident business
  outcome, and violates FR-008/FR-027's requirement that parse failures
  fail safe to `unavailable`, never `grounded` and never
  `insufficient_information`. A new, distinct exception type with its own
  `ask_question.py` handling — rejected: reusing `LLMProviderError`
  already yields the correct `unavailable` mapping via existing exception
  handling, so a parallel type would be redundant indirection for the same
  outcome (Principle XIII).

## 6. `OLLAMA_THINK` configuration and wire parameter

- **Decision**: New `Settings.OLLAMA_THINK: bool = False` field
  (`config.py`), read once at `main.py::_build_configured_llm_provider`
  and passed into `OllamaLLMProvider.__init__(..., think=...)`.
  `OllamaLLMProvider.complete()` sends the top-level `"think": self._think`
  field on the same `/api/chat` request body that already carries
  `model`/`messages`/`options.num_predict`/`format`.
- **Rationale**: Ollama's `/api/chat` (and `/api/generate`) accept a
  top-level `think` boolean for hybrid-reasoning models (Qwen3 among them)
  that controls whether the model performs its internal reasoning step
  before answering — this is the same mechanism the feature description's
  suggested `OLLAMA_THINK` env var names. Threading it through the
  constructor (like `base_url`/`model`/`timeout_seconds` already are)
  keeps it server-only by construction: nothing about `ChatRequest` (which
  already has `extra="forbid"`, Principle X) or the request path can reach
  it — it is fixed at provider-construction time, before any request
  exists (FR-013).
- **Alternatives considered**: The `/no_think` / `/think` prompt-suffix
  convention some Qwen3 releases also support — rejected: that would mean
  controlling a server-side setting by mutating prompt *content*, which
  is both fragile (a future model/prompt change could silently break it)
  and harder to keep visibly separate from the untrusted-vs-trusted-content
  boundary `domain/prompting.py` is built around; the native API parameter
  is a real configuration knob, not text the model has to parse.

## 7. Never surfacing "thinking" content

- **Decision**: `OllamaLLMProvider` reads only `message.content` from the
  response body — never `message.thinking` (the field Ollama populates
  alongside `content` when `think=true`). This holds regardless of the
  `OLLAMA_THINK` setting's value, including during the think=true side of
  the A/B comparison (§11).
- **Rationale**: Directly satisfies FR-016 — reasoning content must never
  reach the end user or any persisted usage/telemetry record. Since the
  provider simply never reads that key, there is no code path that could
  accidentally leak it later (nothing to redact, because nothing is
  captured).

## 8. Where performance telemetry is stored

- **Decision**: One new nullable column on the existing `usage_records`
  table: `provider_metrics` (PostgreSQL `JSONB`, nullable). Populated
  verbatim from `LLMResult.provider_metrics` when a provider returns one
  (Ollama: `{"total_duration_ns": ..., "load_duration_ns": ...,
  "prompt_eval_duration_ns": ..., "eval_duration_ns": ...}`, copied
  directly from Ollama's own response fields (`total_duration`,
  `load_duration`, `prompt_eval_duration`, `eval_duration` — already
  nanoseconds) with **no unit conversion**, only a rename to make the unit
  explicit in the key itself; Anthropic: always `None`/absent, since the
  Anthropic API does not expose this level of timing detail). Existing
  `input_tokens`/`output_tokens`/`latency_ms` columns are unchanged and
  continue to be populated by both providers exactly as today.
  `provider_metrics` is opaque below the provider boundary: core
  RAG/application decision logic (`application/ask_question.py`,
  `domain/`) may use `supported`, `answer`, and the normalized
  `input_tokens`/`output_tokens` counts, but MUST NOT read or branch on
  any key inside `provider_metrics` — that dict exists solely for usage
  accounting and evaluation tooling (`scripts/run_eval.py`), never for a
  decision the chatbot itself makes.
- **Rationale**: FR-017 requires capturing this "without requiring core
  question-answering logic to depend on backend-specific data" — a single
  opaque JSONB column, written by `_record_usage()` from whatever
  `provider_metrics` dict it was handed (never inspecting or branching on
  its keys), keeps `application/ask_question.py` and the persistence layer
  fully provider-neutral: they pass the bag through, they don't know its
  shape. This reuses the *existing* `usage_records` table/migration
  mechanism rather than a new store (satisfies "do not add a new
  monitoring platform"), and the four Ollama-native fields listed in the
  feature description are exactly what lets tokens/sec be computed
  precisely (`eval_count / (eval_duration_ns / 1e9)`, generation-only)
  rather than approximated from wall-clock `latency_ms` (which, for
  Ollama, also includes model-load and prompt-eval time on a cold call).
  Keeping native nanosecond units (rather than converting to milliseconds)
  avoids an unnecessary integer-rounding step and keeps the stored value
  identical to what Ollama itself returned, at the cost of the eval script
  needing to divide by `1e9` instead of `1000` — an explicit, self-
  documenting trade favored by the `*_duration_ns` naming convention.
  Token counts themselves are **not** duplicated into this JSON blob —
  `input_tokens`/`output_tokens` already exist as first-class columns
  (unchanged since feature 002), so only the four *duration* values are
  new.
- **Alternatives considered**: Four separate typed integer columns instead
  of one JSONB column — rejected: typed columns would force
  `_record_usage()` to know Ollama-specific field names to map dict→
  columns (a form of coupling this feature is explicitly trying to avoid,
  spec section 7), whereas a single opaque JSONB column stays genuinely
  provider-neutral at the persistence layer, at the cost of the
  eval-report code needing to know the (documented) key names when it
  later reads the column back — an acceptable trade since that code is
  dev tooling, not core application logic. A brand-new `provider_telemetry`
  table — rejected as unjustified extra schema surface for optional,
  non-critical data that fits naturally as an extension of the row that
  already represents "this one provider call."

## 9. Correlating the eval script to per-question usage data

- **Decision**: Add `request_id: uuid.UUID` to `ChatResponse` (the UUID
  `api/routers/chat.py` already generates per request for
  `ask_question(..., request_id=...)`, simply also returned in the
  response body). `scripts/run_eval.py` opens a direct SQLAlchemy session
  against `DATABASE_URL` (reusing
  `persistence.database.get_session_factory()`, the same helper the app
  itself uses) and, after each `/chat` call, looks up the
  `usage_records` row where `request_id` matches and
  `provider_kind='llm'` to read `input_tokens`, `output_tokens`, and
  `provider_metrics`.
- **Rationale**: `usage_records.request_id` already exists precisely to
  correlate "one row per provider call" back to the request that produced
  it — the only missing piece was the *client* (here, the eval script)
  never learning which `request_id` a given response corresponds to.
  Exposing a random, non-sensitive correlation UUID in the public response
  is a minimal, additive contract change (documented in `contracts/`) and
  is the same pattern countless HTTP APIs already use for trace
  correlation — it reveals no user data, no cost/config internals, and
  cannot be used to influence server behavior. This keeps the eval script
  a plain, unauthenticated-adjacent HTTP+DB client tool, with no new admin
  HTTP endpoint required.
- **Alternatives considered**: A new admin-only `GET
  /api/v1/admin/usage/{request_id}` endpoint — rejected as unnecessary
  API surface: `run_eval.py` is explicitly "a dev/eval tool only... not
  part of the application" (its own existing docstring) already running
  in the same environment with direct `DATABASE_URL` access (it already
  imports `albercik_chatbot.config.get_settings`), so querying the
  database directly is simpler and adds zero production attack surface,
  versus a new authenticated endpoint that would need its own tests,
  rate-limit/authz consideration, and OpenAPI contract entry for a
  capability only ever used by one dev script. Returning token counts
  directly in `ChatResponse` instead of via a DB lookup — rejected:
  exposing per-request token/cost-shape counts to every public,
  unauthenticated caller is unnecessary information disclosure for a
  customer-facing endpoint that a correlation ID avoids entirely.

## 10. Computing tokens/sec and load duration for the eval report

- **Decision**: Three additional per-question figures, each computed only
  when its required inputs are present and non-zero (never fabricated —
  FR-019):
  - **Generation tokens/sec**: when `provider_metrics.eval_duration_ns` is
    present (Ollama), `output_tokens / (eval_duration_ns / 1e9)` —
    generation-only, excluding model load and prompt evaluation. Otherwise
    (Anthropic, or any row missing that field), fall back to
    `output_tokens / (latency_ms / 1000)` using the existing wall-clock
    `latency_ms`, labeled in the report as an approximation (it includes
    network/queueing time the Ollama-native figure excludes).
  - **Prompt-eval tokens/sec**: when `provider_metrics.prompt_eval_duration_ns`
    is present (Ollama), `input_tokens / (prompt_eval_duration_ns / 1e9)`
    — how fast the model processed the retrieved-context prompt, before
    generation began. No fallback is defined for this figure (Anthropic
    does not expose an equivalent duration) — it is simply omitted/shown
    as unavailable for non-Ollama rows.
  - **Load duration**: `provider_metrics.load_duration_ns` reported
    directly (converted to a human-readable unit, e.g. milliseconds, for
    display only — the stored value stays nanoseconds), when present. This
    is the time Ollama spent loading the model into memory before either
    prompt evaluation or generation; on a warm model it is typically near
    zero, and its presence in the report lets an operator distinguish a
    slow cold-load call from genuinely slow generation.
- **Rationale**: Satisfies FR-022 ("generation tokens-per-second... where
  available") plus this feature's explicit ask for prompt-eval tokens/sec
  and load duration, using the most precise figures available per row
  without inventing data no provider returned (FR-019) — each of these
  three is a genuine, non-fabricated computation (or direct passthrough)
  from `provider_metrics`/existing fields, never shown when the values it
  needs are missing or zero. Reporting all three (rather than only
  generation tokens/sec) gives an operator enough to distinguish *why* a
  call was slow — model load, prompt processing, or generation — which a
  single blended tokens/sec figure cannot.

## 11. Mechanics of the think=true vs. think=false A/B comparison

- **Decision**: `scripts/run_eval.py` gains a `--save-json <path>` option
  that serializes the same per-question results + summary already printed
  (plus the new latency percentiles/token metrics) to a file. A new,
  small `scripts/compare_eval_runs.py <run_a.json> <run_b.json>` loads two
  such files and prints a side-by-side table (accuracy per category,
  average/p50/p95 latency, average output tokens, tokens/sec) — the
  operator still runs the eval script twice, switching `OLLAMA_THINK` and
  restarting the `app` container between runs, exactly as
  `eval/README.md` already documents for comparing the Ollama vs.
  Anthropic backends (feature 002).
- **Rationale**: `run_eval.py` cannot flip `OLLAMA_THINK` and restart the
  `app` container itself — that container is a separate Docker Compose-
  managed process, and reaching into its lifecycle from a Python eval
  script would be fragile, out of proportion for a dev tool, and outside
  this feature's "no new monitoring platform / no automated provider
  routing" boundaries. Reusing the exact "run once per configuration,
  compare the two labeled reports" pattern already established for the
  cross-provider comparison keeps this consistent with existing operator
  workflow, and `compare_eval_runs.py` is a small, single-purpose script,
  not new infrastructure.
- **Alternatives considered**: A single script that spins up two
  containers/configs and diffs them automatically — rejected as
  disproportionate automation for a one-time-per-tuning-decision
  measurement task (Decision Priority: simplicity over this kind of
  performance-tooling elegance).
- **Measured result (2026-08-18, Polish phase)**: Both configurations run
  against the real `qwen3:4b` model on GPU-accelerated Ollama (RTX 3070),
  same knowledge base, same `eval/questions.jsonl`, no retrieval/prompt
  changes between runs. `OLLAMA_THINK=false` is the chosen default — see
  `eval/README.md`'s "OLLAMA_THINK A/B comparison" section for the full
  table and reports (`eval/results/qwen3-4b-think-false.json`,
  `eval/results/qwen3-4b-think-true.json`). Summary: `think=true` was
  ~3.6x slower on average (8948ms vs 2467ms; p95 13551ms vs 6017ms) and
  produced 6/30 new `unavailable` outcomes not present under
  `think=false` — `qwen3:4b` exhausted `LLM_MAX_ANSWER_TOKENS` on
  reasoning before emitting the structured JSON answer, leaving
  `message.content` empty; this correctly failed safe to `unavailable`
  via the §5 mechanism (proving that fail-safe path works under a real
  adverse interaction) rather than a silent misclassification. This is
  strictly worse than `think=false` on both the performance and
  reliability axes this feature cares about, so no meaningful-quality-
  advantage exception applied. This measurement also surfaced (but does
  not fix — out of scope for the A/B measurement itself) that neither
  configuration meets the SC-001 grounded-accuracy target (20/20;
  measured 13/20 and 14/20) — see `eval/README.md`'s "Known open issue"
  section.

## 12. `ProviderName` enum / usage accounting for Ollama — unchanged

- **Decision**: No change to `ProviderName`, `ProviderKind`, or the budget
  query in `infra/budget.py`. `provider_name='ollama'` continues to never
  count toward the Anthropic monetary budget (Design Constraint 4, feature
  002) — this feature only adds the optional `provider_metrics` column
  (§8) alongside the existing, unchanged accounting fields.
- **Rationale**: Spec section 8 explicitly requires preserving current
  `UsageRecord` behavior and provider attribution; there is no new
  requirement here that touches budget semantics.

## 13. System prompt changes

- **Decision**: `domain/prompting.py::SYSTEM_PROMPT` gains two additions,
  applied identically for both providers (it is assembled once, before any
  provider is chosen):
  1. A rule stating that the model must decide `supported`/`answer`
     together, and that `supported` must be `false` whenever the KONTEKST
     block does not actually contain the information needed to answer —
     replacing today's softer "say so in the text" instruction (rule 5)
     with the structural expectation the new output schema exists to
     enforce.
  2. A new rule: absence of information about a topic in KONTEKST is not
     evidence of a negative answer — the model must not conclude "Albertos
     does not do/offer/allow X" merely because X is unmentioned; only an
     explicit statement in KONTEKST may ground a negative answer. This is
     the direct implementation of FR-005/FR-006, using the same three
     illustrative patterns from spec section 4 (unoffered service,
     unmentioned rental policy, unmentioned achievement) condensed into
     the instruction.
- **Rationale**: `SYSTEM_PROMPT` is already the *only* source of
  instructions the model receives (`domain/prompting.py`'s own docstring)
  and is shared, unmodified, by both providers via
  `assemble_prompt()` — adding these rules here, rather than per-provider,
  is what makes FR-006 ("expressed in trusted system instructions, not
  retrieved content") and FR-009 (shared contract) true by construction.
- **Alternatives considered**: Encoding the no-negative-inference rule as
  a retrieval/domain-logic check (e.g., scanning the answer for negation
  words) — explicitly forbidden by spec section 5 (fragile string
  matching) and section 4 ("must be expressed in trusted system
  instructions").

## 14. Polish-phase targeted correction: rule 7 (2026-08-18)

- **Decision**: A live evaluation run (`OLLAMA_THINK=false`, real
  `qwen3:4b`) diagnosed 7 grounded-expected questions (eval/questions.jsonl
  ids 6, 11, 13, 14, 24, 25, 26) incorrectly returning
  `insufficient_information`. Each was diagnosed individually by
  replicating the exact retrieval → relevance-filter → context-limit →
  prompt-assembly → LLM-call pipeline outside the application and
  inspecting retrieved chunks/similarity/final context/raw structured
  result. All 7 had their supporting fact(s) retrieved and present in the
  final context — retrieval (category A) and structured-output/provider
  parsing (category C) were ruled out for every case. `SYSTEM_PROMPT`
  gains one more addition, rule 7: `supported=true` is explicitly
  confirmed appropriate when KONTEKST contains the needed facts even if
  the answer requires combining two or more facts, the question is a
  paraphrase, KONTEKST is worded differently than the question, the
  correct answer is affirmative or negative, or the facts span more than
  one retrieved chunk — scoped explicitly to "facts genuinely present,"
  never overriding rule 6 for the "facts absent" case.
- **Rationale**: Rule 6's "jednoznacznie" (unambiguous) framing was being
  read by the model as requiring near-verbatim phrasing match, not just
  presence of the fact — e.g. context stating "ćwiczenia odbywają się na
  boso" (barefoot) was judged insufficiently "unambiguous" to answer a
  question about shoes, and a cost figure requiring combining "żółty pas
  = 8 kyu" with "9–6 kyu costs 100 zł" (both explicit, same chunk) was
  similarly declined. Rule 7 directly counters this over-literalism
  without touching rule 6's actual safety property (never inferring a
  negative from silence) — verified unchanged by regression tests in
  `tests/unit/test_prompting.py` asserting both rules' content coexist,
  and that rule 7 cannot be planted/overridden by retrieved-document
  content (same injection-resistance test pattern as rule 6).
- **Measured result**: grounded accuracy was unchanged in aggregate
  (65%, 13/20) — the *composition* of failures changed (3 originally-
  failing questions started passing; 3 different, previously-passing
  questions newly failed; one new false-grounded case appeared, still
  within the ≤1/7 threshold). **SC-001 (20/20) remains unmet.** The flat
  aggregate result, combined with a same-prompt/same-context diagnostic
  probe of question #13 independently returning opposite `supported`
  values on two separate calls, points to `qwen3:4b`'s decoding
  non-determinism (temperature-driven sampling) as large enough, relative
  to this benchmark's ~20-question `grounded` sample size, to mask or
  fabricate an apparent single-run accuracy delta. This is analogous to
  spec.md's existing SC-002 small-sample caveat, but applies more directly
  here since `grounded` correctness is a free-text judgment call, not a
  fixed threshold comparison.
- **Explicitly not done**: A second or third eval re-run chasing a
  passing sample, and any further prompt edit targeting the specific
  post-fix failures (#3, #5, #6, #11, #15, #22, #25, #26) — both would be
  tuning against single-run noise rather than a diagnosed cause, which
  this task was explicitly scoped to avoid ("do not tune blindly, stop").
- **Recommended future work** (out of scope for this correction pass):
  repeat the frozen benchmark multiple times per prompt variant and
  compare distributions rather than single-run pass counts before
  attributing further change to a prompt edit; consider whether a
  lower/fixed `temperature` specifically for the eval harness (leaving
  production behavior untouched) would stabilize measurement.

## 15. Deterministic Ollama generation: `OLLAMA_TEMPERATURE`/`OLLAMA_SEED` (2026-08-19)

- **Decision**: Added two new `Settings` fields, `OLLAMA_TEMPERATURE:
  float = 0.0` and `OLLAMA_SEED: int = 42`, forwarded by
  `OllamaLLMProvider` inside the `/api/chat` request's `options` object
  (alongside the existing `num_predict`). Same ownership pattern as
  `OLLAMA_THINK` (§6): constructor-only, never a `LLMProvider.complete()`
  parameter, never derived from request content — proven by new tests in
  `tests/unit/test_ollama_provider.py` (forwarding, non-default values,
  fixed-at-construction-not-per-call) and new parametrized cases in
  `tests/contract/test_chat_no_client_override.py` covering every
  plausible client-supplied override spelling (`temperature`, `seed`,
  `OLLAMA_TEMPERATURE`, `OLLAMA_SEED`, lowercase variants). Two new tests
  in `tests/unit/test_anthropic_provider_retries.py` confirm
  `AnthropicLLMProvider` structurally cannot accept either parameter and
  its request body never carries either key regardless of the settings'
  values.
- **Rationale**: §14 found that a same-prompt/same-context call to
  `qwen3:4b` could return a different `supported` decision across
  separate invocations, at Ollama's default nonzero sampling temperature —
  making single-run eval deltas an unreliable signal for judging whether a
  prompt change actually helped. Pinning `temperature=0` (greedy decoding)
  and a fixed `seed` removes this source of variance so that future
  answerability-prompt calibration work can trust a single re-run's
  outcome delta as attributable to the prompt change, not to sampling.
- **Experiment and measured result**: the frozen 30-question benchmark was
  run 3 times back to back with this configuration (`OLLAMA_THINK=false`,
  `OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`, unchanged KB/model between
  runs) — see `eval/results/repeatability-run-{1,2,3}.json` and
  `eval/README.md`'s "Reproducibility experiment" section for the full
  table. **Result: 30/30 (100%) per-question outcome agreement across all
  3 runs — zero unstable question IDs.** Question #13 specifically
  returned `grounded` in all 3 runs (previously observed flipping).
  Grounded accuracy measured deterministically at 85% (17/20), with
  identical failures every run (#3, #6, #22 — all under-answering
  `insufficient_information` where `grounded` was expected; never a
  false-grounded/safety miss). Insufficient-information rejection 100%
  (7/7), false-grounded 0/7, out-of-scope 100% (3/3) — identical in all 3
  runs.
- **Explicitly not done**: no prompt, retrieval, embedding, Top-K,
  threshold, chunking, or scope-classifier code was touched, and
  `eval/questions.jsonl`'s expected outcomes were not modified, per this
  task's explicit scope — the deterministic 85% (17/20) baseline and the
  3 remaining failing questions are left for a future prompt-calibration
  session, now on solid methodological footing (further tuning's effect
  can be measured directly, without needing repeated runs to separate
  signal from sampling noise).
- **Not adopted**: no attempt was made to determine whether `temperature=0`
  changes answer *quality* independent of reproducibility (e.g. whether a
  small nonzero temperature would answer more of the 3 remaining questions
  correctly) — that would require its own A/B measurement and is out of
  this task's scope.

## 16. Final targeted calibration: rule 8 — measured regression, not adopted (2026-08-19)

- **Decision**: Diagnosed the 3 questions (#3, #6, #22) that deterministically
  failed every one of the §15 repeatability runs. All 3 had their
  supporting fact present verbatim in the final context (category A and C
  ruled out again). Rule 7 (§14) didn't cover the actual failure shapes:
  #6's raw model output explicitly derived "no shoes" from "barefoot" in
  its own reasoning text yet still set `supported=false`; #3's fact sat
  among 4 similarly-worded list entries; #22 needed a direct inference
  from an explicit general condition ("sports outfit suffices at first
  training") to the asker's stated situation. Added rule 8 to
  `SYSTEM_PROMPT`, explicitly distinguishing (A) fact genuinely absent
  (rule 6 governs, unchanged) from (B) fact present, needing only logical
  negation / correct-item selection / direct inference with no added
  content (supported=true) — with a contrasting example (online classes)
  reinforcing that (B) never licenses inferring from silence. Regression
  tests added in `tests/unit/test_prompting.py` (TDD, RED confirmed
  before implementation).
- **Measured result — a severe regression, not an improvement**: a single
  re-run of the frozen 30-question benchmark (same deterministic config,
  `eval/results/qwen3-4b-think-false-rule8.json`) measured grounded
  accuracy at **35% (7/20), down from the 85% (17/20) §15 deterministic
  baseline**. All 3 originally-targeted questions still failed, plus 10
  more previously-passing questions newly failed (13 total), all via the
  identical canned `insufficient_information` message. Insufficient-
  information rejection, false-grounded, and out-of-scope figures were
  unchanged (100%/0%/100%) — no safety property regressed, but the recall
  cost was severe and strictly worse on every count that changed.
- **Root-cause hypothesis (not further tested this pass, per the explicit
  "do not modify the prompt again in the same pass" instruction)**: rule
  8 is long, and its (A) branch repeats false/negation-heavy framing
  prominently; on this small local model, adding more instruction text
  emphasizing the false-case plausibly shifted its general decision
  threshold toward `false` broadly, rather than surgically correcting
  only the 3 targeted patterns.
- **Explicitly not done**: no second edit, no revert, and no second eval
  run were performed in this pass — the regression is reported and left
  exactly as measured for the next session/a human reviewer to act on.
- **Recommendation for the next session**: revert rule 8 and restore the
  rules-1–7 `SYSTEM_PROMPT` (the real, deterministic 85%/17/20 baseline —
  strictly better on every axis than rule 8's measured 35%/7/20). Any
  further attempt at the #3/#6/#22 gap should change one small,
  narrowly-scoped instruction at a time, re-measuring after each
  individual change — this session is evidence that prompt length/
  emphasis has a real, unpredictable, and potentially large effect on
  this model's overall answerability threshold, not just on the targeted
  failure patterns.
- **REJECTED, reverted 2026-08-19 (same day, next pass)**: rule 8 removed
  from `domain/prompting.py::SYSTEM_PROMPT`, restoring the exact rules-
  1–7 text; its 3 regression tests removed from
  `tests/unit/test_prompting.py`. **Rule 8 is not part of the active
  prompt** — this §16 stays as the historical record of what was tried
  and why it was rejected (the rule-8 prompt text itself lives in git
  history, not reproduced again here). A confirming re-run of the frozen
  30-question benchmark (same deterministic config, unchanged KB) after
  the revert measured **85% (17/20) grounded, 100% (7/7)
  insufficient-information rejection, 0/7 false-grounded, 100% (3/3)
  out-of-scope — identical to the §15 baseline, same failing questions
  (#3, #6, #22)** — see
  `eval/results/qwen3-4b-think-false-post-revert.json` and
  `eval/README.md`'s "Deterministic baseline restored" section. The
  revert is confirmed exact, not just intended.

## 17. Model selection: qwen3:8b adopted as the default Ollama model (2026-08-19)

- **Decision**: Changed `OLLAMA_MODEL`'s default from `qwen3:4b` to
  `qwen3:8b` in `config.py`, `.env.example`, and `docker-compose.yml`'s
  `ollama-init` service. This is a model swap only — no change to
  `SYSTEM_PROMPT`, retrieval, embeddings, chunking, relevance threshold,
  `RETRIEVAL_TOP_K`, `MAX_CONTEXT_CHARS`, the scope classifier, the
  structured answerability contract, `eval/questions.jsonl`,
  `OLLAMA_THINK`, `OLLAMA_TEMPERATURE`, `OLLAMA_SEED`, or
  `LLM_MAX_ANSWER_TOKENS`.
- **Rationale (measured, not assumed)**: with the prompt fixed at the
  §16-confirmed rules-1–7 deterministic baseline, a controlled evaluation
  (same deterministic config, same KB, same frozen 30-question benchmark,
  single run each, `qwen3:8b` provisioned via the existing `ollama-init`
  mechanism — no new provisioning code) measured:
  - Grounded accuracy: **19/20 (95%)**, up from `qwen3:4b`'s 17/20 (85%).
  - Insufficient-information rejection: 7/7 (100%) on both models —
    unchanged.
  - False-grounded: 0/7 on both models — unchanged, no safety regression.
  - Out-of-scope accuracy: 3/3 (100%) on both models — unchanged.
  - No `unavailable`/provider-failure outcomes, no OOM, on the RTX 3070
    reference host; `qwen3:8b` used ~6.0 GB of the 8 GB VRAM budget.
  - Latency: avg 2.57s / p50 2.03s / p95 4.18s (vs. `qwen3:4b`'s avg
    1.88s / p50 1.49s / p95 5.47s) — slower per call (~31% lower
    generation tokens/sec, 55.30 vs. 80.11) but still acceptable for this
    deployment's interactive use case.
  - Full reports: `eval/results/qwen3-4b-think-false-post-revert.json`
    (baseline) and `eval/results/qwen3-8b-think-false.json` (8B),
    compared via `scripts/compare_eval_runs.py`.
- **Per-question**: `qwen3:8b`'s only failure was **#6** ("Czy na
  treningach ćwiczy się w butach?") — the same question that failed on
  4B. #3 and #22 (both 4B failures) now pass on 8B. No question that
  passed on 4B regressed on 8B. No workaround targeting #3, #6, or #22
  specifically was introduced — the only change made was the model name.
- **Explicitly not done in this pass**: no investigation or fix of #6
  (deliberately out of scope — a narrow model-adoption/documentation
  pass only); no new `OLLAMA_THINK`/temperature/seed A/B on `qwen3:8b`
  (those settings were held fixed, not re-validated, on the new model);
  no new model-selection mechanism (`qwen3:4b` remains available via the
  existing `OLLAMA_MODEL` override, exactly as before).
- **SC-001 status**: **still NOT met against the original 20/20 target**
  — `qwen3:8b` measures 19/20. This is not reported or treated as
  satisfying the *original* SC-001. Feature 004 remains not safe to
  close on the *original* SC-001. **Superseded 2026-08-19 by §18 below**:
  SC-001 itself was subsequently amended (a deliberate product decision,
  not a re-measurement) to accept ≥19/20 for the MVP — see §18 for the
  full amendment record.
- **Historical data preserved**: all `qwen3:4b`-labeled measurements in
  §§1–16 above (the original Polish-phase diagnosis, rule-7/rule-8
  experiments, the §15 reproducibility experiment, and the §16
  post-revert confirmation) describe `qwen3:4b` runs specifically and are
  left exactly as recorded — they are historical baseline results, not
  retroactively relabeled as `qwen3:8b`. `qwen3:4b` was the default when
  those sections were written; `qwen3:8b` is the default as of this
  section.

## 18. SC-001 acceptance-criterion amendment: 19/20 accepted for the MVP (2026-08-19)

- **Decision**: SC-001 (`spec.md`) is amended from an absolute 100%
  (20/20) grounded-accuracy requirement to **grounded accuracy ≥19/20
  (≥95%)** on the frozen 30-question benchmark. This is a deliberate
  product/acceptance-criteria decision, made explicitly in `spec.md`'s
  "SC-001 acceptance-criterion amendment" section and its 2026-08-19
  Clarifications entry — it is **not** a claim that the original 20/20
  target was actually reached; §17 above still accurately records that it
  was not.
- **Basis**: the already-measured, already-confirmed §17 result —
  `qwen3:8b`, deterministic config (`OLLAMA_THINK=false`,
  `OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`), 19/20 (95%) grounded, 7/7
  insufficient-information rejection, 0/7 false-grounded, 3/3
  out-of-scope. No benchmark was re-run for this amendment — it is a
  specification/status change applied to the existing, already-verified
  result in `eval/results/qwen3-8b-think-false.json`.
- **Sole remaining case**: question #6, "Czy na treningach ćwiczy się w
  butach?" — the retrieved context explicitly contains "Ćwiczenia
  odbywają się na boso," a semantic-negation/inference edge case, not a
  retrieval failure or a safety failure. Retained in `eval/questions.jsonl`
  with its original `grounded` expected outcome, unchanged, and
  documented as a known, accepted MVP limitation (not silently dropped or
  hidden).
- **Why no further tuning was attempted**: §16's rule-8 experiment
  targeted exactly this class of case (logical negation of an explicit
  fact, among other patterns) and, despite careful, narrow scoping,
  caused a severe measured regression (35%/7/20, down from 85%/17/20) on
  the `qwen3:4b` backend. That result stands as direct evidence that
  further global prompt calibration aimed at this one remaining
  edge case carries a real, demonstrated risk of broad grounded-recall
  regression — a risk judged not worth taking to close a single case when
  every safety metric is already at or above target.
- **Safety criteria explicitly not weakened**: SC-002 (insufficient-
  information rejection ≥6/7) and SC-003 (false-grounded ≤15%/≤1-in-7)
  are unchanged from their original wording and are independently met
  (7/7, 0/7) by the same measured result.
- **Outcome**: with SC-001 (amended), SC-002, and SC-003 all met on the
  `qwen3:8b` default, and SC-004–SC-007 already satisfied (§11 A/B
  comparison; 335 passing automated tests, none requiring GPU/live-model
  access; existing eval-report format), **feature 004 is documented as
  complete** (`spec.md` Status field) — with question #6 retained as a
  known, accepted MVP limitation, not as an unresolved gap.
