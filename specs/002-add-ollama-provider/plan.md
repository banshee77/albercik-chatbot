# Implementation Plan: Local Ollama LLM Provider

**Branch**: `002-add-ollama-provider` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-add-ollama-provider/spec.md`

## Summary

Add a second `LLMProvider` implementation — `OllamaLLMProvider` — behind the
existing Principle V interface, alongside the existing `AnthropicLLMProvider`.
Which one answers a question is chosen exclusively by a new server-side
`LLM_PROVIDER` setting (default: `ollama`, per the Clarifications session),
resolved once at app-factory composition time exactly like the existing
provider construction already works. Core RAG logic
(`application/ask_question.py`, `domain/*`) is untouched — it already depends
only on the `LLMProvider` Protocol. The one real architectural addition is a
`UsageRecord.provider_name` column so the existing Anthropic budget query can
structurally exclude local-model usage rather than inferring it from model
name. Ollama is reachable only over the internal Docker network (no published
port), with its own bounded-retry/timeout policy mirroring
`AnthropicLLMProvider`'s existing pattern.

**Addendum (User Story 4, spec update 2026-08-18)**: A normal
`docker compose up -d` must produce a working local backend without a
separate manual `ollama pull` step. This is a pure deployment/Compose
concern — a new one-shot `ollama-init` service (research.md §6a) ensures
the configured `OLLAMA_MODEL` is present before `app` starts, gated by
Compose's own `depends_on: condition:` mechanism. No application or domain
code changes; `OllamaLLMProvider`, `ask_question.py`, and the composition
boundary in `main.py` are unaffected by this addendum.

## Technical Context

**Language/Version**: Python 3.14 (unchanged — existing project)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x + Alembic, `pgvector`,
`anthropic` SDK (existing, unchanged), `httpx` (existing dependency, already
used by the test suite — reused directly for the Ollama HTTP client; no new
SDK dependency introduced for Ollama, consistent with Principle XIII)

**Storage**: PostgreSQL + `pgvector` (unchanged); one additive column on the
existing `usage_records` table (`provider_name`), one new Alembic migration

**Testing**: pytest (existing); `OllamaLLMProvider` unit tests use a mocked
HTTP transport, mirroring exactly how `AnthropicLLMProvider`'s tests already
inject a fake `_AnthropicClientLike` transport — no real Ollama process
required by the automated suite (Principle XI)

**Target Platform**: Linux container (Docker / Docker Compose), unchanged

**Project Type**: Single backend web service (unchanged — no new project)

**Performance Goals**: Not newly specified by the feature; inherits the
existing bounded-timeout/bounded-retry philosophy. Local CPU-hosted inference
is expected to be slower than the hosted Anthropic API, which is why
`OLLAMA_TIMEOUT_SECONDS` is a separate, independently-configurable value
from Anthropic's `PROVIDER_TIMEOUT_SECONDS` rather than reusing it.

**Constraints**: Client MUST NOT be able to select provider/model/generation
parameters (Principle X, unchanged); Ollama's HTTP endpoint MUST NOT be
publicly reachable — internal Docker network only; switching backends MUST
require configuration only, no code change (spec FR-004). Addendum: a
normal `docker compose up -d` MUST NOT require a separate manual model-
download command (spec FR-019); model provisioning MUST stay outside
application/domain code (spec FR-025) and MUST NOT unnecessarily re-run
once the model is already present (spec FR-022).

**Scale/Scope**: One new provider implementation file, one new config
section, one additive DB column + migration, two Docker Compose services
(`ollama` + the new one-shot `ollama-init`), doc updates. No new public API
surface, no new project, no new container image (both Compose services
reuse the official `ollama/ollama` image).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| I. Security by Default | No new secrets — Ollama's local API needs no API key by default; if an operator's Ollama deployment requires one, it follows the same env-var pattern as `ANTHROPIC_API_KEY`. LLM output from either backend never used for authz. | PASS |
| II. Tenancy Posture | Untouched — no tenant/org concept anywhere in this feature. | PASS |
| III. Secure RAG | Ollama output MUST receive identical untrusted-content handling as Anthropic (spec FR-015); `domain/prompting.py` stays provider-neutral and unmodified. | PASS |
| IV. Secure Document Ingestion | Not touched — ingestion pipeline unmodified. | N/A |
| V. LLM Provider Neutrality | This feature *is* the anticipated exercise of this principle: a second implementation behind the existing `LLMProvider` Protocol, with `application/ask_question.py` remaining provider-agnostic (spec FR-007). | PASS |
| VI. Embedding Provider Neutrality | Untouched — Ollama embeddings explicitly out of scope (spec). | PASS |
| VII. Provider and Cloud Neutrality | Directly anticipated by the constitution's own text: Principle VII names "a self-hosted model" as an expected future LLM alternative. | PASS |
| VIII. API Security | No new public endpoint; provider selection is 100% server-side config, never client-influenced (spec FR-002). | PASS |
| IX. Privacy and Logging | Ollama failures logged server-side only, mirroring the existing `AnthropicLLMProvider` logging pattern added this session — no internal URLs/stack traces to the client (spec FR-013). | PASS |
| X. Cost Safety (NON-NEGOTIABLE) | Central design driver: local-model usage MUST NOT be able to count toward the Anthropic budget (spec FR-010) — resolved structurally in Phase 1 via a dedicated `provider_name` column, not model-name inference (see data-model.md). All existing rate/concurrency/context/output controls apply identically regardless of backend (spec FR-009). | PASS |
| XI. Testing Discipline (NON-NEGOTIABLE) | Spec mandates `OllamaLLMProvider` unit tests with mocked HTTP responses; automated suite MUST NOT require a real Ollama process (spec FR-017). | PASS |
| XII. Engineering Quality | New provider class follows the already-established `AnthropicLLMProvider` shape (bounded retry loop, `Protocol`-typed transport for testability) — no new pattern introduced. | PASS |
| XIII. Simplicity for MVP | No LangChain/LangGraph/agents/Kubernetes/fallback-routing introduced (spec Out of Scope); provider selection is one small factory decision at the composition boundary, not a plugin framework; reuses `httpx` rather than adding an `ollama` SDK dependency. Automatic model provisioning (User Story 4) reuses the existing `ollama/ollama` image and Compose's own `depends_on: condition:` primitives rather than a custom script, polling loop, or new image (research.md §6a). | PASS |
| XIV. Approved MVP Technology Stack | Ollama itself is not named in the fixed stack list, but is implemented purely as a second `Protocol` implementation using an already-approved dependency (`httpx`) — no new infrastructure category, no new SDK. This is squarely the kind of extension Principle VII already sanctions ("self-hosted model" as an anticipated alternative) rather than a new stack element. Noted here rather than treated as a violation requiring Complexity Tracking. | PASS (noted) |

No violations requiring justification — **Complexity Tracking is empty.**

**Post-Design Re-check** (after Phase 0 `research.md` and Phase 1
`data-model.md`/`quickstart.md` were written): the budget-isolation design
(research.md §4, data-model.md) *strengthens* Principle X compliance versus
a naive implementation — it makes local-model budget exclusion structural
(a dedicated `provider_name` column) rather than inferred, closing exactly
the kind of silent-leakage gap Principle X's "fail closed" language warns
against. No new dependency was introduced (`httpx` is reused, research.md
§1); no new service category beyond the optional-but-default `ollama`
container, which is never publicly reachable (research.md §6). All 14
principles remain **PASS**; the gate is still clean.

**Post-Design Re-check — 2026-08-18 addendum** (after research.md §6a was
added for User Story 4): automatic model provisioning introduces no new
dependency, no new image, and no new public surface — it is entirely a
Compose-level `depends_on`/healthcheck wiring change reusing the existing
`ollama/ollama` image (Principle XIII), keeps the Ollama endpoint internal-
network-only exactly as before (Principle I/VIII, FR-026), and its one
piece of conditional logic (skip provisioning when `LLM_PROVIDER != ollama`)
lives in the init service's own shell command, never in `main.py` or
`application/ask_question.py` (Principle V/XII — no new branching at the
application composition boundary). Fail-closed behavior is preserved and
strengthened: an unprovisionable model now fails *before* `app` starts at
all (Compose `service_completed_successfully`), rather than only being
discoverable at first-request time as before this addendum. All 14
principles remain **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/002-add-ollama-provider/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

No `contracts/` output for this feature: `/api/v1/chat`'s external contract
(`specs/001-albertos-rag-chatbot/contracts/openapi.yaml`) is unchanged by
this feature — same request/response shape, same outcome values, same status
codes. Ollama's own HTTP API is a third-party interface this application
*depends on*, not one it exposes; its request/response shape is documented
in research.md instead, next to the decision that motivates it.

### Source Code (repository root)

```text
src/albercik_chatbot/
├── providers/llm/
│   ├── protocol.py                  # unchanged — existing LLMProvider Protocol
│   ├── anthropic_provider.py        # unchanged
│   └── ollama_provider.py           # NEW — OllamaLLMProvider
├── config.py                        # extended: LLM_PROVIDER, OLLAMA_BASE_URL,
│                                     #   OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
├── main.py                          # extended: LLM_PROVIDER-driven construction
│                                     #   at the existing composition boundary,
│                                     #   plus one startup INFO log line
│                                     #   (provider + model only — never
│                                     #   OLLAMA_BASE_URL/credentials, FR-018)
├── persistence/
│   ├── models.py                    # extended: UsageRecord.provider_name
│   └── repositories.py              # unchanged
├── infra/
│   ├── budget.py                    # extended: filter by provider_name='anthropic'
│   └── logging.py                   # unchanged
└── application/ask_question.py      # unchanged (already provider-neutral)

alembic/versions/
└── <new>_add_usage_record_provider_name.py   # NEW migration

tests/unit/
└── test_ollama_provider.py          # NEW — mocked HTTP, mirrors
                                      #   test_anthropic_provider_retries.py

docker-compose.yml                   # extended: `ollama` service (internal
                                      #   network only, no published port,
                                      #   gains an `ollama list` healthcheck)
                                      #   + NEW one-shot `ollama-init` service
                                      #   (research.md §6a) + `app`'s
                                      #   depends_on gains
                                      #   `ollama-init: service_completed_successfully`

scripts/run_eval.py                  # extended: reports which backend
                                      #   (LLM_PROVIDER) a run was executed against
```

**Structure Decision**: Single existing backend project, unchanged layout
(`plan.md` Option 1 from the original `001-albertos-rag-chatbot` feature).
This feature adds one new file under the already-established
`providers/llm/` boundary and extends existing files at their already-defined
seams (config, composition root, budget query, usage schema) — no new
top-level module, no new service process beyond the `ollama` container
itself. The User Story 4 addendum adds exactly one more Compose service
(`ollama-init`), which is a one-shot startup step, not a long-running
process, and reuses the `ollama` image already present rather than
introducing a new one.

## Complexity Tracking

*No entries — Constitution Check reported no violations requiring
justification.*
