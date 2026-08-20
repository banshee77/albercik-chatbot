# Implementation Plan: Shiruno Admin Platform Shell

**Branch**: `013-admin-platform-shell` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-admin-platform-shell/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Build the first customer-facing frontend: a standalone React/TypeScript/
Vite single-page application (`apps/admin/`) that lets a customer
administrator log in through the existing `POST /api/v1/auth/login` +
`GET /api/v1/admin/me` flow, see their own organization's identity, move
through a protected application shell, reach placeholder Knowledge/
Conversations/Analytics routes, and log out — with the bearer token kept
in memory only (never `localStorage`/`sessionStorage`), one centralized
API access boundary, and narrowly-configured backend CORS as the only
backend change (research.md R1-R11). No new database entity, no change to
existing API semantics, no functional Knowledge/Conversations/Analytics
behavior — those are Features 014-016.

## Technical Context

**Language/Version**: TypeScript (frontend, new); Python 3.14 (backend,
unchanged)

**Primary Dependencies**: React, `react-router`, Vite (frontend, all new
to this repository); FastAPI's own `CORSMiddleware` (backend, already a
transitive dependency of the existing FastAPI install — no new package)

**Storage**: N/A — no new database entity; the frontend's only "storage"
is an in-memory JS object for the lifetime of one tab (research.md R1),
deliberately never persisted

**Testing**: Vitest + `@testing-library/react` + `@testing-library/user-event`
(frontend, new); pytest (backend, unchanged — only the new
`CORS_ALLOWED_ORIGINS` setting and its middleware wiring need coverage)

**Target Platform**: Modern evergreen browsers (frontend, authenticated
SPA); Linux server/Docker container (backend, unchanged)

**Project Type**: Web application — frontend (`apps/admin/`) + existing
backend (`src/shiruno/`), two independently-run processes in local
development (research.md R9)

**Performance Goals**: No new numeric target; standard SPA responsiveness
(interactive within a normal page-load budget) is sufficient — this
feature has no data-volume or throughput dimension

**Constraints**: No secret in frontend build configuration (FR-023); no
wildcard CORS origin for authenticated traffic (FR-024); token never
written to `localStorage`/`sessionStorage` (research.md R1); frontend is
explicitly not a security boundary — every constraint the backend already
enforces (tenant isolation, fail-closed auth) remains enforced there,
unchanged

**Scale/Scope**: One frontend application, 5 routes (3 of them
placeholder-only in this feature), 1 new backend setting
(`CORS_ALLOWED_ORIGINS`), 0 new backend endpoints, 0 new database entities

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default | PASS | Token kept in-memory only (research.md R1); no new trust decision is made client-side. |
| II. Multi-Tenant Isolation | PASS | Frontend never supplies a tenant identifier on any request (FR-006, FR-021); tenant identity is exclusively server-derived via `/admin/me`, unchanged from Feature 009's existing enforcement. |
| III. Secure RAG | N/A | This feature touches no retrieval/generation path. |
| IV. Secure Document Ingestion | N/A | No upload behavior is added or changed. |
| V. LLM Provider Neutrality | N/A | No LLM code touched. |
| VI. Embedding Provider Neutrality | N/A | No embedding code touched. |
| VII. Provider and Cloud Neutrality | PASS | Frontend production hosting is explicitly deferred (spec, research.md R9); nothing here commits to a cloud provider. |
| VIII. API Security | PASS | No new endpoint; existing auth/authorization ordering on `/auth/login` and `/admin/me` is unchanged. CORS is added narrowly, never wildcard (FR-024, research.md R8). |
| IX. Privacy and Logging | PASS | No raw backend error, stack trace, or token is ever rendered (FR-019); nothing new is logged. |
| X. Cost Safety | N/A | This feature adds no path that can invoke a paid LLM/embedding provider. |
| XI. Testing Discipline | PASS | research.md R10-R11 — component tests mock the API client, no real network/provider dependency; role-relevant behavior (auth, tenant-boundary respect) is directly tested. |
| XII. Engineering Quality | PASS | One small `api/` boundary (R7), one `AuthProvider` (R6) — no premature abstraction beyond what FR-020/FR-016 already require. |
| XIII. Simplicity for MVP | PASS | Next.js, Redux, GraphQL, a component library, and MSW were each explicitly considered and rejected as more than this shell needs (research.md R4-R6, R10). |
| **XIV. Approved MVP Technology Stack** | **PASS** | Resolved 2026-08-20 by constitution amendment v4.1.0 → v4.2.0: TypeScript, React, Vite, and React Router added to the approved stack, scoped to browser-based Shiruno applications under `apps/*`. Next.js, Redux, Zustand, GraphQL, Tailwind, MUI, Chakra, shadcn, Storybook, Nx, Turborepo, and SSR frameworks explicitly remain unapproved, matching this plan's own choices (research.md R4-R6, R10). |

**Principle XIV gate — resolved**: The constitution was amended
(`.specify/memory/constitution.md`, v4.1.0 → v4.2.0, 2026-08-20) to add
the approved frontend stack, following the same process Feature 012 used
for OpenTelemetry/Phoenix. The amendment also extended Principles I, II,
VII, VIII, XI, and XIII with frontend-specific rules (in-memory-only
token storage, frontend-never-a-security-boundary, deployment neutrality,
narrow CORS, frontend testing gates, frontend simplicity) — every one of
which this plan's research.md decisions (R1-R11) already independently
matched before the amendment existed. Feature 013 now passes all 14
Constitution Check gates; nothing in this plan's architecture changed as
a result. Safe to proceed to `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/013-admin-platform-shell/
├── plan.md               # This file (/speckit-plan command output)
├── research.md            # Phase 0 output (/speckit-plan command)
├── data-model.md          # Phase 1 output (/speckit-plan command)
├── quickstart.md          # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md    # Spec-quality checklist (/speckit-specify, /speckit-clarify)
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new backend API
surface — it reuses `POST /api/v1/auth/login` and `GET /api/v1/admin/me`
exactly as they exist today (data-model.md). The only backend-facing
contract change is the new `CORS_ALLOWED_ORIGINS` server setting, which is
configuration, not an API contract.

### Source Code (repository root)

Web-application structure — a new frontend directory alongside the
existing single-package backend, per research.md R3 (executing
`docs/architecture.md`'s own already-documented target direction, not new
speculative structure).

```text
apps/admin/                      # NEW — Shiruno Admin frontend
├── src/
│   ├── api/
│   │   ├── client.ts             # base URL, auth header, JSON handling, 401 callback (research.md R7)
│   │   ├── auth.ts                # login(username, password)
│   │   └── admin.ts               # getMe()
│   ├── auth/
│   │   └── AuthProvider.tsx       # AuthState context + login()/logout() (research.md R6)
│   ├── routes/
│   │   ├── LoginPage.tsx
│   │   ├── ProtectedLayout.tsx    # route guard + header + navigation shell
│   │   ├── AppHome.tsx            # /app
│   │   ├── KnowledgePlaceholder.tsx    # /app/knowledge
│   │   ├── ConversationsPlaceholder.tsx # /app/conversations
│   │   └── AnalyticsPlaceholder.tsx     # /app/analytics
│   ├── components/
│   │   └── (Header, Nav, LoadingState, ErrorMessage — small, shell-only)
│   ├── App.tsx                    # router wiring (react-router data router)
│   └── main.tsx                   # Vite entry point
├── public/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── .env.example                   # VITE_SHIRUNO_API_URL (research.md R9)
└── tests/
    ├── login.test.tsx
    ├── route-protection.test.tsx
    ├── session-expiration.test.tsx
    ├── logout.test.tsx
    └── navigation.test.tsx

src/shiruno/                      # existing backend — unchanged except:
├── config.py                      # + CORS_ALLOWED_ORIGINS setting (research.md R8)
└── main.py                        # + conditional CORSMiddleware registration

tests/                             # existing backend test suite — unchanged except:
└── unit/
    └── test_cors_configuration.py # NEW — CORS middleware wiring, off-by-default, no wildcard
```

**Structure Decision**: Web-application layout with two independently-run
processes — `apps/admin/` (new, frontend, Vite dev server / static build)
and `src/shiruno/` (existing, backend, unchanged in every way except the
one new CORS setting). No existing backend file moves; no existing
directory is restructured to accommodate the frontend, matching the
spec's explicit instruction.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No Constitution Check items require a Complexity Tracking justification —
every applicable principle (I, II, VII, VIII, IX, XI, XII, XIII) passes
without deviation; III/IV/V/VI/X are N/A (this feature touches none of
their subject matter). Principle XIV is flagged above as a
technology-approval gate, to be resolved via `/speckit-constitution`
(matching Feature 012's precedent) rather than a documented exception —
Principle XIV's own governance text requires an amendment for this
situation, not a Complexity Tracking justification.
