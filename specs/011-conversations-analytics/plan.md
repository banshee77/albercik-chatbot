# Implementation Plan: Conversations & Analytics

**Branch**: `011-conversations-analytics` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-conversations-analytics/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Persist a durable, tenant-owned record of every public chat request that reaches one of the five existing outcomes (grounded, insufficient_information, out_of_scope, unavailable, small_talk), attributed server-side to a configured "public reference tenant" (Albertos) with zero change to the `POST /api/v1/chat` contract. The `ConversationRecord` write happens on a `SAVEPOINT` *nested inside* the same outer, per-request database transaction as existing usage accounting — never a second session, connection, queue, or background worker — so a recording failure rolls back only that savepoint, never the outer transaction; the row is still committed or rolled back together with the rest of the request when the outer transaction concludes, exactly like every other write in that request, and a recording failure can never turn a successful chat answer into an error. Five new tenant-scoped, authenticated admin endpoints (`GET /admin/conversations`, `GET /admin/conversations/{id}`, `GET /admin/analytics/summary`, `GET /admin/analytics/knowledge-gaps`, `GET /admin/analytics/questions`) expose this data using bounded pagination, a 30-day default date-range window, and PostgreSQL-native aggregation (`GROUP BY`, `percentile_cont`) — no BI infrastructure, no LLM-based classification. Tenant-safe usage/provider visibility is achieved by having `ConversationRecord` directly snapshot the operationally-relevant usage fields (tokens, provider, model, latency, a safe failure category, and grounded-answer sources) at write time, rather than retroactively adding `tenant_id` to the pre-existing, cross-feature `UsageRecord` table or backfilling its historical rows; every one of those fields is an immutable, at-write-time snapshot that a later document replacement/deletion or provider/model configuration change never rewrites or reconstructs (research.md §2a). The public reference tenant itself is resolved fail-closed — must exist and be active, no fallback, no auto-creation — by a small, independently-testable function, and a resolution failure affects only whether that request's conversation gets recorded, never the chat response itself.

## Technical Context

**Language/Version**: Python 3.14 (existing, unchanged)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic — all already in use; no new dependency introduced.

**Storage**: PostgreSQL (existing `db`/`db-test` Compose services) — one new table, `conversation_records`, added via a single additive Alembic migration; `usage_records` is unchanged (no new column, no backfill).

**Testing**: `pytest` + `pytest-asyncio`, `httpx.AsyncClient` against `create_app(...)` with fake LLM/embedding providers, real Postgres for integration tests — existing conventions (`tests/conftest.py`, `tests/fixtures/admin.py`) extended, not replaced.

**Target Platform**: Linux server (Docker), unchanged.

**Project Type**: Single existing backend web service (`src/shiruno/`) — no new project/app.

**Performance Goals**: None beyond preserving existing public chat behavior and reliability; analytics endpoints are administrator-scale (not public-traffic-scale) reads, served by straightforward indexed PostgreSQL aggregation — no caching layer, no background pre-aggregation, no BI platform.

**Constraints**: `POST /api/v1/chat`'s request/response contract MUST remain byte-for-byte unchanged (FR-039). A conversation-recording failure MUST NOT turn an otherwise-successful chat answer into an error (FR-003) — enforced by writing `ConversationRecord` on a `SAVEPOINT` nested inside the request's existing transaction, so only that savepoint (never the outer transaction) rolls back on failure; the row's own durability still depends on the outer transaction's normal commit, exactly like every other write in the request — never a second session, connection, queue, or background worker. The public reference tenant MUST resolve fail-closed only (exists and active; no fallback tenant; no auto-creation; never derived from request content) and a resolution failure MUST likewise never affect the chat response, only whether that request's conversation gets recorded (research.md §4). Every new admin capability MUST derive tenant context exclusively from the authenticated administrator's session (FR-034). Conversation listing MUST be server-bounded regardless of client input (FR-019). Analytics date ranges MUST default to a bounded window, not unbounded history (FR-024).

**Scale/Scope**: Five new authenticated admin endpoints across two new router files; five new application-layer modules (`resolve_public_tenant`, `record_conversation`, `list_conversations`, `get_conversation`, `conversation_analytics`); one new table with four indexes; small, additive extensions to `AskQuestionResult` and `BudgetCheckResult` to surface data `ask_question()` already computes internally but currently discards; one new configuration setting (the public reference tenant's slug). No new external dependency, no new background worker, no retention-cleanup scheduler.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v4.0.0.

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default (NON-NEGOTIABLE) | **PASS** | No new secrets; tenant context server-derived throughout; the public reference tenant is resolved from server configuration, never from client input. |
| II. Multi-Tenant Isolation by Default (NON-NEGOTIABLE) | **PASS** | `ConversationRecord.tenant_id` is set exactly once, server-side, at write time, via `resolve_public_tenant()` — exists-and-active only, no fallback to any other tenant, no auto-creation, never influenced by request content (research.md §4). Every new admin route requires `get_current_administrator` + `get_current_tenant`; cross-tenant attempts on all five new routes are mandatory-tested (spec Testing requirements, US6). No client-supplied tenant id has any effect on the public `/chat` path or any admin route. |
| III. Secure RAG | **PASS** | No change to retrieval, grounding, or prompt assembly; conversation recording is a pure read of `ask_question()`'s already-computed result, after the answer is decided. |
| IV. Secure Document Ingestion | **N/A** | No ingestion code touched. |
| V. LLM Provider Neutrality | **PASS** | No LLM-provider code touched; `provider_name`/`provider_model` are recorded as opaque strings already produced by the existing provider abstraction, never branched on. |
| VI. Embedding Provider Neutrality | **N/A** | No embedding-provider code touched. |
| VII. Provider and Cloud Neutrality | **PASS** | Storage stays PostgreSQL-only; no analytics/observability platform introduced (explicit non-goal). |
| VIII. API Security | **PASS** | All five new routes resolve auth/tenant via `Depends()` before any body executes; errors stay generic (`NotFoundAppError`, no new error type needed for cross-tenant denial). |
| IX. Privacy and Logging | **PASS** | Conversation records deliberately exclude IP, fingerprinting, cookies, raw tokens, full headers, and raw provider exception text (FR-011/012/009); a recording failure is logged without question/answer content (FR-004/038). |
| X. Cost Safety (NON-NEGOTIABLE) | **PASS** | No new public cost surface: conversation recording is a same-transaction DB write triggered only by requests that already passed every existing cost/abuse gate (rate limit, budget, kill switch, concurrency) and reached an outcome — rejected/throttled requests are explicitly excluded (FR-001a), so this cannot become a new anonymous-write amplification vector. |
| XI. Testing Discipline (NON-NEGOTIABLE) | **PASS** | Cross-tenant isolation tests mandatory for all five new routes; a dedicated test proves a conversation-recording failure never prevents the visitor's answer from being returned (SC-008); provider fakes remain the only providers any test exercises. |
| XII. Engineering Quality | **PASS** | One new table, five small application-layer modules mirroring the existing per-use-case pattern (`upload_document.py`, `delete_document.py`, etc.), including a dedicated `resolve_public_tenant()` isolated specifically for independent unit testing of its fail-closed rules; `AskQuestionResult`/`BudgetCheckResult` extended additively, not restructured. |
| XIII. Simplicity for MVP | **PASS** | No BI infrastructure, no LLM-based topic classification, no background worker, no caching layer, no cursor-pagination complexity (plain `limit`/`offset`, the simplest mechanism that satisfies bounded pagination). `UsageRecord` is left untouched rather than retrofitted with a speculative `tenant_id` backfill across pre-tenant-era history. |
| XIV. Approved MVP Technology Stack | **PASS** | No new technology; `percentile_cont`/`GROUP BY` are native PostgreSQL, already the project's database. |

**Gate result**: PASS. No Complexity Tracking entries anticipated.

**Post-Phase-1 re-check**: unchanged — PASS. The two research decisions with the most structural weight — the `SAVEPOINT`-isolated recording write (§3) and snapshotting usage fields on `ConversationRecord` instead of retrofitting `UsageRecord` (§2) — both reduce risk and complexity relative to their alternatives rather than introducing any.

## Project Structure

### Documentation (this feature)

```text
specs/011-conversations-analytics/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/shiruno/
├── persistence/
│   └── models.py                  # + ConversationRecord, ConversationOutcome,
│                                   #   FailureCategory enums
├── api/
│   ├── schemas.py                  # + ConversationSummary, ConversationDetail,
│   │                                #   ConversationListResponse, AnalyticsSummaryResponse,
│   │                                #   QuestionFrequencyItem, etc.
│   └── routers/
│       ├── chat.py                 # + end-to-end latency measurement,
│       │                            #   record_conversation() call (SAVEPOINT-isolated)
│       ├── conversations.py        # NEW — GET /admin/conversations,
│       │                            #   GET /admin/conversations/{id}
│       └── analytics.py            # NEW — GET /admin/analytics/summary,
│                                    #   GET /admin/analytics/knowledge-gaps,
│                                    #   GET /admin/analytics/questions
├── application/
│   ├── ask_question.py             # AskQuestionResult: + provider_name, provider_model,
│   │                                #   input_tokens, output_tokens, provider_metrics,
│   │                                #   failure_category (all optional, additive)
│   ├── resolve_public_tenant.py    # NEW — fail-closed lookup only: exists +
│   │                                #   active, no fallback, no auto-create
│   ├── record_conversation.py      # NEW — calls resolve_public_tenant(); if a
│   │                                #   tenant resolves, snapshots the result inside
│   │                                #   a SAVEPOINT; if not, logs and returns (no
│   │                                #   record possible — no tenant to attribute it to)
│   ├── list_conversations.py       # NEW — tenant-scoped, paginated, filtered list
│   ├── get_conversation.py         # NEW — tenant-scoped single-record fetch
│   └── conversation_analytics.py   # NEW — summary / knowledge-gaps / common-questions
├── domain/
│   └── question_normalization.py   # NEW — deterministic lowercase/whitespace
│                                    #   normalization, shared by recording and analytics
├── infra/
│   └── budget.py                   # BudgetCheckResult: + reason ("kill_switch" |
│                                    #   "budget_exceeded"), additive
└── config.py                       # + PUBLIC_CHAT_TENANT_SLUG (default "albertos"),
                                     #   + CONVERSATION_LIST_DEFAULT/MAX_PAGE_SIZE,
                                     #   + ANALYTICS_DEFAULT_LOOKBACK_DAYS

alembic/versions/
└── <rev>_add_conversation_records.py   # NEW — creates conversation_records + indexes

tests/
├── contract/
│   ├── test_chat_conversation_recording.py   # NEW — every outcome persists correctly;
│   │                                          #   recording failure doesn't break /chat;
│   │                                          #   missing/inactive public tenant doesn't
│   │                                          #   change the ChatResponse either
│   ├── test_conversations_list.py             # NEW
│   ├── test_conversations_detail.py           # NEW — includes historical-snapshot
│   │                                          #   immutability: replacing/deleting the
│   │                                          #   cited document, or a differently-
│   │                                          #   configured provider/model on a second
│   │                                          #   recorded conversation, never changes
│   │                                          #   an already-recorded row (research.md §2a)
│   ├── test_analytics_summary.py              # NEW — includes a multi-provider-in-range
│   │                                          #   case proving the provider breakdown
│   │                                          #   reflects each row's own snapshot
│   ├── test_analytics_knowledge_gaps.py       # NEW
│   ├── test_analytics_questions.py            # NEW
│   └── test_admin_authorization_fail_closed.py # extended: 5 new routes
├── unit/
│   ├── test_question_normalization.py         # NEW
│   └── test_resolve_public_tenant.py          # NEW — exists+active, missing, inactive,
│                                                #   no fallback among multiple tenants,
│                                                #   no tenant is ever auto-created
└── integration/
    └── test_conversation_records_migration.py # NEW — upgrade/downgrade
```

**Structure Decision**: Single existing backend project (`src/shiruno/`) — no new project, app, or package. Two new router files mirror the existing one-resource-per-file pattern (`documents.py`, `admin.py`); both share `admin.py`'s already-established `/api/v1/admin` prefix, which its own docstring names as the namespace future admin features build under. Five new application-layer modules mirror the existing one-use-case-per-file convention. `ask_question.py` and `infra/budget.py` are extended additively (new optional fields/return attributes) rather than restructured, so every existing caller and test continues to compile and pass unmodified.

## Complexity Tracking

*No entries.* No principle is violated; the design's two most consequential
decisions (SAVEPOINT-isolated recording, snapshot-not-backfill for usage
data) were chosen specifically because they are simpler and lower-risk than
their respective alternatives (letting a recording failure risk the
transaction; retrofitting and backfilling `tenant_id` across `UsageRecord`'s
full pre-tenant history).
