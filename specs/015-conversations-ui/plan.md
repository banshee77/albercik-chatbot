# Implementation Plan: Conversations UI

**Branch**: `015-conversations-ui` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-conversations-ui/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Replace the Feature 013 `/app/conversations` placeholder with a functional,
read-only conversation-review screen — search, outcome filter, date range,
pagination, and an inline conversation-detail panel showing question,
answer, outcome, historical grounded sources, and safe operational
metadata — consuming the existing Feature 011
`GET /api/v1/admin/conversations` and
`GET /api/v1/admin/conversations/{id}` endpoints exactly as they exist
today (research.md R1: no new endpoint, no backend change at all). Built
as one new `apps/admin/src/routes/ConversationsPage.tsx` composing a small
set of new `apps/admin/src/components/conversations/*` components, backed
by one new `apps/admin/src/api/conversations.ts` module on top of Feature
013's existing centralized `api/client.ts` — unmodified, since every
request here is a plain authenticated `GET` (research.md R2). No new
frontend dependency, no new backend endpoint, no new database entity, and
no `client.ts` change at all — the smallest surface area of the three UI
features shipped so far (013, 014, 015).

## Technical Context

**Language/Version**: TypeScript (frontend, existing `apps/admin/`); no
backend language/version touched — this feature makes no backend change

**Primary Dependencies**: React, `react-router` (both existing in
`apps/admin/`, already approved under constitution Principle XIV) — no new
frontend dependency introduced by this feature

**Storage**: N/A — no new database entity; this feature only reads the
existing tenant-scoped `ConversationRecord` table, exclusively through
Feature 011's existing endpoints (research.md R1)

**Testing**: Vitest + `@testing-library/react` + `@testing-library/user-event`
(existing `apps/admin/` harness, unchanged); backend regression suite
(existing, entirely unmodified — this feature makes no backend change)

**Target Platform**: Modern evergreen browsers (same as Feature 013/014;
`navigator.clipboard.writeText` — research.md R13 — is supported in every
one)

**Project Type**: Web application — entirely a frontend change to
`apps/admin/`; `src/shiruno/` (backend) is not touched at all by this
feature, unlike Feature 014's one-line additive CORS fix

**Performance Goals**: No new numeric target — this feature's requests are
exactly Feature 011's existing synchronous, already-paginated endpoints;
standard SPA responsiveness (interactive within a normal page-load budget)
is sufficient, matching Feature 013's and Feature 014's own Technical
Context

**Constraints**: No ad-hoc `fetch()` outside the centralized `api/`
boundary (FR-039); no client-supplied tenant identifier on any request
(FR-041); no raw backend exception text, `provider_metrics` payload,
trace/embedding/chunk data, or internal tenant ID ever rendered (FR-025,
FR-037); every list/detail request bounded, never unbounded (FR-019);
frontend remains not a security boundary — every constraint already
enforced server-side (tenant isolation, fail-closed 404 on cross-tenant
lookup, immutable point-in-time snapshots) remains enforced there,
unchanged

**Scale/Scope**: One route (`/app/conversations`, replacing a
placeholder), 6 new small components under
`apps/admin/src/components/conversations/`, 1 new hook
(`usePanelFocus.ts`), 1 new API module (`conversations.ts`), 0 changes to
`client.ts`, 0 new backend endpoints, 0 new database entities, 0 new
frontend dependencies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default | PASS | No new trust decision made client-side; the bearer token continues to be handled exactly as Feature 013 established (in-memory only) — this feature adds no token handling of its own. |
| II. Multi-Tenant Isolation | PASS | `listConversations`/`getConversation` (research.md R3) rely exclusively on the existing bearer-token-derived tenant context; `ListConversationsParams` has no field a caller could set to select a tenant (FR-041, data-model.md). |
| III. Secure RAG | N/A | This feature touches no retrieval/generation/prompting path — it displays already-recorded conversations, never generates or re-runs an answer (FR-049). |
| IV. Secure Document Ingestion | N/A | No upload/ingestion path is touched by this feature. |
| V. LLM Provider Neutrality | N/A | No LLM code touched — this feature displays `provider_name`/`provider_model` as opaque strings the backend already normalized; it never calls a provider. |
| VI. Embedding Provider Neutrality | N/A | No embedding code touched. |
| VII. Provider and Cloud Neutrality | PASS | No new cloud-specific dependency; frontend build/hosting posture is unchanged from Feature 013/014. |
| VIII. API Security | PASS | No new endpoint, so no new authn/authz ordering to review; the existing `get_current_administrator`/`get_current_tenant` dependency chain on both `/conversations*` routes is untouched (research.md R1). |
| IX. Privacy and Logging | PASS | Raw `provider_metrics` is structurally excluded from the frontend type (research.md R4, FR-037); question/answer content is never logged, persisted in storage, or sent to third-party analytics (FR-044); nothing new is logged — this feature adds no new logging code. |
| X. Cost Safety | N/A | This feature invokes no LLM/embedding call of its own — it only reads already-recorded outcomes of past calls. |
| XI. Testing Discipline | PASS | research.md R12 — every Conversations component test mocks `api/conversations.ts` at the module boundary; no real backend/network/Ollama/Phoenix dependency, mirroring Feature 013's and Feature 014's own R10. |
| XII. Engineering Quality | PASS | `conversations.ts` mirrors the existing `knowledge.ts`/`admin.ts` shape exactly (research.md R3); page-local state stays in `ConversationsPage.tsx`, matching `KnowledgePage.tsx`'s existing pattern; `outcomeLabel.ts` mirrors the existing, already-reviewed `statusLabel.ts` (research.md R7) rather than inventing a new mapping convention. |
| XIII. Simplicity for MVP | PASS | No React Query/TanStack Query, no debounce utility, no pagination library, no new CSS layout system (research.md R5, R8, R9, R11) — each explicitly considered and rejected as more than an explicit-submit-search, reload-after-filter, inline-panel MVP needs. |
| XIV. Approved MVP Technology Stack | PASS | Uses exactly the stack Feature 013's constitution amendment (v4.2.0) already approved for `apps/*` — TypeScript, React, Vite, React Router. No new technology, so no further amendment is needed. |

**No Constitution Check items require resolution or amendment** — every
applicable principle passes without a new gate to clear, exactly as
Feature 014 concluded. Safe to proceed directly to `/speckit-tasks` once
this plan is approved.

### Post-Design Re-check (after Phase 1)

data-model.md and research.md introduce nothing that changes any row in
the table above: no new entity crosses a security boundary, no new
dependency was added, and the one new hook (`usePanelFocus.ts`, research.md
R6) is a small, focus-only utility with no modal/trust semantics of its
own. Constitution Check **remains PASS** with no new items to resolve.

## Project Structure

### Documentation (this feature)

```text
specs/015-conversations-ui/
├── plan.md               # This file (/speckit-plan command output)
├── research.md            # Phase 0 output (/speckit-plan command)
├── data-model.md          # Phase 1 output (/speckit-plan command)
├── quickstart.md          # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md    # Spec-quality checklist (/speckit-specify, /speckit-clarify)
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new backend API
surface at all (research.md R1). The authoritative contract it consumes is
already documented at
`specs/011-conversations-analytics/contracts/conversations-api.md`; this
plan's research.md cross-checks that contract directly against the current
`src/shiruno/api/routers/conversations.py` and `schemas.py` implementation
rather than duplicating it — the same choice Feature 014 made for its own
(already-existing) Knowledge API contract.

### Source Code (repository root)

Extends the existing `apps/admin/` frontend from Feature 013/014 — no new
top-level directory, no backend directory touched at all.

```text
apps/admin/
├── src/
│   ├── api/
│   │   ├── client.ts               # UNCHANGED — every request here is a plain
│   │   │                           #   authenticated GET (research.md R2)
│   │   ├── conversations.ts        # NEW — listConversations(params), getConversation(id)
│   │   │                           #       (research.md R3)
│   │   ├── types.ts                # EXTENDED — ConversationOutcome, ConversationSummary,
│   │   │                           #   ConversationListResponse, ConversationListParams,
│   │   │                           #   ConversationSource, ConversationDetail,
│   │   │                           #   SafeFailureCategory (data-model.md)
│   │   ├── knowledge.ts            # unchanged (Feature 014)
│   │   ├── auth.ts                 # unchanged (Feature 013)
│   │   └── admin.ts                # unchanged (Feature 013)
│   ├── routes/
│   │   ├── ConversationsPage.tsx   # NEW — replaces ConversationsPlaceholder.tsx; owns
│   │   │                           #   page state (list status, filters, offset, selection,
│   │   │                           #   detail status) — data-model.md "Frontend-only state"
│   │   ├── KnowledgePage.tsx       # unchanged (Feature 014)
│   │   ├── LoginPage.tsx           # unchanged
│   │   ├── AppHome.tsx             # unchanged
│   │   ├── ProtectedLayout.tsx     # unchanged
│   │   └── AnalyticsPlaceholder.tsx  # unchanged (Feature 016)
│   │   # ConversationsPlaceholder.tsx deleted
│   ├── components/
│   │   ├── conversations/          # NEW subfolder
│   │   │   ├── ConversationList.tsx        # table: question, outcome, time (FR-001–FR-003)
│   │   │   ├── ConversationFilters.tsx     # search form + outcome select + date inputs
│   │   │   │                               #   (FR-010–FR-017, research.md R8–R10)
│   │   │   ├── ConversationPagination.tsx  # Previous/Next (FR-018–FR-020, research.md R11)
│   │   │   ├── ConversationDetailPanel.tsx # inline detail (FR-022–FR-038, research.md R5–R6)
│   │   │   ├── OutcomeBadge.tsx            # text label, never color-only (FR-008)
│   │   │   └── outcomeLabel.ts             # mirrors statusLabel.ts (research.md R7)
│   │   ├── knowledge/               # unchanged (Feature 014)
│   │   ├── Header.tsx                # unchanged (Feature 013)
│   │   ├── Nav.tsx                   # unchanged (Feature 013)
│   │   ├── LoadingState.tsx          # unchanged (Feature 013) — reused for both list- and
│   │   │                             #   detail-level loading (FR-004, FR-023)
│   │   └── ErrorMessage.tsx          # unchanged (Feature 013) — reused for both list- and
│   │                                 #   detail-level failure (FR-006, FR-026)
│   ├── hooks/
│   │   ├── usePanelFocus.ts         # NEW — focus-in/focus-out for the inline detail panel
│   │   │                            #   (research.md R6, FR-047); does not touch <dialog>
│   │   ├── useDialogElement.ts      # unchanged (Feature 014) — not reused here (research.md R6)
│   │   └── usePageTitle.ts          # unchanged
│   └── routeConfig.tsx              # EXTENDED — 'conversations' child now renders ConversationsPage
└── tests/
    ├── conversations-list.test.tsx             # NEW
    ├── conversations-search.test.tsx           # NEW
    ├── conversations-outcome-filter.test.tsx   # NEW
    ├── conversations-date-filter.test.tsx      # NEW
    ├── conversations-pagination.test.tsx       # NEW
    ├── conversations-detail.test.tsx           # NEW — grounded/gap/out-of-scope/unavailable/small-talk
    ├── conversations-empty-states.test.tsx     # NEW
    ├── conversations-accessibility.test.tsx    # NEW
    ├── conversations-session-expiration.test.tsx  # NEW
    ├── api-conversations-client.test.ts        # NEW — query-param construction (research.md R10)
    ├── testUtils.tsx                           # EXTENDED — adds renderConversationsPage()
    │                                            #   (research.md R12)
    └── (existing Feature 013/014 test files unchanged)

src/shiruno/                       # NOT touched by this feature
tests/                             # NOT touched by this feature (backend)
```

**Structure Decision**: Pure extension of Feature 013/014's existing
`apps/admin/` layout — one new route file, one new API module, one new
component subfolder, one new focus-management hook, and one additive edit
to an already-existing file (`routeConfig.tsx`). `client.ts` is untouched
(research.md R2) — the first of the three UI features not to need a
`client.ts` change. No existing backend file is touched; no existing
frontend file outside `routeConfig.tsx` and `types.ts` is touched.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Not applicable — every Constitution Check item passes without deviation
(see table above); III, IV, V, VI, and X are marked N/A because this
feature's scope genuinely doesn't touch their subject matter (retrieval/
generation, document ingestion, LLM/embedding provider code, paid-provider
cost exposure), not because a violation was waived.
