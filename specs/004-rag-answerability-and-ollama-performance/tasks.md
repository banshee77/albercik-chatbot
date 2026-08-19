---

description: "Task list for feature 004-rag-answerability-and-ollama-performance"
---

# Tasks: RAG Answerability & Ollama Performance

**Input**: Design documents from `/specs/004-rag-answerability-and-ollama-performance/`
(plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: plan.md, spec.md (required); research.md, data-model.md,
contracts/chat-endpoint-delta.md, quickstart.md (all present, all read)

**Tests**: Included — explicitly required by plan.md's Testing/Project
Structure sections and Constitution Principle XI (Testing Discipline); every
provider/application behavior change below ships with a corresponding
mocked-transport unit or contract test, never a real Ollama/Anthropic/GPU
call (SC-006).

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3)
so each can be implemented, tested, and demoed independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)
- Every task names its exact file path(s)

## Path Conventions

Single existing backend project (`src/albercik_chatbot/`, `tests/`,
`scripts/`, `eval/`, `alembic/`) — no new top-level directory (plan.md
Structure Decision).

---

## Phase 1: Setup

**Purpose**: Confirm the one new-ish dependency assumption this feature
relies on before touching any provider code.

- [X] T001 Confirm the installed `anthropic` SDK version in `pyproject.toml`/`uv.lock` is ≥0.122.0 and exposes `anthropic.types.output_config_param.OutputConfigParam` and `anthropic.types.json_output_format_param` (research.md §4); bump the pin if the installed version is older, run `uv sync`

**Checkpoint**: Dependency assumption verified — safe to build the shared answerability contract on it.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one shared type both providers and the application layer
depend on. **No user story can be implemented until this phase is done** —
every subsequent task references `LLMResult.answer`/`.supported` and/or
`ANSWERABILITY_JSON_SCHEMA`.

⚠️ **CRITICAL**: This phase intentionally leaves `ollama_provider.py`,
`anthropic_provider.py`, and `ask_question.py` referencing the now-removed
`LLMResult.text` field until their respective story-phase tasks (T008–T010)
update them — expected transient breakage, not a regression to fix here.

- [X] T002 Add `ANSWERABILITY_JSON_SCHEMA` module-level constant (`{"type": "object", "properties": {"supported": {"type": "boolean"}, "answer": {"type": "string"}}, "required": ["supported", "answer"]}`) and extend the `LLMResult` dataclass — add `supported: bool`, rename `text: str` → `answer: str`, add `provider_metrics: dict[str, int] | None = None` — in `src/albercik_chatbot/providers/llm/protocol.py` (data-model.md "LLMResult (modified)", "ANSWERABILITY_JSON_SCHEMA (new constant)")
- [X] T003 [P] Update `FakeLLMProvider`'s default response in `tests/fakes/fake_llm_provider.py` to `LLMResult(answer="To jest odpowiedź testowa.", supported=True, model="fake-llm", input_tokens=10, output_tokens=5, latency_ms=1, provider_metrics=None)` (depends on T002)

**Checkpoint**: `LLMResult`'s new shape exists — user story implementation can now begin.

---

## Phase 3: User Story 1 - Chatbot honestly admits when it doesn't know (Priority: P1) 🎯 MVP

**Goal**: Replace "the model returned text ⇒ grounded" with a structured,
provider-independent `supported`/`answer` decision from the single existing
LLM call, so questions the retrieved context doesn't actually answer are
classified `insufficient_information` instead of `grounded` (FR-001–FR-004,
FR-007–FR-010, FR-027).

**Independent Test**: Run `eval/questions.jsonl` (or the contract tests
below) and confirm previously-false-grounded `insufficient_information`-
expected questions are now correctly classified, while `grounded`/
`out_of_scope` questions are unaffected.

### Tests for User Story 1

- [X] T004 [P] [US1] In `tests/unit/test_ollama_provider.py`: assert the `/api/chat` request body includes `"format": ANSWERABILITY_JSON_SCHEMA`; assert `complete()` returns `LLMResult(answer=..., supported=...)` parsed from a canned `message.content` JSON string; assert a malformed body (invalid JSON, missing `supported`/`answer` key, or wrong type) makes `complete()` raise `LLMProviderError` — **not** a synthesized `LLMResult(supported=False, ...)` (research.md §5)
- [X] T005 [P] [US1] In `tests/unit/test_anthropic_provider_retries.py`: assert `messages.create(...)` is called with `output_config={"format": {"type": "json_schema", "schema": ANSWERABILITY_JSON_SCHEMA}}`; assert `complete()` parses a canned text-content JSON string into `LLMResult(answer=..., supported=...)`; assert malformed/unparseable content makes `complete()` raise `LLMProviderError`, not a synthesized result
- [X] T006 [P] [US1] Add contract tests (new `tests/contract/test_chat_answerability.py`) using `FakeLLMProvider`: `supported=True` → `ChatResponse.outcome == "grounded"`; `supported=False` → `outcome == "insufficient_information"` and the fixed message is returned (never `result.answer`'s content); `FakeLLMProvider(error=LLMProviderError(...))` → `outcome == "unavailable"`, confirming a provider-level failure never becomes `insufficient_information` (FR-008, FR-027)

### Implementation for User Story 1

- [X] T007 [US1] In `src/albercik_chatbot/providers/llm/ollama_provider.py::complete()`: add `"format": ANSWERABILITY_JSON_SCHEMA` to the `/api/chat` request body; replace the current `text = body["message"]["content"]` extraction with `json.loads()`-parsing that string into `supported`/`answer`; on `json.JSONDecodeError`, missing key, or wrong type, log a warning (mirroring the existing malformed-envelope warning) and raise `LLMProviderError` — do not return a result; on success return `LLMResult(answer=..., supported=..., model=..., input_tokens=..., output_tokens=..., latency_ms=..., provider_metrics=None)` (`provider_metrics` populated later, T019) (depends on T002, T004)
- [X] T008 [US1] In `src/albercik_chatbot/providers/llm/anthropic_provider.py::complete()`: pass `output_config={"format": {"type": "json_schema", "schema": ANSWERABILITY_JSON_SCHEMA}}` to `self._client.messages.create(...)`; replace the current plain-text-join extraction with `json.loads()`-parsing the joined text content into `supported`/`answer`; on parse/validation failure, log a warning and raise `LLMProviderError`; on success return `LLMResult(answer=..., supported=..., model=..., input_tokens=..., output_tokens=..., latency_ms=..., provider_metrics=None)` (depends on T002, T005)
- [X] T009 [US1] In `src/albercik_chatbot/application/ask_question.py::ask_question()`, replace the final `return AskQuestionResult(outcome="grounded", answer=result.text, ...)` with a branch on `result.supported`: `True` → `outcome="grounded", answer=result.answer, sources=extract_sources(limited_chunks)`; `False` → `outcome="insufficient_information", answer=_INSUFFICIENT_INFORMATION_MESSAGE` (no sources) — the existing `except LLMProviderError: ... outcome="unavailable"` block is unchanged and now also covers malformed structured output for free (depends on T007, T008)
- [X] T010 [US1] Update rule 5 of `SYSTEM_PROMPT` in `src/albercik_chatbot/domain/prompting.py`: replace "Jeśli w kontekście nie ma wystarczających informacji... powiedz to wprost" with an instruction that the model must decide `supported`/`answer` together and set `supported=false` whenever KONTEKST does not actually contain the information needed to answer (research.md §13.1)

**Checkpoint**: User Story 1 is fully functional and independently testable — `eval/questions.jsonl`'s insufficient-information rejection rate should rise materially above the 0/7 baseline.

---

## Phase 4: User Story 2 - Chatbot never invents a negative fact from silence (Priority: P2)

**Goal**: Stop the model from converting silence about a topic into a
confident fabricated negative claim (FR-005, FR-006).

**Independent Test**: Using targeted example questions where context is
silent (but topically adjacent) on the asked-about topic, confirm the
chatbot responds with `insufficient_information` rather than a fabricated
"no."

### Tests for User Story 2

- [X] T011 [P] [US2] In `tests/unit/test_prompting.py`, add a test asserting the no-negative-inference rule text is present in `SYSTEM_PROMPT` (e.g. asserting on a distinctive substring of the new rule)

### Implementation for User Story 2

- [X] T012 [US2] Add the no-negative-inference rule to `SYSTEM_PROMPT` in `src/albercik_chatbot/domain/prompting.py` (research.md §13.2): absence of information about a topic in KONTEKST is not evidence of a negative answer; the model must not conclude "Albertos does not do/offer/allow X" merely because X is unmentioned — only an explicit statement in KONTEKST may ground a negative answer (depends on T010, since both rules live in the same `SYSTEM_PROMPT` constant)

**Checkpoint**: User Stories 1 AND 2 both work independently — re-run `eval/questions.jsonl` and spot-check the silent-context example questions from spec.md User Story 2.

---

## Phase 5: User Story 3 - Faster answers from the local model (Priority: P3)

**Goal**: A server-only `OLLAMA_THINK` setting controlling Qwen3's reasoning
mode, plus performance telemetry and extended eval tooling to measure its
effect (FR-012–FR-025).

**Independent Test**: With Stories 1–2 already in place, run the frozen
benchmark once with `OLLAMA_THINK=true` and once with `OLLAMA_THINK=false`,
and produce a report comparing accuracy and latency between the two runs;
confirm no `ChatRequest` field can influence the setting.

### Tests for User Story 3

- [X] T013 [P] [US3] In `tests/unit/test_ollama_provider.py`, add tests asserting: `think: true`/`think: false` is forwarded on the `/api/chat` request body exactly per the constructor-supplied setting; `provider_metrics` is populated as `{"total_duration_ns": ..., "load_duration_ns": ..., "prompt_eval_duration_ns": ..., "eval_duration_ns": ...}` copied verbatim (no unit conversion) from the response body's `total_duration`/`load_duration`/`prompt_eval_duration`/`eval_duration` fields when present, and is `None` when absent
- [X] T014 [P] [US3] In `tests/contract/test_chat_no_client_override.py`, add a test (alongside the existing provider-override tests) confirming no `ChatRequest` field can influence `think` mode — `ChatRequest`'s existing `extra="forbid"` plus its single `question` field already make this structurally impossible; assert this remains true (FR-013)
- [X] T015 [P] [US3] Add `tests/unit/test_run_eval.py` covering `scripts/run_eval.py`'s pure-Python summarization logic: latency `avg`/`p50`/`p95`, generation tokens/sec, prompt-eval tokens/sec, and the `None`-when-missing-data cases (FR-019) — factor this logic out of `_summarize()`/`_run_questions()` into small pure functions first if needed to make it unit-testable without an HTTP client

### Implementation for User Story 3

- [X] T016 [P] [US3] Add `OLLAMA_THINK: bool = False` to `Settings` in `src/albercik_chatbot/config.py`; document it in `.env.example` next to the other Ollama provider settings
- [X] T017 [US3] Add a `think: bool` constructor parameter to `OllamaLLMProvider.__init__` in `src/albercik_chatbot/providers/llm/ollama_provider.py`, stored as `self._think`; in `complete()`, add `"think": self._think` to the `/api/chat` request body (depends on T007, T013)
- [X] T018 [US3] In the same `complete()` method, read `total_duration`/`load_duration`/`prompt_eval_duration`/`eval_duration` from the response body (when present) into `LLMResult(provider_metrics={"total_duration_ns": ..., "load_duration_ns": ..., "prompt_eval_duration_ns": ..., "eval_duration_ns": ...})` — native nanosecond values, no conversion; never read `message.thinking` regardless of `think`'s value (research.md §7, FR-016) (depends on T007, T013)
- [X] T019 [US3] Pass `settings.OLLAMA_THINK` into `OllamaLLMProvider(...)` construction in `_build_configured_llm_provider()`, `src/albercik_chatbot/main.py` (depends on T016, T017)
- [X] T020 [P] [US3] Add a nullable `provider_metrics` column (`JSONB`) to `UsageRecord` in `src/albercik_chatbot/persistence/models.py` (data-model.md "UsageRecord (extended)")
- [X] T021 [US3] Create Alembic migration `alembic/versions/<new>_add_usage_records_provider_metrics.py`: purely additive `ADD COLUMN provider_metrics JSONB NULL`, no backfill (depends on T020)
- [X] T022 [US3] In `_record_usage()` and its call site in `src/albercik_chatbot/application/ask_question.py::ask_question()`, thread `result.provider_metrics` through to the `UsageRecord` row as an opaque value — no key is read or branched on anywhere in this module (depends on T018, T020)
- [X] T023 [P] [US3] Add `request_id: uuid.UUID` to `ChatResponse` in `src/albercik_chatbot/api/schemas.py` (contracts/chat-endpoint-delta.md)
- [X] T024 [US3] In `post_chat()`, `src/albercik_chatbot/api/routers/chat.py`, capture the `request_id` already generated for `ask_question(...)` into a local variable and pass it into the `ChatResponse(...)` construction (depends on T023)
- [X] T025 [US3] Extend `scripts/run_eval.py`: after each `/chat` call, open a session via `persistence.database.get_session_factory()` and query the `usage_records` row matching `request_id`/`provider_kind='llm'` for `input_tokens`, `output_tokens`, `provider_metrics`; add `latency_avg_ms`/`latency_p50_ms`/`latency_p95_ms` to `_summarize()`; add per-question `tokens_per_second` (`output_tokens / (eval_duration_ns / 1e9)`, falling back to `output_tokens / (latency_ms/1000)` when Ollama-specific data is absent), `prompt_eval_tokens_per_second` (`input_tokens / (prompt_eval_duration_ns / 1e9)`, Ollama-only, no fallback), and `load_duration_ms`; add `avg_output_tokens`, `avg_tokens_per_second`, `avg_prompt_eval_tokens_per_second`, `avg_load_duration_ms` to the summary; add a `--save-json <path>` CLI option serializing results+summary (research.md §9, §10) (depends on T024, T015)
- [X] T026 [US3] Create `scripts/compare_eval_runs.py <run_a.json> <run_b.json>`: load two `--save-json` reports and print a side-by-side table (accuracy per category, average/p50/p95 latency, average output tokens, tokens/sec) (research.md §11) (depends on T025)
- [X] T027 [P] [US3] Update `eval/README.md`: document the new per-question/aggregate metrics (tokens/sec, prompt-eval tokens/sec, load duration, latency percentiles) and the `OLLAMA_THINK` A/B procedure using `compare_eval_runs.py`
- [X] T028 [P] [US3] Update `README.md`: document `OLLAMA_THINK`, the structured-answerability behavior change, and known limitations (e.g. the 7-item benchmark's MVP-gate framing, spec SC-002 note)

**Checkpoint**: All three user stories are independently functional; an `OLLAMA_THINK` A/B comparison report can be produced (SC-004).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite verification that nothing outside this feature's
scope regressed, and that the feature's own numeric/acceptance targets are
met and recorded.

- [X] T029 [P] Run `uv run pytest` (full suite) and confirm every failure, if any, is a deliberate, documented `LLMResult`/`ChatResponse` contract change from this feature — never a silent regression (SC-005)
- [X] T030 [P] Run `uv run pytest tests/contract/ tests/unit/test_budget.py tests/unit/test_provider_selection.py -v` and confirm all existing cost/abuse controls (rate limiting, kill switch, budget, concurrency, size limits, prompt-injection defenses) remain intact and unweakened (FR-026)
- [X] T031 Run `uv run python scripts/run_eval.py --save-json eval/results/qwen3-4b-think-false.json` against the real Ollama backend (`qwen3:4b`, GPU) and check SC-001–SC-003 — **executed 2026-08-18; SC-002 (insufficient-information ≥6/7 — measured 7/7) and SC-003 (false-grounded ≤15% — measured 0/7) MET; out-of-scope 3/3 MET; SC-001 (grounded accuracy 20/20) NOT MET — measured 13/20 (65%).** Not fixed per this task's scope (no retrieval/prompt/benchmark changes made) — see `eval/README.md` "Known open issue" for the exact 7 failing questions and root-cause discussion; feature 004 is NOT safe to close on SC-001 until a follow-up addresses it.
- [X] T032 Run the `OLLAMA_THINK=true` vs `OLLAMA_THINK=false` comparison via `scripts/compare_eval_runs.py` (quickstart.md Scenario 6) and record the chosen default with justification in `eval/README.md` or the feature PR description (SC-004) — do not assume `think=false` is better without this output. **Executed 2026-08-18 against real `qwen3:4b`: `think=false` selected as the default** — ~3.6x faster on average (2467ms vs 8948ms) and `think=true` introduced 6/30 new `unavailable` outcomes (answer-token budget exhausted by reasoning before valid structured output) not present under `think=false`. Full table + reports in `eval/README.md`/`eval/results/`.
- [X] T033 Execute `quickstart.md` Scenarios 1–7 end-to-end against the running Docker Compose stack

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational; T012 depends on T010 (same `SYSTEM_PROMPT` constant) — implement after US1 in practice, though its own tests (T011) can be drafted earlier
- **User Story 3 (Phase 5)**: Depends on Foundational; T017/T018 extend the same `ollama_provider.py::complete()` method US1 already modified (T007) — implement after US1 is functional, per spec's own story ordering ("the answerability fix... must be in place before latency numbers are compared")
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each Story

- Tests are written first and should fail before their corresponding implementation task lands
- Provider changes (Ollama, Anthropic) before the `ask_question.py` branch that consumes them
- `SYSTEM_PROMPT` changes are independent of provider-code changes but share one file (T010, T012) — sequence, don't parallelize, those two

### Parallel Opportunities

- T004, T005, T006 (US1 tests, different files) in parallel
- T007 and T008 (Ollama vs. Anthropic provider implementation, different files) in parallel once T002 lands
- T013, T014, T015 (US3 tests, different files) in parallel
- T016, T020, T023 (US3: config, persistence column, schema field — different files, no interdependency) in parallel
- T027, T028 (doc updates) in parallel with each other and with T029/T030

---

## Parallel Example: User Story 1

```bash
# Tests, launched together:
Task: "Structured-output + malformed→LLMProviderError tests in tests/unit/test_ollama_provider.py"
Task: "Structured-output + malformed→LLMProviderError tests in tests/unit/test_anthropic_provider_retries.py"
Task: "Contract tests for supported=True/False/error in tests/contract/test_chat_answerability.py"

# Implementation, launched together once T002 (Foundational) is done:
Task: "Structured output in src/albercik_chatbot/providers/llm/ollama_provider.py"
Task: "Structured output in src/albercik_chatbot/providers/llm/anthropic_provider.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (User Story 1)
3. **STOP and VALIDATE**: run `eval/questions.jsonl`, confirm insufficient-information rejection rises from 0/7
4. Deploy/demo if ready — this alone fixes the dominant failure mode (spec's "Why this priority" for US1)

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add User Story 1 → validate independently → this is the MVP
3. Add User Story 2 → validate independently (silent-context examples)
4. Add User Story 3 → validate independently (A/B report, SC-004)
5. Phase 6 Polish → full-suite + acceptance-gate verification

### Notes

- No parallel-team story split is recommended here despite the phase
  structure: US2 and US3 both touch files US1 already modified
  (`prompting.py`, `ollama_provider.py`), so sequential P1→P2→P3 delivery
  avoids merge conflicts, even though each story remains independently
  testable once its predecessor lands.
- Commit after each task or logical group; stop at any checkpoint to
  validate a story independently before moving to the next.
