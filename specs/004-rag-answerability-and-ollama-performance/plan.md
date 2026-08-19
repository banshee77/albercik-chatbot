# Implementation Plan: RAG Answerability & Ollama Performance

**Branch**: `004-rag-answerability-and-ollama-performance` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-rag-answerability-and-ollama-performance/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The chatbot currently decides "grounded" vs. "insufficient information" purely
from whether the LLM produced text at all, which is why 7/7 insufficient-
information questions are currently misclassified as grounded (the model
often *says* it lacks context, but the app never listens). The fix: extend
`LLMProvider.complete()`'s single grounded-generation call to return a
structured `supported: bool` decision alongside the answer text — both
providers implement the same contract via their own native structured-output
mechanism (Ollama's `format` JSON-schema parameter; Anthropic's native
`output_config`/`json_schema` structured outputs, both parsing the same
shared JSON schema — no forced tool-use) — and make
`application/ask_question.py` branch on that field instead of "LLM returned
text ⇒ grounded". A new system-prompt rule stops the model from inventing
negative facts from silent context. A **successfully parsed**
`supported=false` result maps to `insufficient_information`; a **malformed or
unparseable** structured response is a provider/protocol failure and maps to
the existing `unavailable` outcome (via `LLMProviderError`), never silently
treated as either `grounded` or `insufficient_information`. Separately, a new
`OLLAMA_THINK` setting — owned entirely by `OllamaLLMProvider`, not part of
the shared `LLMProvider` interface — controls Qwen3's reasoning mode,
measured via an extended `scripts/run_eval.py` (adds p50/p95 latency, token
counts, generation and prompt-eval tokens/sec, load duration, and a two-run
comparison script) against the frozen 30-question benchmark, targeting ≥85%
(≥6/7 — an MVP acceptance gate sized to this small fixture set, not a
statistical production guarantee) insufficient-information rejection and
≤15% false-grounded on the Ollama backend while holding grounded/out-of-scope
accuracy at 100%.

## Technical Context

**Language/Version**: Python 3.13 (existing project; see `pyproject.toml`)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, `anthropic` SDK
(≥0.122.0 — the installed version already ships the stable, non-beta
`output_config`/`json_schema` structured-outputs parameter used here;
confirmed present in `anthropic/types/output_config_param.py` and
`json_output_format_param.py`), `httpx` (already used directly for the
Ollama HTTP API — no new SDK), `pydantic` / `pydantic-settings`, Alembic

**Storage**: PostgreSQL + pgvector (unchanged); one additive nullable
column on the existing `usage_records` table (see data-model.md) via a new
Alembic migration

**Testing**: `pytest`, `httpx.MockTransport` (Ollama), a fake
`_AnthropicClientLike` transport (Anthropic) — both patterns already
established by `tests/unit/test_ollama_provider.py` and
`tests/unit/test_anthropic_provider_retries.py`; no real provider, GPU, or
paid call in the automated suite (Principle XI, spec Testing section)

**Target Platform**: Linux server (Docker Compose), local Ollama container
+ optional Anthropic API

**Project Type**: Single backend web service (existing structure; no new
project)

**Performance Goals**: No new fixed latency target — Story 3 is a measured
A/B comparison (`OLLAMA_THINK=true` vs. `false`) with the resulting default
choice documented, not assumed (spec SC-004)

**Constraints**: Answerability decision MUST come from the same LLM call
that produces the answer (no second call); a malformed/unparseable
structured response MUST fail safe to the existing `unavailable` outcome
(provider/protocol failure), never `grounded` and never
`insufficient_information`; only a successfully-parsed `supported=false`
result maps to `insufficient_information`; `OLLAMA_THINK` MUST be
server-only and owned by `OllamaLLMProvider` (not part of the shared
`LLMProvider.complete()` signature); `LLMResult.provider_metrics` MUST
stay opaque to core RAG/application decision logic — `application/
ask_question.py` and `domain/` may use `supported`, `answer`, and the
normalized `input_tokens`/`output_tokens` counts, but MUST NOT read or
branch on any key inside `provider_metrics` (usage accounting/evaluation
only); every `provider_metrics` timing key MUST carry an explicit unit
suffix (`*_duration_ns`), never a bare name; existing cost/abuse controls
MUST remain intact (Principle X)

**Scale/Scope**: One frozen 30-question benchmark (`eval/questions.jsonl`,
unchanged); single-tenant, single Albertos knowledge base (Principle II) —
no scale change from this feature

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Security by Default | No secrets in structured-output schemas, config, or logs; `OLLAMA_THINK` is server config, not a secret | PASS |
| II. Tenancy Posture | No tenant concepts touched | PASS |
| III. Secure RAG | Retrieved content stays data-only; the new "absence ≠ negative evidence" rule lives in the trusted system prompt, never in retrieved content (FR-006); grounding-on-insufficient-context behavior gets *stricter*, not weaker; a parse failure can no longer be silently absorbed into either `grounded` or `insufficient_information` — it surfaces honestly as `unavailable` (FR-008) | PASS |
| V. LLM Provider Neutrality | `LLMProvider` Protocol changes (added `supported`, renamed `text`→`answer`, added `provider_metrics`) apply identically to both providers; both use the same shared `ANSWERABILITY_JSON_SCHEMA` via their own native structured-output mechanism (Ollama `format`; Anthropic `output_config`/`json_schema` — no forced tool-use); `application/ask_question.py` and `domain/` gain **no** Ollama/Anthropic branching — see research.md §1, §4 | PASS |
| VI. Embedding Provider Neutrality | Untouched — embeddings are out of scope for this feature | PASS (N/A) |
| VII. Provider/Cloud Neutrality | No cloud-specific dependency added | PASS |
| VIII. API Security | `ChatRequest` keeps `extra="forbid"`; the one new public field (`ChatResponse.request_id`) is additive and non-sensitive | PASS |
| IX. Privacy and Logging | Reasoning/"thinking" content is never read past `message.content`/the structured `answer` field, never logged, never persisted (FR-016, FR-020) | PASS |
| X. Cost Safety | No new client-controllable parameter; `OLLAMA_THINK` (owned by `OllamaLLMProvider`, not the shared Protocol) and the structured-output schema are server-side only; no new LLM call added (still exactly one per grounded question) | PASS |
| XI. Testing Discipline | All new provider behavior covered by mocked-transport unit tests; no real-provider/GPU dependency (spec Testing section, items 1–14) | PASS |
| XII/XIII. Engineering Quality / Simplicity | No new abstraction layer; `LLMResult` gains fields rather than a parallel type; telemetry reuses the existing `usage_records` table (one nullable JSONB column) instead of a new store — see research.md §8 | PASS |
| XIV. Approved Stack | No technology outside Python/FastAPI/PostgreSQL/pgvector/SQLAlchemy/Alembic/Anthropic API/Docker/`uv` introduced | PASS |

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-rag-answerability-and-ollama-performance/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Existing single-project layout (`src/albercik_chatbot/`, `tests/`,
`scripts/`, `eval/`, `alembic/`) — no new top-level directory. Modified and
new files only:

```text
src/albercik_chatbot/
├── providers/llm/
│   ├── protocol.py                 # MODIFY: LLMResult (+supported, text→answer, +provider_metrics), ANSWERABILITY_JSON_SCHEMA
│   ├── ollama_provider.py          # MODIFY: format=schema, think=constructor-owned setting, parse structured JSON, malformed→LLMProviderError, provider_metrics (*_duration_ns)
│   └── anthropic_provider.py       # MODIFY: output_config={"format": {"type": "json_schema", "schema": ANSWERABILITY_JSON_SCHEMA}}, parse structured JSON text, malformed→LLMProviderError
├── domain/
│   └── prompting.py                # MODIFY: SYSTEM_PROMPT — structured-answer + no-negative-inference rule
├── application/
│   └── ask_question.py             # MODIFY: branch on result.supported for grounded vs. insufficient_information
├── api/
│   ├── schemas.py                  # MODIFY: ChatResponse += request_id
│   └── routers/chat.py             # MODIFY: capture request_id, pass into ChatResponse
├── config.py                       # MODIFY: += OLLAMA_THINK
├── main.py                         # MODIFY: pass settings.OLLAMA_THINK into OllamaLLMProvider(...)
└── persistence/models.py           # MODIFY: UsageRecord += provider_metrics (nullable JSONB)

alembic/versions/
└── <new>_add_usage_records_provider_metrics.py   # NEW migration

scripts/
├── run_eval.py                     # MODIFY: read request_id, query usage_records directly for tokens/provider_metrics, add p50/p95 + tokens/sec, --save-json
└── compare_eval_runs.py            # NEW: side-by-side think=true vs. think=false report from two --save-json outputs

eval/README.md                      # MODIFY: document new metrics + think A/B procedure
README.md, .env.example             # MODIFY: OLLAMA_THINK, structured answerability, known limitations

tests/
├── fakes/fake_llm_provider.py      # MODIFY: default supported=True, new field
├── unit/test_ollama_provider.py    # MODIFY/ADD: structured output, think forwarding, malformed→LLMProviderError, telemetry parsing (*_duration_ns)
├── unit/test_anthropic_provider_*.py # MODIFY/ADD: output_config/json_schema structured output, malformed→LLMProviderError, shared-contract parity
├── unit/test_prompting.py          # ADD (or extend): no-negative-inference rule present in SYSTEM_PROMPT
├── contract/test_chat_*.py         # MODIFY/ADD: supported=True→grounded, supported=False→insufficient_information, malformed/provider failure→unavailable
└── unit/test_run_eval*.py          # ADD if run_eval.py's pure-Python summarization logic (p50/p95, tokens/sec) is factored out for unit testing
```

**Structure Decision**: Single existing backend project — this feature
extends already-established modules (`providers/llm/`, `domain/`,
`application/`, `api/`, `config.py`, `main.py`, `persistence/models.py`,
`scripts/`, `eval/`) in place. No new service, package, or deployment unit.

## Complexity Tracking

*No Constitution Check violations — this section is not needed.*
