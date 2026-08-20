# Tasks: Knowledge Base UI

**Input**: Design documents from `/specs/014-knowledge-base-ui/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — spec.md's own Success Criteria (SC-001–SC-010) explicitly
require automated verification for nearly every one ("verified by an
automated test"/"verified by automated tests"), and research.md R10 defines
the exact mechanism (Vitest + Testing Library, `api/knowledge.ts` mocked at
the module boundary, no real backend/network).

**Organization**: Tasks are grouped by user story from spec.md, in priority
order. US1–US3 are P1 (view, upload, recover-from-failure — the complete
"manage knowledge without a developer" MVP loop); US4–US5 are P2 (replace,
delete); US6 (session expiration during a mutation) is the sole P3, and
reuses Feature 013's already-built centralized mechanism rather than adding
new behavior.

**Cross-story sequencing note**: US1's Independent Test deliberately uses a
tenant that *already has* documents, so it never depends on Upload (US2)
to be testable — but FR-003's empty-state "prominent way to upload" and
the spec's own Page Structure (Upload sits between Health and the
Document list at the page level, not only inside the empty state) both
need an `UploadControl` component to exist. Rather than stub it, US1
builds the full accessible `UploadControl` shell (file input, filename
display, submit button) with no submit/network logic yet, and US2 extends
that same file with the actual upload behavior — mirroring Feature 013's
own `AuthProvider.tsx` (substrate in Foundational, `login()` added in
US1) and `LoginPage.tsx` (built in US1, extended by US6/US7) precedent.
Similarly, US3's failure-recovery panel offers Re-index alone at first
(FR-016's "re-index and/or replace" explicitly permits just one), and US4
adds the Replace trigger to that same panel afterward — no stub needed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task in the same phase)
- **[Story]**: Which user story this task belongs to (US1–US6, matching
  spec.md)
- Every task names its exact file path(s)

## Path Conventions

Extends the existing `apps/admin/` frontend from Feature 013 (plan.md
Structure Decision) — no new project. `src/shiruno/` is touched by exactly
one task (T037, a one-line additive CORS fix surfaced during live QA);
every other backend task runs the existing suite unmodified.

---

## Phase 1: Setup

No setup tasks are required. This feature extends the existing
`apps/admin/` scaffold from Feature 013 in place — no new dependency, tool,
or project scaffolding is introduced (plan.md Technical Context: zero new
frontend dependencies).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two small, additive extensions to the existing centralized
API client every mutation needs, the new `knowledge.ts` API module every
story calls into, the shared status-label component, and the route itself
wired to a (not-yet-data-rendering) page substrate.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 Extend `apps/admin/src/api/client.ts`'s `request()`: (a) skip
      forcing `Content-Type: application/json` when `init.body instanceof
      FormData`, letting the browser set its own multipart boundary; (b)
      on a `204`/empty-body success response, return `undefined`
      immediately instead of calling `response.json()` (research.md R2)
- [X] T002 Create `apps/admin/src/api/knowledge.ts`: `listDocuments()`,
      `getKnowledgeHealth()`, `getDocument(id)`, `uploadDocument(file)`,
      `replaceDocument(id, file)`, `reindexDocument(id)`,
      `deleteDocument(id)` — all via `request()` from `client.ts` (T001);
      `uploadDocument`/`replaceDocument` build a `FormData` with the file
      under field name `file`; no function accepts or constructs a tenant
      identifier (research.md R1, R3; FR-030, FR-031)
- [X] T003 [P] Create `apps/admin/src/components/knowledge/StatusBadge.tsx`:
      maps `"processing"` → "Processing", `"ready"` → "Ready", `"failed"`
      → "Failed", any other value → a generic fallback label; renders
      status as text, never conveyed by color alone (FR-005, FR-008;
      research.md R6)
- [X] T004 Create `apps/admin/src/routes/KnowledgePage.tsx`: page-level
      state substrate per data-model.md `KnowledgePageState` (`status:
      "loading" | "loaded" | "error"`, `documents`, `health`,
      `selectedDocumentId`, `pendingAction`), a `reloadKnowledge()`
      function (`Promise.all([listDocuments(), getKnowledgeHealth()])`,
      research.md R8) called once on mount via `useEffect`; renders only
      `LoadingState`/`ErrorMessage` scaffolding for now — health/list/
      empty rendering is built in US1 (depends on T002)
- [X] T005 Wire `apps/admin/src/routeConfig.tsx`: replace the `'knowledge'`
      child route's `KnowledgePlaceholder` element with `KnowledgePage`
      (T004)
- [X] T006 Delete `apps/admin/src/routes/KnowledgePlaceholder.tsx`
      (superseded by T004/T005)

**Checkpoint**: Foundation ready — every user story below can now begin.

---

## Phase 3: User Story 1 - Administrator sees whether their knowledge base is ready (Priority: P1) 🎯 MVP

**Goal**: Opening Knowledge shows a real health summary and document list
(or an intentional empty state) sourced from the tenant's own data, with
explicit loading and error-with-retry states.

**Independent Test**: Log in as a tenant administrator with existing
knowledge documents, open Knowledge, and confirm the health summary and
document list both reflect that tenant's real data (spec US1).

### Implementation for User Story 1

- [X] T007 [P] [US1] Create
      `apps/admin/src/components/knowledge/HealthSummary.tsx`: renders
      total/ready/processing/failed document counts, active chunk count,
      and "Ready for chat: Yes/No" from a `KnowledgeHealthSummary` —
      never a raw tenant ID, embedding vector, or provider config
      (FR-001, FR-002)
- [X] T008 [P] [US1] Create
      `apps/admin/src/components/knowledge/DocumentTable.tsx`: renders
      `documents` in the exact order received (FR-006), each row showing
      filename, status (via `StatusBadge`, T003), and updated date —
      matching spec's own conceptual layout (Name/Status/Updated); content
      type lives in `DocumentDetailPanel` (T017/FR-014) rather than being
      duplicated in the list; never renders a document the backend didn't
      return as active (FR-004, FR-005, FR-007)
- [X] T009 [P] [US1] Create
      `apps/admin/src/components/knowledge/UploadControl.tsx`: accessible
      file input (`accept=".txt,text/plain"`) + selected-filename display
      + submit button, taking an `onUpload(file)` callback prop it invokes
      on submit — no network/loading/error logic yet (that lands in US2)
      (FR-009, FR-010; research.md R7)
- [X] T010 [US1] Extend `apps/admin/src/routes/KnowledgePage.tsx` (T004):
      render `LoadingState` while `status === "loading"`; render
      `ErrorMessage` plus a retry action while `status === "error"`; once
      `status === "loaded"`, render `HealthSummary` (T007) and
      `UploadControl` (T009, `onUpload` still a no-op stub) at the top of
      the page, then either `DocumentTable` (T008) when `documents.length
      > 0`, or an intentional empty-state message ("No knowledge has been
      added yet.") reusing the same `UploadControl` as its prominent CTA
      when `documents.length === 0` (FR-003, FR-034, FR-035)

### Tests for User Story 1

- [X] T011 [US1] Add `renderKnowledgePage()` to
      `apps/admin/tests/testUtils.tsx` — wraps `KnowledgePage` (T004) in
      an authenticated `AuthContext.Provider`, mirroring
      `route-protection.test.tsx`'s existing direct-context-injection
      pattern (research.md R10); component test in
      `apps/admin/tests/knowledge-health.test.tsx`: mocking
      `api/knowledge.ts`, confirms the health summary renders total/
      ready/processing/failed counts, chunk count, and "ready for chat"
      correctly from a mocked `getKnowledgeHealth()` response (FR-001; US1
      Scenario 1)
- [X] T012 [US1] Component test in
      `apps/admin/tests/knowledge-list.test.tsx`: confirms the document
      list renders tenant-returned documents with human-readable status
      text (not color alone) in the order the mock returns them (FR-004–
      FR-007; US1 Scenario 1); confirms an empty `listDocuments()`
      response renders the intentional empty state with a keyboard-
      reachable upload CTA, not a broken-looking table (FR-003; US1
      Scenario 2); confirms an explicit loading state renders before data
      arrives (US1 Scenario 3); confirms a rejected initial load renders a
      distinct error state with a retry action, never presented as an
      empty knowledge base (FR-034, FR-035; US1 Scenario 4)
- [X] T013 [P] [US1] Unit test in
      `apps/admin/tests/api-knowledge-client.test.ts`: mocking global
      `fetch`, confirms every `knowledge.ts` (T002) function's request —
      list, health, get, upload, replace, re-index, delete — never
      includes a tenant identifier in its URL, headers, or body (FR-031)

**Checkpoint**: An administrator can open Knowledge and see their real
health/list data — the feature's core read value already exists.

---

## Phase 4: User Story 2 - Administrator uploads a document and it becomes usable knowledge (Priority: P1)

**Goal**: Selecting and submitting a file adds it to the tenant's knowledge
base, with an explicit in-progress state and a refreshed list/health on
completion — no full page reload.

**Independent Test**: While on the Knowledge page, select and upload a
valid document, and confirm the document list and health summary both
update to reflect it, ending in a "Ready" status (spec US2).

### Implementation for User Story 2

- [X] T014 [US2] Extend `apps/admin/src/routes/KnowledgePage.tsx` (T010):
      implement `handleUpload(file)` — sets `pendingAction: {kind:
      "upload"}`, calls `uploadDocument(file)` (T002), on success calls
      `reloadKnowledge()` and shows success feedback exposing the
      resulting document's status, on failure surfaces the returned
      `ApiError.message` via `ErrorMessage`, always clears `pendingAction`
      in a `finally`; wire it as `UploadControl`'s (T009) real `onUpload`
      prop, replacing the stub (FR-012, FR-013)
- [X] T015 [US2] Extend
      `apps/admin/src/components/knowledge/UploadControl.tsx` (T009):
      disable the submit button while `pendingAction?.kind === "upload"`
      and show an explicit "Uploading and indexing…" `LoadingState` for
      the duration — no fabricated percentage progress (FR-011)

### Tests for User Story 2

- [X] T016 [US2] Integration test in
      `apps/admin/tests/knowledge-upload.test.tsx`: a mocked successful
      `uploadDocument()` response refreshes both the document list and
      health summary and shows success feedback without a full reload
      (FR-012; US2 Scenario 2); a mocked rejected `uploadDocument()` shows
      exactly one safe message, never raw backend text (FR-013; US2
      Scenario 3); a second submission while the first is still pending is
      prevented (US2 Scenario 4); the whole flow — file selection through
      submission — is operable using the keyboard alone (FR-037)

**Checkpoint**: An administrator can add new knowledge end-to-end — the
feature's core value-creation flow now works.

---

## Phase 5: User Story 3 - Administrator recovers a failed document without developer help (Priority: P1)

**Goal**: A failed document's detail explains why in plain language and
offers Re-index as a self-service recovery action, without ever presenting
an unrelated working document as broken.

**Independent Test**: With a document in a failed state, open its detail,
confirm the sanitized failure reason and Re-index action are shown, trigger
it, and confirm the outcome is reflected without other documents appearing
broken (spec US3).

### Implementation for User Story 3

- [X] T017 [P] [US3] Create
      `apps/admin/src/components/knowledge/DocumentDetailPanel.tsx`:
      inline panel (research.md R4) driven by `selectedDocumentId`,
      rendering filename, status (via `StatusBadge`), content type, and
      uploaded/updated/indexed dates, plus — when `status === "failed"` —
      the sanitized `error_message`; offers a Re-index trigger for any
      document whose status is not `"processing"`, worded honestly as
      rebuilding the search index from already-stored content (e.g.
      "Rebuild search index") — never implying it re-reads the source
      file or recomputes chunk boundaries (FR-014–FR-017; research.md
      R1/R11)
- [X] T018 [US3] Extend `apps/admin/src/routes/KnowledgePage.tsx` (T010):
      implement `handleReindex(documentId)` — sets `pendingAction:
      {kind:"reindex", documentId}`, calls `reindexDocument(id)` (T002),
      calls `reloadKnowledge()` and shows feedback scoped to that document
      on both success and failure, always clears `pendingAction` in
      `finally`; wire document selection so choosing a row/name sets
      `selectedDocumentId` and opens `DocumentDetailPanel` (T017)
      (FR-018–FR-020)
- [X] T019 [US3] `apps/admin/src/components/knowledge/DocumentTable.tsx`
      (T008) rows are already selectable buttons (keyboard-operable by
      construction, FR-037); since Re-index lives only in
      `DocumentDetailPanel` (T017) — not duplicated as a row-level
      button, research.md R4 — "disabling only that row's Re-index
      trigger" is satisfied structurally: `DocumentDetailPanel`'s
      `isReindexing` prop is scoped to the *selected* document only, so
      selecting/acting on a different row is always unaffected by
      another document's in-flight re-index (FR-018)

### Tests for User Story 3

- [X] T020 [P] [US3] Component test in
      `apps/admin/tests/knowledge-detail.test.tsx`: opening a failed
      document's detail shows "Failed" as text plus its sanitized message
      (US3 Scenario 1); its available actions include Re-index (US3
      Scenario 2); a ready document's detail shows no failure message and
      is never presented as unusable (FR-016); a processing document's
      detail does not offer Re-index (FR-017, backend `409` avoidance;
      research.md R1)
- [X] T021 [US3] Integration test in
      `apps/admin/tests/knowledge-reindex.test.tsx`: triggering re-index
      disables duplicate submission for that document while leaving other
      documents' actions available (US3 Scenario 3; FR-018); a mocked
      successful re-index refreshes the document's state and health (US3
      Scenario 5; FR-019); a mocked failed re-index on an already-"ready"
      document shows a safe message while that document — and every other
      already-ready document — keeps being presented as ready, never
      broken (US3 Scenario 4; FR-020, SC-005); the failed-document
      recovery flow is operable using the keyboard alone (FR-037)

**Checkpoint**: A tenant can now fully self-recover from a failed upload —
the feature's "no CLI/developer needed" goal is met for re-index.

---

## Phase 6: User Story 4 - Administrator replaces outdated knowledge safely (Priority: P2)

**Goal**: Replacing a document keeps the current one active until the
replacement succeeds, then activates the new version — regardless of the
document's current status (spec Clarifications, 2026-08-20).

**Independent Test**: Replace an existing document with a new file, confirm
the current document stays represented as active while processing, and
confirm the new version becomes active only once it succeeds (spec US4).

### Implementation for User Story 4

- [X] T022 [P] [US4] Create
      `apps/admin/src/components/knowledge/ReplaceDialog.tsx`: native
      `<dialog>` (research.md R5) — file selection plus one lightweight
      confirmation explaining that the current document keeps serving the
      assistant until the replacement succeeds; moves focus to its
      primary control on open and returns focus to the triggering control
      on close (FR-021, FR-022, FR-038)
- [X] T023 [US4] Extend
      `apps/admin/src/components/knowledge/DocumentDetailPanel.tsx`
      (T017): add a Replace trigger for any document regardless of
      status — Ready, Processing, or Failed (spec Clarifications,
      2026-08-20; FR-021) — opening `ReplaceDialog` (T022)
- [X] T024 [US4] Extend `apps/admin/src/routes/KnowledgePage.tsx` (T018):
      implement `handleReplace(documentId, file)` — sets `pendingAction:
      {kind:"replace", documentId}`, calls `replaceDocument(id, file)`
      (T002), on success calls `reloadKnowledge()` and presents the new
      version as the active document, on failure shows a safe message
      while the original document keeps being presented as active and
      usable, always clears `pendingAction` in `finally` (FR-023–FR-025)

### Tests for User Story 4

- [X] T025 [US4] Integration test in
      `apps/admin/tests/knowledge-replace.test.tsx`: Replace is offered
      for a Ready, a Processing, and a Failed document alike (US4 Scenario
      1; Clarifications 2026-08-20); confirming requires the one
      lightweight confirmation step before the request is sent; duplicate
      replace submission for the same document is prevented while in
      flight (US4 Scenario 2; FR-023); a mocked successful replace
      refreshes list/detail/health and shows the new version as active
      (US4 Scenario 3; FR-024); a mocked failed replace shows a safe
      message while the original document is still presented as active
      and usable (US4 Scenario 4; FR-025, SC-005); the dialog manages
      focus correctly on open and close (FR-038); the whole flow —
      opening Replace through confirming — is operable using the
      keyboard alone (FR-037)

**Checkpoint**: Knowledge can now be kept current over time without ever
risking a mid-replacement gap in what the assistant can answer from.

---

## Phase 7: User Story 5 - Administrator deletes knowledge that is no longer needed (Priority: P2)

**Goal**: Deleting a document requires a deliberate, document-naming
confirmation, then removes it from the active list and refreshes health —
no full page reload.

**Independent Test**: Delete an existing document, confirm the confirmation
step names it by its safe display name, confirm it, and verify it
disappears from the list and the health summary updates (spec US5).

### Implementation for User Story 5

- [X] T026 [P] [US5] Create
      `apps/admin/src/components/knowledge/DeleteDialog.tsx`: native
      `<dialog>` (research.md R5) confirming `Delete "{filename}"?`,
      explaining the assistant will no longer be able to use it once
      deleted, with focus managed on open/close (FR-026, FR-038)
- [X] T027 [US5] Extend
      `apps/admin/src/components/knowledge/DocumentDetailPanel.tsx`
      (T023): add a Delete trigger opening `DeleteDialog` (T026)
- [X] T028 [US5] Extend `apps/admin/src/routes/KnowledgePage.tsx` (T018):
      implement `handleDelete(documentId)` — sets `pendingAction:
      {kind:"delete", documentId}`, disables the delete confirmation
      control while in flight, calls `deleteDocument(id)` (T002), on
      success calls `reloadKnowledge()`, clears `selectedDocumentId` if it
      pointed at the deleted document, and shows success feedback; on
      failure shows a safe generic message without treating a "not found"
      response as proof another tenant's document exists (FR-026–FR-029)

### Tests for User Story 5

- [X] T029 [US5] Integration test in
      `apps/admin/tests/knowledge-delete.test.tsx`: delete requires the
      explicit confirmation step, which identifies the document by its
      filename (US5 Scenario 1; FR-026); the confirmation control is
      disabled while the request is in flight, preventing duplicate
      submission (US5 Scenario 2; FR-027); a mocked successful delete
      removes the document from the list and refreshes health without a
      full reload (US5 Scenario 3; FR-028); a mocked failed delete shows a
      safe, generic message (US5 Scenario 4; FR-029); the confirmation
      dialog is reachable and operable using the keyboard alone, with
      correct focus behavior (FR-037, FR-038)

**Checkpoint**: Full document lifecycle — create, recover, replace, delete
— is now available entirely from the UI.

---

## Phase 8: User Story 6 - A session that expires mid-action is handled safely (Priority: P3)

**Goal**: A knowledge request (initial load or any mutation) that is
rejected for authentication reasons is caught by Feature 013's existing
centralized 401/403 path — no new mechanism, just proof it covers Knowledge
too.

**Independent Test**: While a knowledge mutation is in flight, simulate the
backend rejecting the request for authentication reasons, and confirm the
administrator is returned to login with no stale success dialog and no
knowledge data left visible (spec US6).

### Tests for User Story 6

- [X] T030 [US6] Integration test in
      `apps/admin/tests/knowledge-session-expiration.test.tsx`: mocking
      `global.fetch` directly (not `api/knowledge.ts`, research.md R10) so
      a knowledge request goes through the real `client.ts` →
      `unauthorizedHandler` path and is rejected with `401`; confirms this
      for both the initial page load and a mutation in flight; confirms
      the administrator is redirected to `/login` with the generic
      session-expired message, no dialog left implying the mutation
      succeeded, and no previously-visible knowledge data remaining
      (US6 Scenarios 1–2; FR-032, FR-033)

**Checkpoint**: Session expiration during any knowledge action is proven
safe — no new implementation was needed beyond what Feature 013's
`client.ts`/`AuthProvider` already provide.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T031 [P] Run `npm run build` in `apps/admin/` and confirm the
      production build succeeds with zero errors (SC-009)
- [X] T032 [P] Run ESLint and `tsc -b` across `apps/admin/` and fix any
      findings (SC-009)
- [X] T033 [P] Update the "Admin frontend" section of the root
      `README.md` (added by Feature 013) to describe `/app/knowledge` as
      the functional Knowledge Base UI rather than a placeholder
- [X] T034 Run the full existing backend automated suite (`uv run pytest`,
      `uv run ruff check .`, `uv run mypy src tests`) and confirm every
      pre-existing test/gate still passes unmodified (FR-040, FR-041,
      SC-010)
- [X] T035 Manually execute
      `specs/014-knowledge-base-ui/quickstart.md` end-to-end against the
      live local backend and frontend dev server (spec Live Quickstart) —
      this run surfaced a real bug (T037) that no automated test caught
- [X] T036 [P] Responsive/visual check: confirm the Knowledge page
      (health summary, document list, detail panel, dialogs) remains
      usable at a common laptop width (~1366px) and a common tablet width
      (~768px) via browser dev-tools device emulation, matching Feature
      013's own precedent check (FR-039) — verified together with T035
      via Playwright screenshots at both widths, zero horizontal overflow
- [X] T037 Fix `src/shiruno/main.py`'s CORS `allow_methods` (Feature
      013's original `["GET", "POST"]` never anticipated a browser
      `DELETE` request): add `"DELETE"`, and extend
      `tests/unit/test_cors_configuration.py` with an assertion covering
      all three methods so this can't silently regress (research.md R12;
      discovered by T035's live QA — the CORS preflight for delete
      returned 400, which unit/component tests can't catch since they
      never exercise a real browser's preflight mechanism)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None — no tasks.
- **Foundational (Phase 2)**: BLOCKS every user story. Contains the
  `client.ts` extensions (T001), the `knowledge.ts` API module (T002), the
  shared `StatusBadge` (T003), and the route wired to a data-fetching
  substrate (T004–T006).
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (extends the
  `UploadControl`/`KnowledgePage` files US1 creates).
- **User Story 3 (Phase 5)**: Depends on Foundational + US1 (extends
  `KnowledgePage`/`DocumentTable`); independent of US2.
- **User Story 4 (Phase 6)**: Depends on Foundational + US3 (extends
  `DocumentDetailPanel`/`KnowledgePage` US3 creates); independent of US2.
- **User Story 5 (Phase 7)**: Depends on Foundational + US3 (extends
  `DocumentDetailPanel`/`KnowledgePage`); independent of US2, US4.
- **User Story 6 (Phase 8)**: Depends on Foundational + at least one
  mutation existing to test against (US2 or later); test-only, no new
  implementation.
- **Polish (Phase 9)**: Depends on all desired stories being complete.

### Within Each User Story

- Implementation tasks precede their test tasks throughout, since every
  story's tests exercise real new behavior (unlike Feature 013's US2/US3/
  US5, which only verified Foundational's already-built mechanism, this
  feature's every story adds new UI/state).
- Tasks touching the same file within a phase (e.g., `KnowledgePage.tsx`
  in T010 then T014/T018/T024/T028, or `DocumentDetailPanel.tsx` in T017
  then T023/T027) are sequential by construction — each later task
  extends what an earlier phase or story already created.

### Parallel Opportunities

- T003 (Foundational) is independent of T001/T002/T004–T006 and can run
  alongside them once the phase starts.
- T007, T008, T009 (US1) are independent files and can run in parallel;
  T013 (US1's tenant-boundary unit test) is independent of T011/T012 and
  can run in parallel with them.
- T017 (US3, `DocumentDetailPanel.tsx`) and T020 (US3's detail test) are
  independent of the `DocumentTable`/`KnowledgePage` edits in T018/T019.
- T022 (US4, `ReplaceDialog.tsx`) and T026 (US5, `DeleteDialog.tsx`) are
  fully independent files and can be built in parallel with each other —
  though their respective stories' `DocumentDetailPanel`/`KnowledgePage`
  extensions remain sequential within each story.
- T031, T032, T033, T036 (Polish) touch independent concerns/files and can
  run in parallel; T034 (the full backend regression run) and T035 (manual
  quickstart) are each independent of the other three but heavier, best
  run on their own.

---

## Parallel Example: User Story 1

```bash
# Launch these together once Foundational (T001-T006) is done — different files:
Task: "Create apps/admin/src/components/knowledge/HealthSummary.tsx"
Task: "Create apps/admin/src/components/knowledge/DocumentTable.tsx"
Task: "Create apps/admin/src/components/knowledge/UploadControl.tsx"
```

---

## Implementation Strategy

### MVP First (User Stories 1–3 Only)

1. Complete Phase 1: Setup (no tasks)
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1 — **STOP and VALIDATE**: confirm health/
   list render real tenant data end-to-end against a real local backend
4. Complete Phase 4: User Story 2 — confirm upload → Ready works
5. Complete Phase 5: User Story 3 — confirm a failed document can be
   re-indexed back to Ready without CLI help
6. This alone already delivers the feature's core value (spec's own Goal:
   "recover from failed indexing without developer/CLI assistance" is met
   the moment US3 lands)

### Incremental Delivery

1. Setup + Foundational → the shared API/route substrate exists
2. US1 → real health/list data visible → **first checkpoint with real
   value**
3. US2 → knowledge can be created, not just viewed
4. US3 → knowledge can be self-recovered, not just created — the P1 MVP
   loop is complete
5. US4 → knowledge can be kept current safely
6. US5 → knowledge can be retired
7. US6 (P3) → session-expiration safety net proven, whenever convenient
8. Polish → build/lint/backend-regression gates, docs, live quickstart,
   responsive check

### Recommended Team Strategy

Given how much of this feature shares `KnowledgePage.tsx` and
`DocumentDetailPanel.tsx` across stories (US1/US3 create them, US2/US4/US5
each extend them further), this feature is better suited to sequential
single-developer implementation in priority order than parallel
multi-developer staffing — the exception is the handful of genuinely
independent new files noted under Parallel Opportunities above (e.g.
`ReplaceDialog.tsx` and `DeleteDialog.tsx` can be built by two people at
once once US3 lands, since both only ever get wired into
`DocumentDetailPanel.tsx` afterward, not built inside it).

---

## Notes

- `[P]` tasks touch different files with no dependency on an incomplete
  task in the same phase; tasks that extend a file an earlier phase or
  story already created are deliberately left sequential.
- `[Story]` labels map every user-story-phase task back to spec.md's
  US1–US6 for traceability.
- Only one task touches `src/shiruno/`: T037's one-line, additive CORS fix
  (research.md R12), surfaced by T035's live QA and not knowable at
  planning time — every other task is frontend-only, and the full backend
  regression suite (T034) confirms nothing else changed (FR-041).
- Commit after each task or logical group; verify tests fail before their
  corresponding implementation task lands, where a test task follows its
  implementation task in the same phase.
- No constitution gate is pending — Principle XIV's frontend stack was
  already approved for `apps/*` by Feature 013's v4.2.0 amendment, and
  this feature introduces no new technology (plan.md Constitution Check).
