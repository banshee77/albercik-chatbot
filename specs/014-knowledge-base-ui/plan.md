# Implementation Plan: Knowledge Base UI

**Branch**: `014-knowledge-base-ui` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-knowledge-base-ui/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Replace the Feature 013 `/app/knowledge` placeholder with a functional
knowledge-management screen — health summary, document list, upload,
inline document detail, re-index, replace, and delete — consuming the
existing Feature 010 `/api/v1/documents*` API exactly as it exists today
(research.md R1: no new endpoint or database entity). Built as one new
`apps/admin/src/routes/KnowledgePage.tsx` composing a small set of new
`apps/admin/src/components/knowledge/*` components, backed by one new
`apps/admin/src/api/knowledge.ts` module on top of Feature 013's existing
centralized `api/client.ts` — extended in place with two small, additive
fixes (multipart `FormData` bodies; `204 No Content` handling,
research.md R2) that this feature is the first caller to need. No new
frontend dependency, no new route, no new backend endpoint or database
entity — the one backend change this feature does make is additive and
narrow: Feature 013's CORS `allow_methods` list never included `DELETE`
(it only ever needed `GET`/`POST`), which silently blocked the browser's
preflight for Delete until live-QA caught it (research.md R12).

## Technical Context

**Language/Version**: TypeScript (frontend, existing `apps/admin/`);
Python 3.14 (backend — one small, additive one-line CORS fix, research.md
R12; no new endpoint, model, or migration)

**Primary Dependencies**: React, `react-router` (both existing in
`apps/admin/`, already approved under constitution Principle XIV) — no new
frontend dependency introduced by this feature

**Storage**: N/A — no new database entity; this feature reads/writes the
existing tenant-scoped `KnowledgeDocument`/`DocumentChunk` tables
exclusively through Feature 010's existing endpoints (research.md R1)

**Testing**: Vitest + `@testing-library/react` + `@testing-library/user-event`
(existing `apps/admin/` harness, unchanged); backend regression suite
(existing, plus one extended assertion in the pre-existing CORS test,
research.md R12)

**Target Platform**: Modern evergreen browsers (same as Feature 013;
native `<dialog>` — research.md R5 — is supported in every one)

**Project Type**: Web application — almost entirely a frontend change to
`apps/admin/`; `src/shiruno/` (backend) has one one-line, additive CORS
fix (research.md R12) and is otherwise unmodified

**Performance Goals**: No new numeric target — this feature's requests are
exactly Feature 010's existing synchronous endpoints; standard SPA
responsiveness (interactive within a normal page-load budget) is
sufficient, matching Feature 013's own Technical Context

**Constraints**: No ad-hoc `fetch()` outside the centralized `api/`
boundary (FR-030); no client-supplied tenant identifier on any request
(FR-031); no raw backend exception text, chunk content, embedding vector,
or internal provider/tenant-ID ever rendered (FR-002, FR-013, FR-015);
frontend remains not a security boundary — every constraint already
enforced server-side (tenant isolation, fail-closed auth, per-document
lifecycle rules) remains enforced there, unchanged

**Scale/Scope**: One route (`/app/knowledge`, replacing a placeholder), 7
new small components under `apps/admin/src/components/knowledge/`, 1 new
API module (`knowledge.ts`), 2 additive extensions to the existing
`client.ts`, 1 one-line additive CORS fix (research.md R12), 0 new backend
endpoints, 0 new database entities, 0 new frontend dependencies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default | PASS | No new trust decision made client-side; the bearer token continues to be handled exactly as Feature 013 established (in-memory only, research.md R2 only touches how the *body* is encoded, not token handling). |
| II. Multi-Tenant Isolation | PASS | Every `knowledge.ts` function relies exclusively on the existing bearer-token-derived tenant context (FR-031); no function accepts or constructs a tenant identifier (research.md R3). |
| III. Secure RAG | N/A | This feature touches no retrieval/generation/prompting path — it manages documents, not answers. |
| IV. Secure Document Ingestion | PASS | Upload/replace continue to route through Feature 010's existing validated `_ingest_content` path unchanged (research.md R1); this feature adds no new ingestion code, and its one client-side pre-check (file extension, research.md R7) is explicitly non-authoritative. |
| V. LLM Provider Neutrality | N/A | No LLM code touched. |
| VI. Embedding Provider Neutrality | N/A | No embedding code touched — re-index continues to call the existing `EmbeddingProvider` interface server-side, unchanged. |
| VII. Provider and Cloud Neutrality | PASS | No new cloud-specific dependency; frontend build/hosting posture is unchanged from Feature 013. |
| VIII. API Security | PASS | No new endpoint, so no new authn/authz ordering to review; existing `get_current_administrator`/`get_current_tenant` dependency chain on every `/documents*` route is untouched. |
| IX. Privacy and Logging | PASS | No raw backend error, chunk, or embedding is ever rendered (FR-002, FR-013, FR-015); nothing new is logged — this feature adds no new logging code. |
| X. Cost Safety | N/A | Re-index invokes the same local embedding provider Feature 010 already calls on upload — no paid-provider or new cost-exposure path is added by this feature. |
| XI. Testing Discipline | PASS | research.md R10 — every Knowledge component test mocks `api/knowledge.ts` at the module boundary; no real backend/network/Ollama/Phoenix dependency, mirroring Feature 013's own R10. |
| XII. Engineering Quality | PASS | `knowledge.ts` mirrors the existing `auth.ts`/`admin.ts` shape exactly (research.md R3); page-local state stays in `KnowledgePage.tsx` (research.md R8) rather than introducing a new state-management layer. |
| XIII. Simplicity for MVP | PASS | No React Query/TanStack Query, no modal library, no new routing surface (research.md R4, R5, R8) — each explicitly considered and rejected as more than a reload-after-mutation, native-`<dialog>` MVP needs. |
| XIV. Approved MVP Technology Stack | PASS | Uses exactly the stack Feature 013's constitution amendment (v4.2.0) already approved for `apps/*` — TypeScript, React, Vite, React Router. No new technology, so no further amendment is needed. |

**No Constitution Check items require resolution or amendment** — every
applicable principle passes without a new gate to clear, unlike Feature
013 (which needed the v4.2.0 stack amendment before it could proceed).
Safe to proceed directly to `/speckit-tasks` once this plan is approved.

## Project Structure

### Documentation (this feature)

```text
specs/014-knowledge-base-ui/
├── plan.md               # This file (/speckit-plan command output)
├── research.md            # Phase 0 output (/speckit-plan command)
├── data-model.md          # Phase 1 output (/speckit-plan command)
├── quickstart.md          # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md    # Spec-quality checklist (/speckit-specify, /speckit-clarify)
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new backend API
surface at all. The authoritative contract it consumes is already
documented at
`specs/010-knowledge-base-admin/contracts/documents-api-delta.md`; this
plan's research.md R1 cross-checks that contract against the current
`api/schemas.py`/`documents.py` implementation rather than duplicating it.

### Source Code (repository root)

Extends the existing `apps/admin/` frontend from Feature 013 — no new
top-level directory, no backend directory touched.

```text
apps/admin/
├── src/
│   ├── api/
│   │   ├── client.ts              # EXTENDED — FormData body support, 204 handling (research.md R2)
│   │   ├── knowledge.ts           # NEW — listDocuments, getKnowledgeHealth, getDocument,
│   │   │                          #       uploadDocument, replaceDocument, reindexDocument,
│   │   │                          #       deleteDocument (research.md R3)
│   │   ├── auth.ts                # unchanged (Feature 013)
│   │   └── admin.ts               # unchanged (Feature 013)
│   ├── routes/
│   │   ├── KnowledgePage.tsx      # NEW — replaces KnowledgePlaceholder.tsx; owns page state
│   │   │                          #       (research.md R8, R9); KnowledgePlaceholder.tsx deleted
│   │   ├── LoginPage.tsx          # unchanged
│   │   ├── AppHome.tsx            # unchanged
│   │   ├── ProtectedLayout.tsx    # unchanged
│   │   ├── ConversationsPlaceholder.tsx  # unchanged (Feature 015)
│   │   └── AnalyticsPlaceholder.tsx      # unchanged (Feature 016)
│   ├── components/
│   │   ├── knowledge/             # NEW subfolder (research.md R9)
│   │   │   ├── HealthSummary.tsx
│   │   │   ├── DocumentTable.tsx
│   │   │   ├── DocumentDetailPanel.tsx
│   │   │   ├── UploadControl.tsx
│   │   │   ├── ReplaceDialog.tsx
│   │   │   ├── DeleteDialog.tsx
│   │   │   └── StatusBadge.tsx
│   │   ├── Header.tsx             # unchanged (Feature 013)
│   │   ├── Nav.tsx                # unchanged (Feature 013)
│   │   ├── LoadingState.tsx       # unchanged (Feature 013) — reused inside knowledge/ components
│   │   └── ErrorMessage.tsx       # unchanged (Feature 013) — reused inside knowledge/ components
│   └── routeConfig.tsx            # EXTENDED — 'knowledge' child now renders KnowledgePage
└── tests/
    ├── knowledge-health.test.tsx       # NEW
    ├── knowledge-list.test.tsx         # NEW
    ├── knowledge-upload.test.tsx       # NEW
    ├── knowledge-detail.test.tsx       # NEW
    ├── knowledge-reindex.test.tsx      # NEW
    ├── knowledge-replace.test.tsx      # NEW
    ├── knowledge-delete.test.tsx       # NEW
    ├── knowledge-session-expiration.test.tsx  # NEW
    ├── testUtils.tsx                   # EXTENDED — adds renderKnowledgePage() (research.md R10)
    └── (existing Feature 013 test files unchanged)

src/shiruno/                       # NOT touched by this feature
tests/                             # NOT touched by this feature (backend)
```

**Structure Decision**: Pure extension of Feature 013's existing
`apps/admin/` layout — one new route file, one new API module, one new
component subfolder, and two additive edits to already-existing files
(`client.ts`, `routeConfig.tsx`). No existing backend file is touched; no
existing frontend file outside those two is touched.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Not applicable — every Constitution Check item passes without deviation
(see table above); III, V, VI, and X are marked N/A because this
feature's scope genuinely doesn't touch their subject matter (retrieval/
generation, LLM/embedding provider code, paid-provider cost exposure),
not because a violation was waived.
