# Implementation Plan: LLM / RAG Observability

**Branch**: `012-rag-observability` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-rag-observability/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Add structured, vendor-neutral end-to-end tracing of the existing chat/RAG
pipeline (`chat.py` → `ask_question.py` → `record_conversation()`) for
operator/developer diagnosis, built on the OpenTelemetry Python SDK with
Phoenix as the first local-development OTLP backend, disabled by default,
never influencing chat behavior or reliability. The whole feature is one new
`infra/observability.py` module plus additive instrumentation calls at
existing pipeline stage boundaries in `ask_question.py`/`chat.py`/
`record_conversation.py`, seven new `Settings` fields, and one optional
Compose service. No new HTTP endpoints, no new database tables, no changes
to the public chat contract (research.md, data-model.md).

## Technical Context

**Language/Version**: Python 3.14 (unchanged — existing project requirement)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, existing project stack,
plus three new libraries for this feature: `opentelemetry-api`,
`opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`
(research.md R3)

**Storage**: PostgreSQL/pgvector — unchanged, no new tables or columns
(data-model.md). Trace data itself is never persisted by Shiruno's own
database; it lives only in the OTLP backend (Phoenix locally).

**Testing**: pytest (unchanged), using `opentelemetry-sdk`'s own
`InMemorySpanExporter` + `SimpleSpanProcessor` for span-assertion tests —
no new test dependency, no real Phoenix/network/Ollama/Anthropic
requirement (research.md R12)

**Target Platform**: Linux server (Docker container) — unchanged

**Project Type**: Web service (single FastAPI application) — unchanged

**Performance Goals**: No new performance target; the explicit requirement
is the *absence* of a measurable effect on `/chat` latency/success rate
whether tracing is disabled, enabled with a working backend, or enabled
with an unreachable backend (FR-032–034, SC-004)

**Constraints**: Export must never block the visitor-facing response beyond
the OTel SDK's own async `BatchSpanProcessor` behavior (FR-033); zero
content capture by default (FR-013–017); no raw exception text/credentials
ever exported (FR-005, FR-020, FR-026)

**Scale/Scope**: One new module (`infra/observability.py`), instrumentation
calls added at 8 existing pipeline-stage boundaries across 3 existing
files, 7 new config settings, 1 new optional Compose service — no new API
surface (FR-042)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default | PASS | No new trust boundary; traces are operator-only, never influence authz. |
| II. Multi-Tenant Isolation | PASS | Tenant attributes are server-derived only (research.md R8); no client-supplied tenant value can reach a trace (FR-028/029). |
| III. Secure RAG | PASS | Retrieval/generation instrumentation is read-only observation of decisions already made elsewhere; adds no new decision path. |
| IV. Secure Document Ingestion | N/A | This feature touches no ingestion code. |
| V. LLM Provider Neutrality | PASS | Instrumentation reads `LLMResult`/`AskQuestionResult` fields already exposed through the existing `LLMProvider` Protocol; no provider-specific branching added (FR-023). |
| VI. Embedding Provider Neutrality | PASS | Same — reads existing `EmbeddingProvider` call sites, no new coupling. |
| VII. Provider and Cloud Neutrality | PASS | OTel is itself a vendor-neutral standard (the point of Assumption 1); Phoenix is isolated behind the OTLP exporter boundary, swappable for Langfuse or another backend without application-code changes (research.md R11). |
| VIII. API Security | PASS | No new API surface (FR-042); public `/chat` request/response contract unchanged (FR-039). |
| IX. Privacy and Logging | PASS | This feature is largely *in service of* this principle applied to a new channel — FR-005/013–020 are all privacy-by-default requirements for the new trace data specifically. |
| X. Cost Safety | PASS | Tracing adds no LLM/embedding calls and cannot be enabled/influenced by a client; export failure cannot turn a successful response into a retried or extra paid call. |
| XI. Testing Discipline | PASS | research.md R12 — mockable via `InMemorySpanExporter`, no paid-provider requirement; reliability (FR-032–034) gets explicit test coverage. |
| XII. Engineering Quality | PASS | One cohesive new module; existing call sites gain additive instrumentation, no restructuring. |
| XIII. Simplicity for MVP | PASS | research.md R2/R9 explicitly reject two candidate abstractions (a SAVEPOINT-analogue, a persisted `trace_id` column) as solving problems this feature doesn't actually have. |
| **XIV. Approved MVP Technology Stack** | **PASS** | Resolved 2026-08-20 by constitution amendment v4.0.0 → v4.1.0: OpenTelemetry added to the approved stack as the vendor-neutral tracing standard, with an explicit "Observability boundary" clause (no application decision may depend on tracing; backend unavailability may never affect public chat); Phoenix approved narrowly as the optional, operator/developer-only, OTLP-reached, replaceable local backend. This plan's design (research.md R1–R12) already matched these constraints before the amendment — the amendment closes the process gate, not a design gap. |

**Principle XIV gate — resolved**: The constitution was amended
(`.specify/memory/constitution.md`, v4.0.0 → v4.1.0, 2026-08-20) to add
OpenTelemetry and a narrowly-scoped Phoenix approval to Principle XIV,
following the same process Feature 009 used for its own Principle II
amendment. Feature 012 now passes all 14 Constitution Check gates; nothing
in this plan's architecture changed as a result — the amendment's new
"Observability boundary" and Phoenix-scoping rules were already exactly
what research.md R1 (DI-injected no-op-by-default `Tracer`), R2 (defensive
failure isolation), R10 (optional Compose profile), and R11 (OTel-boundary-
only instrumentation) had independently designed for. Safe to proceed to
`/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/012-rag-observability/
├── plan.md               # This file (/speckit-plan command output)
├── research.md           # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md   # Spec-quality checklist (/speckit-specify, /speckit-clarify)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new HTTP API surface
(FR-042 explicitly forbids a tenant-admin- or customer-facing trace view);
the public `/chat` request/response contract is explicitly unchanged
(FR-039). Trace inspection happens entirely inside Phoenix's own UI, which
this project does not implement or contract against.

### Source Code (repository root)

This is Shiruno's existing single-project FastAPI layout (no frontend/mobile
split — Option 1 applies, with this project's own existing directory names
rather than the generic template ones). This feature adds one new file and
modifies existing files at their current pipeline-stage boundaries; it adds
no new top-level directory.

```text
src/shiruno/
├── infra/
│   ├── observability.py        # NEW — configure_observability(), traced_stage(), Tracer construction (research.md R1/R2)
│   ├── budget.py                # unchanged
│   ├── concurrency.py           # unchanged
│   ├── logging.py               # unchanged
│   └── rate_limit.py            # unchanged
├── api/
│   ├── deps.py                  # + get_tracer() dependency (mirrors get_llm_provider/get_embedding_provider)
│   └── routers/
│       └── chat.py              # + root shiruno.chat span wraps ask_question()/record_conversation() (research.md R5)
├── application/
│   ├── ask_question.py          # + tracer: Tracer parameter; traced_stage() calls at each existing stage boundary (research.md R5)
│   └── record_conversation.py   # + tenant attributes set on the conversation_recording span (research.md R8)
├── config.py                    # + 7 new Settings fields (research.md R4)
└── main.py                      # create_app() gains tracer: Tracer | None = None param; builds app.state.tracer once

tests/
├── unit/
│   └── test_observability.py    # NEW — configure_observability()/traced_stage() unit coverage (research.md R12)
├── integration/
│   └── test_chat_tracing.py     # NEW — span-topology assertions via InMemorySpanExporter, per outcome type
└── contract/
    └── (existing files unchanged — no new HTTP contract)

docker-compose.yml                # + phoenix service under profiles: ["observability"] (research.md R10)
.env.example                      # + documented (commented-out/false) observability settings
```

**Structure Decision**: Single-project FastAPI layout, unchanged from every
prior feature in this codebase. This feature is purely additive
instrumentation layered onto the existing `chat.py` → `ask_question.py` →
`record_conversation.py` call chain plus one new `infra/observability.py`
module — no new service, no new top-level package, no split from the
existing structure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No Constitution Check items require a Complexity Tracking justification —
Principles I–XIII all pass without deviation. Principle XIV is flagged
above (technology-approval gate, not a design-complexity tradeoff) with an
explicit recommendation to resolve it via `/speckit-constitution` before
`/speckit-tasks`, rather than via a Complexity Tracking justification —
Principle XIV's own governance text requires an amendment for this
situation, not a documented exception.
