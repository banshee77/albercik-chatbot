# Implementation Plan: Admin Platform Foundation & Tenant Boundary

**Branch**: `009-admin-platform-foundation` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-admin-platform-foundation/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Introduce `Tenant` as a first-class, server-enforced security boundary:
Albertos becomes tenant #1 (bootstrapped by an Alembic migration, not
ad-hoc SQL); every `Administrator` gains a required `tenant_id`; a new
`get_current_tenant` FastAPI dependency, layered on the existing
`get_current_administrator`, derives tenant context exclusively from the
authenticated session; a minimal `GET /api/v1/admin/me` endpoint proves
that boundary; and the existing admin document-management endpoints
become tenant-scoped (`KnowledgeDocument.tenant_id`) so cross-tenant
isolation is proven against real, already-shipped functionality rather
than a synthetic test resource. The public `/api/v1/chat` contract and
existing document endpoint paths/shapes are untouched. This directly
implements the multi-tenant isolation posture the constitution's Principle
II now mandates (amended 2026-08-19, v3.1.1 → v4.0.0, specifically to
permit and require this feature).

## Technical Context

**Language/Version**: Python 3.14 (existing)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic /
`pydantic-settings`, PyJWT, `bcrypt`, `argparse` (stdlib, for the CLI) —
all already in use; no new dependency is introduced by this feature.

**Storage**: PostgreSQL + `pgvector` (existing `db`/`db-test` Docker
Compose services) — two additive Alembic migrations (data-model.md).

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`),
`httpx.AsyncClient`/`ASGITransport` against `create_app(...)` with fake
LLM/embedding providers, real Postgres+`pgvector` (`db-test`) for
integration tests — all existing conventions (`tests/conftest.py`,
`tests/fixtures/admin.py`), extended, not replaced.

**Target Platform**: Linux server (Docker), unchanged.

**Project Type**: Single backend web service (existing `src/shiruno/`
layout) — no new project/app is created.

**Performance Goals**: None beyond preserving existing behavior — this
feature adds one authenticated GET endpoint and a `tenant_id` filter to
already-authenticated, low-volume admin document operations; no
performance target changes (spec has none).

**Constraints**: Public `/api/v1/chat` contract and behavior MUST remain
byte-for-byte unchanged (FR-021, FR-022). Tenant context MUST be
server-derived and fail closed (constitution Principle II, NON-NEGOTIABLE).
No client-supplied tenant identifier (body, query, header) may influence
tenant-scoped data access (FR-013).

**Scale/Scope**: Two entities added/changed (`Tenant` new;
`Administrator`, `KnowledgeDocument` gain `tenant_id`), one new router
(`api/routers/admin.py`, one route), one new dependency
(`get_current_tenant`), two CLI subcommand changes, two Alembic
migrations. Two tenants exist for testing (Albertos + one test-only
tenant); one tenant (Albertos) holds real production data.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v4.0.0 (amended
2026-08-19, same day, specifically to unblock this feature).

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default (NON-NEGOTIABLE) | **PASS** | Tenant context resolved server-side only (`get_current_tenant`); no LLM involvement in authz; no new secrets introduced. |
| II. Multi-Tenant Isolation by Default (NON-NEGOTIABLE) | **PASS** | This feature *is* the implementation of this principle: `Tenant` as first-class boundary, server-derived context (`get_current_administrator` → `get_current_tenant`), client-supplied tenant ids ignored, fail-closed on missing/invalid/inactive, no existence-leaking 404s (documents), mandatory cross-tenant automated tests (spec Testing Requirements #10, #13; quickstart.md §5, §7). Rule 10 respected: `UsageRecord`/`RateLimitWindow` are NOT retroactively tenant-owned (research.md §10). Rule 11 respected: no platform super-admin capability introduced. |
| III. Secure RAG | **N/A** | This feature does not touch retrieval, prompting, or grounding logic (research.md §3 — public chat path untouched). |
| IV. Secure Document Ingestion | **PASS** | Upload validation (type/size) unchanged; only ownership stamping is added to an already-validated path. |
| V. LLM Provider Neutrality | **N/A** | No LLM-provider code touched. |
| VI. Embedding Provider Neutrality | **N/A** | No embedding-provider code touched. |
| VII. Provider and Cloud Neutrality | **PASS** | No cloud-specific dependency introduced. |
| VIII. API Security | **PASS** | Authn/authz (`get_current_administrator`, `get_current_tenant`) resolved via `Depends()` before any route body runs, per existing pattern; error responses stay generic (`api/errors.py`). |
| IX. Privacy and Logging | **PASS** | Audit logging extended with `tenant_id` only (research.md §7); no credential/token logging introduced. |
| X. Cost Safety (NON-NEGOTIABLE) | **N/A** | No change to `/api/v1/chat`, rate limiting, budget, or kill-switch logic. |
| XI. Testing Discipline (NON-NEGOTIABLE) | **PASS** | Cross-tenant isolation tests are mandatory and planned (spec Testing Requirements, quickstart.md); existing RBAC/security test suite must remain green (Testing Requirement #17, #22). |
| XII. Engineering Quality | **PASS** | Two small composable dependencies (`get_current_administrator`, `get_current_tenant`); no new framework/abstraction layer. |
| XIII. Simplicity for MVP | **PASS** | No synthetic "test resource" table (research.md §3 — reused `KnowledgeDocument` instead); no tenant deactivation UI/API built speculatively (Clarifications, 2026-08-19); `UsageRecord`/`RateLimitWindow` left alone. |
| XIV. Approved MVP Technology Stack | **PASS** | Python, FastAPI, PostgreSQL, `pgvector`, SQLAlchemy, Alembic, Docker Compose, `uv` — no new technology. |

**Gate result**: PASS. No Complexity Tracking entries required.

**Post-Phase-1 re-check** (after `research.md`, `data-model.md`,
`contracts/`, `quickstart.md` were produced): unchanged — PASS. The one
design decision made during Phase 0/1 that was not pre-determined by the
spec (tenant-scoping `KnowledgeDocument` now rather than deferring it,
research.md §3) strengthens Principle II compliance rather than weakening
it, and stays within Principle XIII by reusing an existing table instead
of adding a new one. No gate that passed at Phase 0 was put at risk by the
detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
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
│   └── models.py            # + Tenant, TenantStatus; Administrator/KnowledgeDocument + tenant_id
├── api/
│   ├── deps.py               # + get_current_tenant
│   ├── schemas.py            # + AdministratorOut, TenantOut, AdminMeResponse
│   └── routers/
│       ├── admin.py          # NEW — GET /api/v1/admin/me
│       ├── auth.py           # unchanged path/contract
│       └── documents.py      # tenant-scoped upload/list/delete
├── application/
│   ├── upload_document.py    # + tenant_id param, stamps ownership
│   ├── list_documents.py     # + tenant_id filter
│   └── delete_document.py    # + tenant_id ownership check
├── infra/
│   └── audit.py              # + optional tenant_id param
├── cli.py                    # NEW create-tenant; create-admin + --tenant
└── main.py                   # registers admin.router

alembic/versions/
├── <rev>_add_tenants_table_and_administrator_tenant_id.py   # NEW
└── <rev>_add_knowledge_document_tenant_id.py                 # NEW

tests/
├── contract/
│   ├── test_admin_me.py                 # NEW
│   └── test_documents_auth.py           # extended: cross-tenant cases
├── unit/
│   └── test_cli.py                      # extended: create-tenant, --tenant
├── integration/
│   └── test_tenant_migration.py         # NEW — alembic upgrade/downgrade + backfill
└── fixtures/
    └── admin.py                          # extended: seed_tenant / tenant-aware seeding
```

**Structure Decision**: Single existing backend project
(`src/shiruno/`) — no new top-level project, app, or package. This
feature extends the existing layered structure (API → application →
persistence, per the constitution's Separation of Concerns) exactly where
each concern already lives: a new router alongside `auth.py`/
`documents.py`, a new dependency alongside `get_current_administrator`, a
new model alongside `Administrator`/`KnowledgeDocument`, and CLI additions
alongside `create-admin`. No `apps/admin` or other future-boundary
directory (per `docs/architecture.md`'s "target direction, aspirational"
tree) is created now — that remains out of scope until the actual React
admin frontend work begins.

## Complexity Tracking

*No entries — Constitution Check gate passed with no violations
requiring justification.*
