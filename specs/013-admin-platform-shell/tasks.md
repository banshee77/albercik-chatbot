# Tasks: Shiruno Admin Platform Shell

**Input**: Design documents from `/specs/013-admin-platform-shell/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — spec.md's Acceptance Scenarios (per user story) and
Success Criteria (SC-001–SC-010) explicitly require automated coverage, and
research.md R10-R11 define the exact mechanism (Vitest + Testing Library,
API client mocked at the module boundary, no real backend/network).

**Organization**: Tasks are grouped by user story from spec.md, in priority
order. US1–US6 are P1 (facets of one shared authentication/routing
mechanism); US7 (loading/error politeness) is the sole P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task in the same phase)
- **[Story]**: Which user story this task belongs to (US1–US7, matching
  spec.md)
- Every task names its exact file path(s)

## Path Conventions

Web-application layout per plan.md's Structure Decision: `apps/admin/`
(new frontend) alongside the existing `src/shiruno/` (backend, touched only
for the new CORS setting) and `tests/` (backend test suite, touched only
for the new CORS test).

---

## Phase 1: Setup

**Purpose**: Scaffold the new `apps/admin/` frontend project.

- [X] T001 Scaffold a Vite + React + TypeScript project at `apps/admin/`
      (`package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`,
      `src/main.tsx` stub) using `npm` (research.md R4, R9)
- [X] T002 Add `react-router` as a dependency of `apps/admin/`
      (research.md R5)
- [X] T003 [P] Add Vitest, `@testing-library/react`,
      `@testing-library/user-event`, `@testing-library/jest-dom`, and
      `jsdom` as dev dependencies of `apps/admin/`, with a Vitest config
      (`apps/admin/vite.config.ts` test block or `vitest.config.ts`)
      pointing at the `jsdom` environment (research.md R10)
- [X] T004 [P] Add `apps/admin/.gitignore` (`node_modules/`, `dist/`,
      `.env`) and `apps/admin/.env.example` documenting
      `VITE_SHIRUNO_API_URL=http://localhost:8000` (research.md R9,
      data-model.md Configuration additions)
- [X] T005 [P] Configure ESLint + TypeScript strict mode for `apps/admin/`
      (`.eslintrc`/`eslint.config.js`, `tsconfig.json` strict flags) —
      satisfies SC-008 (production build completes with zero lint/type
      errors)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared API boundary, auth-state substrate, route guard,
and shell chrome every user story extends. Also the one backend change
this feature makes (CORS).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create `apps/admin/src/api/client.ts`: base URL from
      `import.meta.env.VITE_SHIRUNO_API_URL`, attaches the in-memory
      bearer token to every request, parses JSON responses, maps any
      non-2xx response to a typed, safe error (never raw backend text),
      and exposes a way to register one "unauthorized" callback invoked on
      `401`/`403` before rejecting (research.md R1, R7)
- [X] T007 [P] Create `apps/admin/src/api/auth.ts`: `login(username,
      password)` calling `POST /api/v1/auth/login` through `client.ts`
      (research.md R7)
- [X] T008 [P] Create `apps/admin/src/api/admin.ts`: `getMe()` calling
      `GET /api/v1/admin/me` through `client.ts` (research.md R7)
- [X] T009 Create `apps/admin/src/auth/AuthProvider.tsx`: the `AuthState`
      context (`status: "initializing" | "unauthenticated" | "authenticated"
      | "error"`, `administrator`, `tenant`, `errorMessage` — data-model.md
      `AuthState`), starting at `"initializing"` and immediately resolving
      to `"unauthenticated"` (no persisted token to recover — research.md
      R1), a `logout()` that clears all state and registers itself as the
      client's "unauthorized" callback (T006). `login()` itself is
      implemented in US1 (T0XX below) — this task creates the substrate
      only
- [X] T010 Create `apps/admin/src/routes/ProtectedLayout.tsx`: reads
      `AuthState`; renders an explicit loading indicator while
      `"initializing"`; redirects to `/login` while `"unauthenticated"` or
      `"error"`; renders the header, navigation, and nested route content
      only while `"authenticated"` (FR-010, FR-016, US2 Scenario 2)
- [X] T011 [P] Create `apps/admin/src/components/Header.tsx`: Shiruno
      identity, current organization name (`tenant.name`, never
      `tenant.id`), administrator username, and a logout action calling
      `AuthProvider`'s `logout()`; logout copy MUST NOT claim or imply
      server-side token revocation beyond what the bearer-token mechanism
      actually provides (FR-008, FR-015)
- [X] T012 [P] Create `apps/admin/src/components/Nav.tsx`: primary
      navigation with exactly three links — Knowledge, Conversations,
      Analytics — no placeholder entries for any other section (FR-012)
- [X] T013 Wire `apps/admin/src/App.tsx`: `react-router` data router with
      `/login` (public) and `/app` + `/app/knowledge` + `/app/conversations`
      + `/app/analytics` nested under `ProtectedLayout` (T010) (FR-009)
- [X] T014 Wire `apps/admin/src/main.tsx`: mounts `<AuthProvider><App />
      </AuthProvider>` (T009, T013)
- [X] T015 [P] Add `CORS_ALLOWED_ORIGINS: str = ""` to `Settings` in
      `src/shiruno/config.py` (research.md R8)
- [X] T016 Wire conditional `fastapi.middleware.cors.CORSMiddleware`
      registration in `src/shiruno/main.py::create_app()`: added only when
      `settings.CORS_ALLOWED_ORIGINS` is non-empty, with
      `allow_origins=<parsed comma-separated list>` (never `["*"]`),
      `allow_credentials=False`, and `allow_methods`/`allow_headers` scoped
      to `GET`/`POST` and `Authorization`/`Content-Type` (research.md R8)
- [X] T017 [P] Create `tests/unit/test_cors_configuration.py`: no
      `CORSMiddleware` is registered when `CORS_ALLOWED_ORIGINS` is unset
      (default); when set, only the configured origin(s) are allowed and
      the origin list is never `"*"` (FR-024; research.md R8)
- [X] T018 [P] Document `CORS_ALLOWED_ORIGINS` in the root `.env.example`
      (commented out, empty default) (research.md R8)

**Checkpoint**: Foundation ready — every user story below can now begin.

---

## Phase 3: User Story 1 - Administrator logs in and reaches the authenticated shell (Priority: P1) 🎯 MVP

**Goal**: A working login form that, on valid credentials, authenticates
through the existing backend and lands on a shell showing the
administrator's own organization identity.

**Independent Test**: With a valid administrator account, submit correct
credentials at the login page and confirm the application shell loads with
the administrator's own organization identity visible (spec US1).

### Tests for User Story 1

- [X] T019 [P] [US1] Component test in `apps/admin/tests/login.test.tsx`:
      login page renders with labeled, accessible username/password fields
      (FR-025); valid credentials establish authenticated state and land
      on the shell (FR-001, FR-003, US1 Scenario 1); invalid credentials
      show one generic authentication-failure message (FR-002, US1
      Scenario 3); the submitted token/credential value is never rendered
      anywhere in the DOM (FR-019); `/admin/me` is called after a
      successful login and its response populates the displayed
      organization/administrator identity (FR-005, US1 Scenario 2)

### Implementation for User Story 1

- [X] T020 [US1] Implement `login(username, password)` on
      `AuthProvider.tsx` (T009): calls `api/auth.ts`'s `login()`, then
      `api/admin.ts`'s `getMe()`; on both succeeding, sets `status:
      "authenticated"` with the returned administrator/tenant; on either
      failing, sets `status: "error"` with one generic message (FR-002,
      FR-003, data-model.md `AuthState` transitions)
- [X] T021 [US1] Create `apps/admin/src/routes/LoginPage.tsx`: labeled
      username/password fields, client-side non-empty validation before
      calling `login()` (FR-004, FR-025), a loading state during
      submission (FR-017), and the generic error message from `AuthState`
      when present
- [X] T022 [US1] Create `apps/admin/src/routes/AppHome.tsx`: `/app`
      landing content showing organization identity, a welcome state, and
      navigation shortcuts to Knowledge/Conversations/Analytics (spec.md
      US1 Scenario 2, Key Entities)

**Checkpoint**: An administrator can log in and see their own organization
on the shell — the feature's core value already exists.

---

## Phase 4: User Story 2 - Unauthenticated access to protected routes redirects to login (Priority: P1)

**Goal**: Confirm, not just assume, that `ProtectedLayout` (T010) actually
gates every `/app` route correctly, including during bootstrap.

**Independent Test**: Without ever logging in, attempt to open `/app` and
each of its sub-routes directly, and confirm each one redirects to
`/login` (spec US2).

### Tests for User Story 2

- [X] T023 [US2] Integration test in
      `apps/admin/tests/route-protection.test.tsx`: an unauthenticated
      visitor requesting `/app`, `/app/knowledge`, `/app/conversations`, or
      `/app/analytics` is redirected to `/login` (FR-010, US2 Scenario 1);
      an authenticated administrator reaches each of those routes
      successfully (US2 Scenario 3); while `AuthState.status ===
      "initializing"`, no tenant-scoped content renders — only the loading
      state — before either the redirect or the shell appears (FR-016, US2
      Scenario 2)

**Checkpoint**: Route protection is proven, not assumed — no new
implementation was needed beyond what T010 already provides.

---

## Phase 5: User Story 3 - Administrator's own organization identity is always visible and correct (Priority: P1)

**Goal**: Confirm the header and shell only ever show the authenticated
administrator's own organization, sourced exclusively from `/admin/me`,
and that no request the frontend sends can select a different tenant.

**Independent Test**: Log in as an administrator belonging to a specific
tenant, confirm the organization name shown matches that tenant, and
confirm no request carries a client-chosen tenant identifier (spec US3).

### Tests for User Story 3

- [X] T024 [US3] Component test in
      `apps/admin/tests/organization-identity.test.tsx`: the header shows
      `tenant.name` as the primary organization label and never renders
      `tenant.id` as primary text (FR-008); no tenant-switcher control
      (dropdown, search box, or similar) exists anywhere in the rendered
      shell (US3 Scenario 3)
- [X] T025 [P] [US3] Unit test in `apps/admin/tests/api-client.test.ts`:
      inspecting every outgoing request built by `api/client.ts` (T006)
      confirms none ever includes a client-supplied tenant identifier used
      to select data (FR-006, FR-021, US3 Scenario 2)

**Checkpoint**: Organization identity is proven server-derived-only, with
no implementation change needed beyond Foundational's existing `Header.tsx`
and `client.ts`.

---

## Phase 6: User Story 4 - Administrator navigates the placeholder Knowledge, Conversations, and Analytics sections (Priority: P1)

**Goal**: Each of the three future product sections is reachable from
primary navigation and loads a clear placeholder.

**Independent Test**: While authenticated, use primary navigation to reach
Knowledge, then Conversations, then Analytics, confirming each loads with
placeholder content only (spec US4).

### Implementation for User Story 4

- [X] T026 [P] [US4] Create
      `apps/admin/src/routes/KnowledgePlaceholder.tsx`: `/app/knowledge`
      placeholder content with a meaningful page title, no document/upload
      behavior (FR-011, FR-027)
- [X] T027 [P] [US4] Create
      `apps/admin/src/routes/ConversationsPlaceholder.tsx`:
      `/app/conversations` placeholder content, no conversation behavior
      (FR-011, FR-027)
- [X] T028 [P] [US4] Create
      `apps/admin/src/routes/AnalyticsPlaceholder.tsx`: `/app/analytics`
      placeholder content, no analytics behavior (FR-011, FR-027)

### Tests for User Story 4

- [X] T029 [US4] Integration test in `apps/admin/tests/navigation.test.tsx`:
      authenticated navigation to Knowledge, Conversations, and Analytics
      each succeed and render their placeholder (US4 Scenarios 1-3);
      primary navigation contains exactly these three items, no entry for
      any not-yet-built section (US4 Scenario 4); every navigation link is
      reachable and activatable via keyboard alone (FR-026, SC-010)

**Checkpoint**: The full placeholder shell subsequent features (014-016)
will build on top of now exists and is reachable.

---

## Phase 7: User Story 5 - Administrator logs out and the session is fully cleared (Priority: P1)

**Goal**: Logout clears all frontend session/token/cached state and
returns to `/login`, with no stale data reachable afterward.

**Independent Test**: While authenticated, trigger logout and confirm the
administrator lands on `/login`, and that returning to any `/app` route
afterward redirects to `/login` rather than showing cached data (spec US5).

### Tests for User Story 5

- [X] T030 [US5] Integration test in `apps/admin/tests/logout.test.tsx`:
      triggering the logout action clears `AuthState` (back to
      `"unauthenticated"`) and cached administrator/tenant data, and
      navigates to `/login` (FR-014, US5 Scenario 1); the logout UI never
      states or implies server-side token revocation beyond what the
      bearer-token mechanism actually provides (FR-015); attempting to
      return to a previously visited `/app` route afterward redirects to
      `/login` rather than rendering stale content (US5 Scenario 2)

**Checkpoint**: Logout is proven complete — no new implementation was
needed beyond Foundational's `Header.tsx` logout action and
`AuthProvider.logout()`.

---

## Phase 8: User Story 6 - An expired or invalidated session is handled safely mid-use (Priority: P1)

**Goal**: A mid-session authentication failure is caught by the one
centralized `401`/`403` handling path and results in a safe, generic
session-expired redirect — never stale tenant data left on screen.

**Independent Test**: While authenticated and viewing a protected route,
simulate the backend rejecting the next authenticated request with an
authentication failure, and confirm the frontend clears its session state
and redirects to `/login` with a safe, generic message (spec US6).

### Implementation for User Story 6

- [X] T031 [US6] Extend `AuthProvider.tsx`'s registered "unauthorized"
      callback (T009) to distinguish this case from a fresh, deliberate
      logout: set `status: "unauthenticated"` together with a
      `sessionExpired: true` marker before the redirect (FR-013)
- [X] T032 [US6] Extend `LoginPage.tsx` (T021) to read the `sessionExpired`
      marker and render a safe, generic "your session has expired" message
      when present, distinct from the plain (never-logged-in) login state
      (FR-013, US6 Scenario 2)

### Tests for User Story 6

- [X] T033 [US6] Integration test in
      `apps/admin/tests/session-expiration.test.tsx`: an authenticated API
      call that comes back rejected for authentication reasons clears
      `AuthState` (FR-013, US6 Scenario 1) and redirects to `/login`
      showing the generic session-expired message (US6 Scenario 2); no
      previously loaded organization-scoped data remains visible after the
      redirect (US6 Scenario 3)

**Checkpoint**: A session that becomes invalid mid-use is handled exactly
as safely as one that was never valid to begin with.

---

## Phase 9: User Story 7 - Administrator gets safe, clear feedback during loading and error conditions (Priority: P2)

**Goal**: Backend-unreachable, slow, and error conditions all produce
honest, non-technical feedback — never a blank screen, never raw backend
detail.

**Independent Test**: Simulate a backend-unavailable condition during
login and during `/admin/me` retrieval, and confirm both produce a clear,
non-technical message rather than a blank screen or raw error text (spec
US7).

### Implementation for User Story 7

- [X] T034 [P] [US7] Create `apps/admin/src/components/LoadingState.tsx`:
      a small, reusable loading indicator used by `ProtectedLayout` (T010)
      during bootstrap and by `LoginPage` (T021) during submission
      (FR-016, FR-017)
- [X] T035 [P] [US7] Create `apps/admin/src/components/ErrorMessage.tsx`:
      a small, reusable safe-error display component
- [X] T036 [US7] Extend `api/client.ts` (T006): a network-level failure
      (backend completely unreachable) is mapped to the same safe, typed
      error shape as an HTTP error response — never a raw `fetch`
      `TypeError` or browser network-error string reaching UI code
      (FR-018, FR-019)

### Tests for User Story 7

- [X] T037 [US7] Component test in
      `apps/admin/tests/loading-and-error-states.test.tsx`: a simulated
      unreachable backend during login shows the generic
      service-unavailable message, not a raw network error (FR-018,
      FR-019); the login form is fully operable using the keyboard alone,
      including submission (SC-010)

**Checkpoint**: Every loading/error path required by spec.md's Error
States and Loading States sections is now covered, not just the
happy-path stories above.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T038 [P] Run `npm run build` in `apps/admin/` and confirm the
      production build succeeds with zero errors (FR-029, SC-008)
- [X] T039 [P] Run ESLint and `tsc --noEmit` across `apps/admin/` and fix
      any findings (SC-008)
- [X] T040 Run the full existing backend automated suite (`uv run pytest`,
      `uv run ruff check .`, `uv run mypy src tests`) and confirm every
      pre-existing test/gate still passes unmodified in intent — tenant
      isolation, Feature 010 Knowledge API, Feature 011
      Conversations/Analytics, Feature 012 observability, and the public
      `/api/v1/chat` contract (FR-031, SC-009)
- [X] T041 [P] Add an "Admin frontend" section to the root `README.md`
      documenting the `apps/admin/` local development workflow (`npm
      install`, `npm run dev`, `.env` setup) alongside the existing
      backend `docker compose up` instructions (FR-030)
- [X] T042 Manually execute `specs/013-admin-platform-shell/quickstart.md`
      end-to-end against the live local backend and frontend dev server,
      confirming every step (login, organization identity, all three
      placeholder routes, logout, protected-route re-check) behaves as
      documented (quickstart.md)
- [X] T043 [P] Manual/visual check: confirm `apps/admin/`'s layout stays
      usable (no overlapping/clipped content, every interactive element
      still reachable) at a common laptop width (~1366px) and a common
      tablet width (~768px) via browser dev-tools device emulation;
      record the result in the PR description (FR-028)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story.
  Contains both the frontend substrate (API boundary, `AuthProvider`
  skeleton, route guard, shell chrome) and the one backend change (CORS).
- **User Story 1 (Phase 3)**: Depends on Foundational only. Implements the
  one behavior (`login()`) Foundational deliberately left as a stub.
- **User Stories 2, 3 (Phases 4-5)**: Depend on Foundational + US1 (they
  verify mechanisms US1's login flow exercises for the first time); no
  dependency on each other.
- **User Story 4 (Phase 6)**: Depends on Foundational's `Nav.tsx`/router
  wiring (T012, T013) and, for a realistic authenticated test, US1's login
  flow.
- **User Story 5 (Phase 7)**: Depends on Foundational's `Header.tsx`
  logout action and `AuthProvider.logout()` (T009, T011), and US1 to
  reach an authenticated state to log out of.
- **User Story 6 (Phase 8)**: Depends on Foundational's `client.ts`
  "unauthorized" callback plumbing (T006, T009) and US1's `LoginPage.tsx`
  (T021), which it extends.
- **User Story 7 (Phase 9)**: Depends on Foundational (T006, T010) and
  US1's `LoginPage.tsx` (T021), which it extends with loading states.
- **Polish (Phase 10)**: Depends on all desired stories being complete.

### Within Each User Story

- Implementation tasks precede their corresponding test tasks only where
  the test genuinely needs new behavior to exist first (US1, US6, US7);
  where a story only verifies Foundational's already-built mechanism
  (US2, US3 Header check, US5), the test task stands alone.
- Tasks touching the same file within a phase (e.g., `AuthProvider.tsx` in
  T009 then T020, or `LoginPage.tsx` in T021 then T032/T036) are
  sequential by construction — each later task extends what an earlier
  phase already created.

### Parallel Opportunities

- T003, T004, T005 (Setup) touch independent files and can run together.
- T007, T008 (Foundational) are independent files (`auth.ts`, `admin.ts`);
  T011, T012 (`Header.tsx`, `Nav.tsx`) are likewise independent of each
  other and of T007/T008.
- T015, T017, T018 (backend CORS: settings, test, `.env.example`) touch
  different files from every frontend Foundational task and from each
  other (T017 depends on T015/T016 conceptually but is a different file).
- T026, T027, T028 (US4's three placeholder routes) are fully independent
  files and can be built in parallel.
- T034, T035 (US7's two small components) are independent files.
- T038, T039, T041 (Polish) touch independent concerns/files and can run
  in parallel; T040 (the full backend gate run) is independent of all
  three but is heavier and best run on its own.

---

## Parallel Example: Foundational Phase

```bash
# Launch these together once T006 exists — different files:
Task: "Create apps/admin/src/api/auth.ts"
Task: "Create apps/admin/src/api/admin.ts"
Task: "Create apps/admin/src/components/Header.tsx"
Task: "Create apps/admin/src/components/Nav.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run T019, confirm login → shell → organization
   identity works end-to-end against a real local backend
5. This alone already delivers the feature's core value (spec US1's own
   "Why this priority": "the single entry point every other story depends
   on")

### Incremental Delivery

1. Setup + Foundational → the shell's substrate exists
2. US1 → login actually works → **first checkpoint with real value**
3. US2 → prove route protection holds (it's the core access-control
   guarantee — verify it early, before adding more surface area)
4. US3 → prove organization identity is correct and never
   client-selectable
5. US4 → the placeholder navigation subsequent features build on
6. US5 → logout proven complete
7. US6 → mid-session expiration proven safe
8. US7 (P2) → loading/error politeness, whenever convenient
9. Polish → build/lint/backend-regression gates, docs, live quickstart

### Recommended Team Strategy

Given how much of this feature shares `AuthProvider.tsx`,
`api/client.ts`, and `LoginPage.tsx` across stories (US1 creates them, US6
and US7 each extend them further), this feature is better suited to
sequential single-developer implementation in priority order than
parallel multi-developer staffing — the exception is US4 (Phase 6), whose
three placeholder routes are fully independent of every other story once
Foundational's router/nav exist.

---

## Notes

- `[P]` tasks touch different files with no dependency on an incomplete
  task in the same phase; tasks that extend a file an earlier phase
  already created are deliberately left sequential.
- `[Story]` labels map every user-story-phase task back to spec.md's
  US1–US7 for traceability.
- No task in this list changes the semantics of `POST /api/v1/auth/login`,
  `GET /api/v1/admin/me`, the Knowledge API, the Conversations/Analytics
  API, or the public `/api/v1/chat` contract — verified explicitly by T040
  (FR-031).
- Commit after each task or logical group; verify tests fail before their
  corresponding implementation task lands, where a test task follows its
  implementation task in the same phase.
- Constitution gate: Principle XIV was amended (v4.1.0 → v4.2.0, see
  `.specify/memory/constitution.md`) specifically to approve
  TypeScript/React/Vite/React Router (plus frontend-specific extensions to
  Principles I, II, VII, VIII, XI, XIII) before this tasks.md was
  generated — no further constitutional action is needed to implement this
  list.
