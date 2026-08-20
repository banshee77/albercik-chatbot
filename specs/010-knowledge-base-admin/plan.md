# Implementation Plan: Knowledge Base Administration

**Branch**: `010-knowledge-base-admin` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-knowledge-base-admin/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Extend the existing, already tenant-scoped `/api/v1/documents` endpoints (Feature 009) with four new operations — single-document detail, safe replace, honest re-index, and tenant-scoped knowledge health — rather than introducing a parallel `/api/v1/admin/knowledge/...` API, per the spec's explicit preference for backward-compatible extension. Replace is implemented as "new successor document, retire predecessor only on success," made race-safe with a PostgreSQL row-level lock (`SELECT ... FOR UPDATE`) on the predecessor acquired only for the brief final activate/retire step — never held across the slower validation/embedding work — so a failed replacement never takes working knowledge offline, and exactly one of two concurrent replacements for the same document can ever win. Re-index is implemented as "regenerate embeddings for a document's already-persisted chunk text using the current embedding provider" — a genuine, non-fabricated operation given that full original source text is not currently retained — and a failed re-index never regresses a document that was already ready. Retrieval gains an explicit `status == ready` filter (on top of the existing `deleted_at IS NULL` filter) so lifecycle-state safety is enforced structurally by the query, not merely by ingestion-code discipline. Four new nullable/derived columns are added to `KnowledgeDocument` via two additive, reversible Alembic migrations with deterministic backfill.

## Technical Context

**Language/Version**: Python 3.14 (existing, unchanged)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, `pgvector`, Pydantic — all already in use; no new dependency introduced.

**Storage**: PostgreSQL + `pgvector` (existing `db`/`db-test` Compose services) — two additive Alembic migrations adding columns to the existing `knowledge_documents` table; no new table.

**Testing**: `pytest` + `pytest-asyncio`, `httpx.AsyncClient` against `create_app(...)` with fake LLM/embedding providers, real Postgres+`pgvector` for integration tests — existing conventions (`tests/conftest.py`, `tests/fixtures/admin.py`) extended, not replaced.

**Target Platform**: Linux server (Docker), unchanged.

**Project Type**: Single existing backend web service (`src/shiruno/`) — no new project/app.

**Performance Goals**: None beyond preserving existing behavior; ingestion remains synchronous within one HTTP request, exactly as upload already is today — no background job queue is introduced (constitution Principle XIII).

**Constraints**: Public `/api/v1/chat` contract and RAG configuration (Top-K, similarity threshold, embedding defaults, answerability prompt) MUST remain byte-for-byte unchanged (FR-037, FR-038). Every knowledge operation MUST derive tenant context server-side only (FR-031). A failed replace or re-index MUST NOT leave the tenant with less working knowledge than it had before the attempt (SC-004, SC-005). Two concurrent replace requests for the same source document MUST NOT both successfully activate a successor — safe replacement is a data-integrity property of the operation itself, enforced via PostgreSQL row-level locking, not an optional hardening step.

**Scale/Scope**: Four new HTTP operations on the existing `/api/v1/documents` resource, four new columns on `KnowledgeDocument`, one new query filter, two new application-layer modules (`replace_document`, `reindex_document`) plus one new `knowledge_health` module, one shared ingestion helper extracted from the existing upload path. No new tables, no new external dependency, no new CLI surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v4.0.0.

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default (NON-NEGOTIABLE) | **PASS** | No new secrets; tenant context server-derived throughout, matching Feature 009's established pattern. |
| II. Multi-Tenant Isolation by Default (NON-NEGOTIABLE) | **PASS** | Every new operation (detail, replace, delete — unchanged, reindex, health) requires `get_current_administrator` + `get_current_tenant`; cross-tenant attempts on all four new operations are mandatory-tested (spec Testing Requirements #14, #16, #18, #20); no client-supplied tenant id has any effect. |
| III. Secure RAG | **PASS** | Retrieval gains a structural `status == ready` filter, strengthening (not weakening) the guarantee that only genuinely ready, non-deleted content is ever retrieved; no change to how retrieved content is treated relative to instructions. |
| IV. Secure Document Ingestion | **PASS** | Replace and re-index reuse the exact same validation/size/content-safety path as upload (shared ingestion helper) — no weakening, no new upload surface bypassing existing checks. |
| V. LLM Provider Neutrality | **N/A** | No LLM-provider code touched. |
| VI. Embedding Provider Neutrality | **PASS** | Re-index explicitly reuses the existing `EmbeddingProvider` Protocol via the same composition-root-selected instance — no new embedding code path, no client control over provider/model. |
| VII. Provider and Cloud Neutrality | **PASS** | No object storage or cloud-specific service introduced (spec item 16 explicitly forbids this without a spec amendment); storage stays PostgreSQL-only. |
| VIII. API Security | **PASS** | All four new routes resolve auth/tenant via `Depends()` before any body executes, per the existing pattern; errors stay generic (`NotFoundAppError`/`UnauthorizedError`, no new error type needed). |
| IX. Privacy and Logging | **PASS** | `safe_error_message` is explicitly sanitized (FR-013); audit log gains `document_replace`/`document_reindex` actions using the existing structurally-safe `log_audit_event` (no new parameter that could carry content/secrets). |
| X. Cost Safety (NON-NEGOTIABLE) | **N/A** | No change to `/api/v1/chat`, rate limiting, budget, or kill-switch logic; re-index/replace embedding calls are administrator-authenticated, not public-endpoint-triggered, so Principle X's public-anonymous-cost concern does not apply — no new public cost surface is created. |
| XI. Testing Discipline (NON-NEGOTIABLE) | **PASS** | Cross-tenant isolation tests mandatory for every new operation (spec Testing Requirements); "failed processing leaves no active chunks," "failed replace/reindex leaves prior knowledge intact," and "concurrent replace cannot produce two active successors" are all directly testable against the new `status == ready` retrieval filter and the row-locked replace path (research.md §3). |
| XII. Engineering Quality | **PASS** | Shared ingestion logic extracted once (`_ingest_content`) rather than duplicated across upload/replace; no new abstraction beyond what removes real duplication. Row-level locking uses SQLAlchemy's existing `with_for_update()` on the already-open per-request session — no new concurrency primitive introduced. |
| XIII. Simplicity for MVP | **PASS** | No new table (`KnowledgeDocument` extended in place); no background job/queue; no versioning platform; no distributed lock — replace's race-safety uses a plain PostgreSQL row lock on the one row already central to the operation, the simplest mechanism that actually delivers the required data-integrity guarantee (research.md §3, alternatives considered). |
| XIV. Approved MVP Technology Stack | **PASS** | No new technology. |

**Gate result**: PASS. No Complexity Tracking entries remain — the one candidate item identified during initial planning (concurrent-replace races) was corrected into the design itself (research.md §3) rather than accepted as a limitation, so there is nothing left to justify as an exception.

**Post-Phase-1 re-check**: unchanged — PASS. Both post-research additions — the `status == ready` retrieval filter (§1) and the row-locked replace path (§3) — strengthen Principle II/III/XI compliance rather than introducing risk, and neither required a new dependency, abstraction, or infrastructure component.

## Project Structure

### Documentation (this feature)

```text
specs/010-knowledge-base-admin/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/shiruno/
├── persistence/
│   ├── models.py                # KnowledgeDocument + updated_at, indexed_at,
│   │                             #   safe_error_message, replaces_document_id
│   └── repositories.py          # search_similar_chunks: + status == ready filter
├── api/
│   ├── schemas.py                # DocumentSummary: + updated_at, content_type,
│   │                             #   indexed_at, error_message; + KnowledgeHealthResponse
│   └── routers/
│       └── documents.py          # + GET /documents/health, GET /documents/{id},
│                                  #   POST /documents/{id}/replace,
│                                  #   POST /documents/{id}/reindex
├── application/
│   ├── _ingest_content.py        # NEW — shared chunk/embed/persist helper,
│   │                             #   extracted from upload_document.py
│   ├── upload_document.py        # refactored to call _ingest_content
│   ├── replace_document.py       # NEW
│   ├── reindex_document.py       # NEW
│   ├── get_document.py           # NEW — single tenant-scoped fetch
│   └── knowledge_health.py       # NEW
├── infra/
│   └── audit.py                  # AuditAction: + "document_replace", "document_reindex"
└── main.py                       # unchanged (documents.router already registered)

alembic/versions/
├── <rev>_add_knowledge_document_lifecycle_metadata.py   # NEW
└── <rev>_add_knowledge_document_replaces_document_id.py # NEW

tests/
├── contract/
│   ├── test_documents_lifecycle.py      # extended: detail, health, empty state
│   ├── test_documents_replace.py        # NEW
│   ├── test_documents_reindex.py        # NEW
│   └── test_documents_auth.py           # extended: cross-tenant replace/reindex/health
├── unit/
│   └── test_retrieval.py / test_chunking.py  # extended: status filter coverage
└── integration/
    ├── test_knowledge_document_migration.py  # NEW — upgrade/downgrade + backfill
    └── test_replace_concurrency.py           # NEW — two racing replace requests for
                                               #   the same document; exactly one wins,
                                               #   the loser never becomes active
                                               #   retrieval knowledge (research.md §3)
```

**Structure Decision**: Single existing backend project (`src/shiruno/`) — no new project, app, or package. New capability is added exactly where the equivalent existing capability already lives: new routes alongside the existing three in `api/routers/documents.py` (not a new router — the resource is still "documents," just with more operations), new application-layer modules alongside `upload_document.py`/`list_documents.py`/`delete_document.py`, and a schema/query extension rather than a new table. This directly satisfies the spec's "prefer backward-compatible extension over duplicate parallel APIs" requirement (FR-031 context, spec item 11) and mirrors Feature 009's own precedent of extending in place rather than introducing a new namespace prematurely.

## Complexity Tracking

*No entries.* The one candidate item from initial planning — concurrent
replace requests racing on the same source document — was resolved by
correcting the replace design itself (PostgreSQL row-level locking,
research.md §3) rather than accepted as a documented limitation. Safe
replacement under concurrent requests is a data-integrity property of the
replace operation, not an optional hardening step, so there is nothing
here requiring justification as an exception to a constitution principle.
