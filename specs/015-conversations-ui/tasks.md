# Tasks: Conversations UI

**Input**: Design documents from `/specs/015-conversations-ui/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — spec.md's own Success Criteria (SC-001–SC-011) explicitly
require automated verification for nearly every one ("verified by automated
test(s)"), and research.md R12 defines the exact mechanism (Vitest + Testing
Library, `api/conversations.ts` mocked at the module boundary, no real
backend/network) — the same discipline Feature 013/014 already established
and constitution Principle XI ("Frontend quality gates") requires.

**Organization**: Tasks are grouped by user story from spec.md, in priority
order. US1–US2 are P1 (browse the list, inspect one conversation in full —
together the complete "understand real assistant usage" MVP loop); US3–US4
are P2 (narrow the list, page through it); US5 (session expiration mid-browse)
is the sole P3, and reuses Feature 013's already-built centralized mechanism
rather than adding new behavior — identical in shape to Feature 014's US6.

**Cross-story sequencing note**: US1's Independent Test deliberately uses a
tenant that *already has* conversation history, so it never depends on any
later story to be testable. US2 (detail) extends the same
`ConversationsPage.tsx` file US1 builds, adding a `selectedConversationId` /
`detailStatus` branch alongside — not a stub, since nothing in US1 needs a
detail affordance to exist first. US3 (filters) and US4 (pagination) each
extend `ConversationsPage.tsx` further with their own independent pieces of
request-building state; both are fully usable and testable read-only
refinements of the US1/US2 baseline, mirroring how Feature 014's US4/US5
extended `DocumentDetailPanel.tsx`/`KnowledgePage.tsx` without touching each
other's concerns.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task in the same phase)
- **[Story]**: Which user story this task belongs to (US1–US5, matching
  spec.md)
- Every task names its exact file path(s)

## Path Conventions

Extends the existing `apps/admin/` frontend from Feature 013/014 (plan.md
Structure Decision) — no new project, and `src/shiruno/` (backend) is not
touched by any task in this feature (plan.md research.md R1: no new
endpoint, no backend gap found).

---

## Phase 1: Setup

No setup tasks are required. This feature extends the existing
`apps/admin/` scaffold from Feature 013/014 in place — no new dependency,
tool, or project scaffolding is introduced (plan.md Technical Context: zero
new frontend dependencies, zero `client.ts` changes).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The frontend types mirroring Feature 011's contract, the new
`conversations.ts` API module every story calls into, the shared
outcome-label mapping and focus-management hook, and the route itself wired
to a (not-yet-data-rendering) page substrate.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 Extend `apps/admin/src/api/types.ts`: add `ConversationOutcome`
      (the five backend values), `ConversationSummary`,
      `ConversationListResponse`, `ConversationListParams`,
      `ConversationSource`, `SafeFailureCategory`, `ConversationDetail`
      exactly per data-model.md — deliberately omitting `provider_metrics`
      and any `tenant_id` field from every type (research.md R4; FR-037,
      FR-041)
- [X] T002 Create `apps/admin/src/api/conversations.ts`:
      `listConversations(params: ListConversationsParams = {})` — builds a
      query string via `URLSearchParams`, appending `q`/`outcome`/
      `start_date`/`end_date`/`limit`/`offset` only when each is defined/
      non-empty — and `getConversation(id)`, both via `request()` from
      `client.ts` (T001's types; `client.ts` itself is unchanged, research.md
      R2); no function accepts or constructs a tenant identifier (research.md
      R3; FR-039, FR-041)
- [X] T003 [P] Create
      `apps/admin/src/components/conversations/outcomeLabel.ts`: a
      `Record<string, string>` lookup mapping `grounded` → "Answered",
      `insufficient_information` → "Knowledge gap", `out_of_scope` → "Out of
      scope", `unavailable` → "Assistant unavailable", `small_talk` → "Small
      talk", with any other value falling back to "Unknown" — mirrors the
      existing, already-reviewed `statusLabel.ts` shape exactly (research.md
      R7; FR-007, FR-009)
- [X] T004 [P] Create `apps/admin/src/hooks/usePanelFocus.ts`: on `isOpen`
      transitioning to `true`, records `document.activeElement` and moves
      focus to a provided heading ref (`tabIndex={-1}`); on `isOpen`
      transitioning to `false`, restores focus to the recorded element —
      mirrors `useDialogElement.ts`'s explicit focus-save/restore logic
      without any `<dialog>`/modal semantics, since the panel must stay a
      plain non-modal section (research.md R5, R6; FR-047)
- [X] T005 Create `apps/admin/src/routes/ConversationsPage.tsx`: page-level
      state substrate per data-model.md "Frontend-only presentation state"
      (`status: "loading" | "loaded" | "error"`, `items`, `total`,
      `limit = 20`, `offset = 0`, `search`, `outcomeFilter: "all"`,
      `dateFrom`, `dateTo`, `selectedConversationId`, `detailStatus`,
      `detail`); a `loadConversations()` function calling
      `listConversations()` (T002) with the current filter/offset state,
      called once on mount via `useEffect`; renders only
      `LoadingState`/`ErrorMessage` scaffolding for now — list/filter/
      detail/pagination rendering is built in later stories (depends on T002)
- [X] T006 Wire `apps/admin/src/routeConfig.tsx`: replace the
      `'conversations'` child route's `ConversationsPlaceholder` element
      with `ConversationsPage` (T005)
- [X] T007 Delete `apps/admin/src/routes/ConversationsPlaceholder.tsx`
      (superseded by T005/T006)

**Checkpoint**: Foundation ready — every user story below can now begin.

---

## Phase 3: User Story 1 - Administrator sees how visitors are using the assistant (Priority: P1) 🎯 MVP

**Goal**: Opening Conversations shows a real, newest-first list of recent
interactions — question, human-readable outcome, time — sourced from the
tenant's own data, with explicit loading and error-with-retry states, and an
intentional empty state when the tenant has none at all.

**Independent Test**: Log in as a tenant administrator with existing
conversation records, open Conversations, and confirm the list reflects that
tenant's real, newest-first data (spec US1).

### Implementation for User Story 1

- [X] T008 [P] [US1] Create
      `apps/admin/src/components/conversations/OutcomeBadge.tsx`: renders an
      outcome via `outcomeLabel()` (T003) as text, never conveyed by color
      alone (FR-008)
- [X] T009 [P] [US1] Create
      `apps/admin/src/components/conversations/ConversationList.tsx`: table
      with columns Question / Outcome (via `OutcomeBadge`, T008) / Time (+
      latency where useful), rendering `items` in the exact order received
      (FR-001, FR-002) — never re-sorted client-side; each row is a
      selectable button invoking an `onSelect(id)` prop (mirrors
      `DocumentTable.tsx`'s existing selectable-row/`aria-current` pattern);
      never renders the full answer, a tenant identifier, or raw provider
      data (FR-003)
- [X] T010 [US1] Extend `apps/admin/src/routes/ConversationsPage.tsx` (T005):
      render `LoadingState` while `status === "loading"`; render
      `ErrorMessage` plus a retry button (re-invokes `loadConversations()`)
      while `status === "error"`; once `status === "loaded"`, render
      `ConversationList` (T009) when `items.length > 0`, else an intentional
      "No conversations yet." empty-state message (FR-004–FR-006)

### Tests for User Story 1

- [X] T011 [US1] Add `renderConversationsPage()` to
      `apps/admin/tests/testUtils.tsx` — mirrors the existing
      `renderKnowledgePage()` (research.md R12); component test in
      `apps/admin/tests/conversations-list.test.tsx`: mocking
      `api/conversations.ts`, confirms an explicit loading state renders
      before data arrives, then the loaded list renders each mocked item's
      question, human-readable outcome label (never the raw enum string),
      and timestamp, preserving the mocked server order without re-sorting
      (FR-001–FR-003, FR-007; US1 Scenarios 1–2)
- [X] T012 [US1] Component test in
      `apps/admin/tests/conversations-empty-states.test.tsx`: an empty
      `listConversations()` response with no filters active renders "No
      conversations yet." (FR-005; US1 Scenario 3)
- [X] T013 [US1] Integration test in
      `apps/admin/tests/conversations-list.test.tsx`: a rejected initial
      load renders a safe, generic error with a retry action — never stale
      or empty data presented as if the request succeeded; retry re-issues
      the request and can then succeed (FR-006; US1 Scenario 4)
- [X] T014 [P] [US1] Unit test in
      `apps/admin/tests/api-conversations-client.test.ts`: mocking the
      underlying request path, confirms `listConversations()` called with no
      params issues `GET /api/v1/admin/conversations` with no query string,
      and `getConversation(id)` issues
      `GET /api/v1/admin/conversations/{id}`; confirms neither function
      accepts or sends a tenant identifier anywhere in the URL, headers, or
      body (FR-039, FR-041)

**Checkpoint**: An administrator can open Conversations and see their real,
newest-first list data — the feature's baseline read value already exists.

---

## Phase 4: User Story 2 - Administrator inspects one conversation in full (Priority: P1)

**Goal**: Selecting a conversation loads its full detail — question, answer,
outcome, historical sources, operational metadata — independently of the
list, and closing it returns to the list exactly as it was.

**Independent Test**: From a loaded list, select a grounded conversation and
confirm its detail shows question/answer/outcome/sources/metadata exactly as
returned by the detail API, then close it and confirm the list is unchanged
(spec US2).

### Implementation for User Story 2

- [X] T015 [P] [US2] Create
      `apps/admin/src/components/conversations/ConversationDetailPanel.tsx`:
      inline `<section>` (research.md R5, not a `<dialog>`) taking
      `conversation: ConversationDetail`, `status`, and `onClose`; renders a
      heading (ref wired to `usePanelFocus`, T004), the question and answer
      in clearly separated blocks (FR-024), the outcome via `OutcomeBadge`
      (T008) — for `unavailable`, also rendering `safe_failure_category`
      (when non-null) through a small customer-facing mapping (e.g.
      `provider_error`/`budget_exceeded`/`kill_switch`/`concurrency_limit`
      → short safe phrases) alongside the "Assistant unavailable" label,
      never a raw provider exception (FR-033; data-model.md
      "SafeFailureCategory") — the timestamp, a compact operational-metadata
      area (latency, provider, model, input/output tokens — each rendered
      only when non-`null`, absent ones shown naturally, FR-035, FR-036), a
      "Sources"
      section rendered only when `sources` is both non-`null` **and**
      non-empty — an empty array is treated the same as `null` (no Sources
      section at all, never an empty heading with no items) (FR-028–FR-030),
      a collapsed `<details>` "Technical details" containing the copyable
      `request_id`, with a "Copy" control calling
      `navigator.clipboard.writeText(requestId)` (FR-038; research.md R13),
      and a Close button calling `onClose`
- [X] T016 [US2] Extend `apps/admin/src/routes/ConversationsPage.tsx` (T010):
      implement `handleSelect(id)` — sets `selectedConversationId`,
      `detailStatus: "loading"`, calls `getConversation(id)` (T002), on
      success sets `detail` + `detailStatus: "loaded"`, on failure sets
      `detailStatus: "error"` with a safe message that never implies a `404`
      means a cross-tenant conversation exists (FR-026); implement
      `handleCloseDetail()` — clears `selectedConversationId`/`detail`/
      `detailStatus` only, leaving `status`/`items`/`total`/`offset`/
      `search`/`outcomeFilter`/`dateFrom`/`dateTo` untouched (FR-027); render
      `ConversationDetailPanel` (T015) below `ConversationList` (T009) when
      `selectedConversationId` is set, showing `LoadingState`/`ErrorMessage`
      for `detailStatus === "loading"`/`"error"` without blocking the list
      (FR-022, FR-023)

### Tests for User Story 2

- [X] T017 [US2] Component test in
      `apps/admin/tests/conversations-detail.test.tsx`: selecting a row
      loads detail via a mocked `getConversation()` independently of the
      list (the list stays rendered; no page-wide loading state appears); a
      grounded mock's detail shows question and answer clearly separated,
      its Sources section listing the mocked historical labels, and
      operational metadata (latency/provider/model/tokens) in a compact area
      (FR-022–FR-025, FR-028, FR-035; US2 Scenarios 1–3); a second grounded
      mock with `sources: []` renders no Sources section at all — never an
      empty "Sources" heading with no items (FR-029); expanding "Technical
      details" and activating its Copy control calls a stubbed
      `navigator.clipboard.writeText` with the mocked `request_id`
      (FR-038; research.md R13)
- [X] T018 [US2] Component test in
      `apps/admin/tests/conversations-detail.test.tsx`: an
      `insufficient_information` mock renders the "Knowledge gap" state
      without phrasing it as a wrong answer and without fabricated sources
      (FR-031); an `out_of_scope` mock renders a neutral "Out of scope"
      label, not phrased as a failure (FR-032); an `unavailable` mock with a
      non-null `safe_failure_category` renders "Assistant unavailable" plus
      the mapped safe-category text, and a second `unavailable` mock with a
      `null` `safe_failure_category` renders the generic state alone — both
      with no raw provider exception text (FR-033); a small-talk-shaped mock
      (every provider/token field `null`) renders that absence naturally
      with no fabricated zero/placeholder value (FR-034, FR-036; US2
      Scenario 4); a rejected `getConversation()` renders a safe
      detail-level error while the list remains fully rendered and usable,
      never presented as evidence of a cross-tenant record (FR-026; US2
      Scenario 5)
- [X] T019 [US2] Integration test in
      `apps/admin/tests/conversations-detail.test.tsx`: closing the detail
      panel (Close button) clears the selection/detail without altering the
      list's already-loaded items or any active filter/page state (US2
      Scenario 6; FR-027)
- [X] T020 [P] [US2] Accessibility test in
      `apps/admin/tests/conversations-accessibility.test.tsx`: opening
      detail moves focus to the panel's heading; closing it returns focus to
      the row's select button that opened it (FR-047)

**Checkpoint**: An administrator can browse and fully inspect a
conversation — the feature's core "understand real usage" value now exists.

---

## Phase 5: User Story 3 - Administrator narrows the list to find what they're looking for (Priority: P2)

**Goal**: Search, outcome filter, and date range each re-query the backend,
reset pagination, and a filtered-empty result is clearly distinguished from
"no conversations yet," with an easy way to clear filters.

**Independent Test**: Enter a search term and confirm a fresh server-side
query executes; clear it and confirm the full list returns; apply an outcome
filter and a date range and confirm both are sent to the API; confirm each
resets the list to its first page (spec US3).

### Implementation for User Story 3

- [X] T021 [P] [US3] Create
      `apps/admin/src/components/conversations/ConversationFilters.tsx`: a
      labeled `<form onSubmit>` search input + "Search" button (research.md
      R8); a labeled outcome `<select>` with All / Answered / Knowledge gap
      / Out of scope / Unavailable / Small talk options mapping to the five
      backend values (research.md R9; FR-013); two labeled
      `<input type="date">` (From/To) — the "To" value is converted to an
      end-of-day ISO timestamp by a small `toEndOfDayIso(date)` helper before
      being reported upward (research.md R10); when both dates are set and
      From is later than To, `onDateChange` is not invoked and an inline
      validation message is shown instead, so an invalid range is never
      submitted (FR-017); calls `onSearchSubmit(term)`,
      `onOutcomeChange(value)`, `onDateChange({ from, to })` props — no
      network logic of its own
- [X] T022 [US3] Extend `apps/admin/src/routes/ConversationsPage.tsx` (T016):
      wire `ConversationFilters` (T021) — submitting search sets `search` +
      `offset: 0` and reloads (FR-011); clearing the search field and
      resubmitting re-queries the server rather than restoring a cached copy
      (FR-012); changing the outcome select sets `outcomeFilter` + `offset: 0`
      and reloads, omitting the `outcome` param entirely for "All" (FR-013,
      FR-014); changing either date sets `dateFrom`/`dateTo` + `offset: 0`
      and reloads, passing the end-of-day-adjusted value as `end_date`
      (FR-015, FR-016; research.md R10)
- [X] T023 [US3] Extend `apps/admin/src/routes/ConversationsPage.tsx` (T022):
      when the loaded response has zero items **and** at least one filter
      (search/outcome/date) is active, render "No conversations match the
      selected filters." with a "Clear filters" action (resets
      `search`/`outcomeFilter`/`dateFrom`/`dateTo` + `offset: 0` and
      reloads) instead of the unfiltered "No conversations yet." message
      (FR-021)

### Tests for User Story 3

- [X] T024 [US3] Integration test in
      `apps/admin/tests/conversations-search.test.tsx`: submitting a search
      term re-queries `listConversations()` with `q` set to that term —
      never filtering the already-loaded page client-side — and resets to
      the first page; clearing the term and resubmitting re-queries without
      `q` (FR-010–FR-012)
- [X] T025 [US3] Integration test in
      `apps/admin/tests/conversations-outcome-filter.test.tsx`: selecting
      each outcome option calls `listConversations()` with the exact
      corresponding backend enum value in `outcome`; selecting "All" omits
      the `outcome` param entirely; changing the filter resets to the first
      page (FR-013, FR-014)
- [X] T026 [US3] Integration test in
      `apps/admin/tests/conversations-date-filter.test.tsx`: setting From/To
      calls `listConversations()` with `start_date` as the bare date and
      `end_date` as that date's end-of-day timestamp (research.md R10);
      changing either date resets to the first page (FR-015, FR-016);
      setting a From date later than the To date shows an inline validation
      message and never issues a request with that invalid range (FR-017)
- [X] T027 [US3] Component test in
      `apps/admin/tests/conversations-empty-states.test.tsx` (extends T012):
      a zero-item response while a filter is active renders "No
      conversations match the selected filters." — visibly distinct from
      the unfiltered empty state — with a working "Clear filters" action
      that reloads unfiltered from the first page (FR-021; US3
      Scenarios 5–6)
- [X] T028 [P] [US3] Extend
      `apps/admin/tests/api-conversations-client.test.ts` (T014): confirms
      `listConversations()` constructs its query string correctly for
      combinations of `q`/`outcome`/`start_date`/`end_date` (FR-039)

**Checkpoint**: An administrator can narrow the list to a specific question
or time window instead of scrolling full history.

---

## Phase 6: User Story 4 - Administrator pages through a large volume of conversations (Priority: P2)

**Goal**: Previous/Next move through the backend's own bounded pages, with
correct disabled semantics at each end, while every request stays bounded.

**Independent Test**: With enough records to span multiple pages, confirm
Next/Previous load the correct bounded page with the current filter state
preserved, Previous is disabled on the first page, Next is disabled on the
last, and no request is ever unbounded (spec US4).

### Implementation for User Story 4

- [X] T029 [P] [US4] Create
      `apps/admin/src/components/conversations/ConversationPagination.tsx`:
      Previous/Next buttons whose disabled state is driven by `offset === 0`
      (Previous) and `offset + limit >= total` (Next) — communicated through
      an accessible disabled attribute, not styling alone (research.md R11;
      FR-020); calls `onPrevious()`/`onNext()` props
- [X] T030 [US4] Extend `apps/admin/src/routes/ConversationsPage.tsx` (T023):
      wire `ConversationPagination` (T029) — Next increments `offset` by
      `limit` and reloads with the current search/outcome/date state
      preserved; Previous decrements `offset` by `limit` (never below `0`)
      and reloads (FR-018); every `listConversations()` call continues to
      pass a bounded `limit`, so the client never requests an unbounded
      result set (FR-019; research.md R11)

### Tests for User Story 4

- [X] T031 [US4] Integration test in
      `apps/admin/tests/conversations-pagination.test.tsx`: with a mocked
      response reporting more results than one page, Next loads the next
      page while preserving active search/outcome/date state (FR-018);
      Previous returns to the prior page; Previous is disabled on the first
      page and Next is disabled on the last page, each via an accessible
      disabled mechanism, not styling alone (FR-020); every request issued
      across these interactions includes a bounded `limit` value (FR-019,
      SC-006)

**Checkpoint**: An administrator can page through a tenant's full
conversation history without ever triggering an unbounded request.

---

## Phase 7: User Story 5 - A session that expires mid-browse is handled safely (Priority: P3)

**Goal**: A conversations request (initial load, search, filter, date range,
pagination, or detail) that is rejected for authentication reasons is caught
by Feature 013's existing centralized 401/403 path — no new mechanism, just
proof it covers Conversations too.

**Independent Test**: While a list or detail request is in flight, simulate
the backend rejecting it for authentication reasons, and confirm the
administrator is redirected to login with no conversation content left
visible (spec US5).

### Tests for User Story 5

- [X] T032 [US5] Integration test in
      `apps/admin/tests/conversations-session-expiration.test.tsx`: mocking
      `global.fetch` directly (not `api/conversations.ts`, research.md
      R12/matching `knowledge-session-expiration.test.tsx`'s existing
      precedent) so a conversations request goes through the real
      `client.ts` → `unauthorizedHandler` path and is rejected with `401`;
      confirms this for both the initial list load and an in-flight detail
      request; confirms the administrator is redirected to `/login` with no
      question, answer, or list row remaining visible afterward (US5
      Scenarios 1–2; FR-042, FR-043)

**Checkpoint**: Session expiration during any Conversations interaction is
proven safe — no new implementation was needed beyond what Feature 013's
`client.ts`/`AuthProvider` already provide.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T033 [P] Run `npm run build` in `apps/admin/` and confirm the
      production build succeeds with zero errors (SC-010)
- [X] T034 [P] Run ESLint and `tsc -b` across `apps/admin/` and fix any
      findings (SC-010)
- [X] T035 [P] Update the "Admin frontend" section of the root `README.md`
      to describe `/app/conversations` as the functional Conversations UI
      rather than a placeholder
- [X] T036 Run the full existing backend automated suite (`uv run pytest`,
      `uv run ruff check .`, `uv run mypy src tests`) and confirm every
      pre-existing test/gate still passes unmodified — this feature makes no
      backend change at all (FR-050, FR-051, SC-011)
- [X] T037 Manually execute
      `specs/015-conversations-ui/quickstart.md` end-to-end against the live
      local backend and frontend dev server (spec Live Quickstart)
- [X] T038 [P] Responsive/visual check: confirm the Conversations page
      (filters, list, pagination, detail panel) remains usable at a common
      laptop width (~1366px) and a common tablet width (~768px) via browser
      dev-tools device emulation (FR-048) — verified together with T037
- [X] T039 Extend `apps/admin/tests/conversations-accessibility.test.tsx`
      (T020) with an automated `user-event` keyboard-navigation test: `Tab`
      reaches the search input, outcome select, both date inputs, every
      visible conversation row, and Previous/Next, and `Enter`/`Space`
      activates each (search submits, a row opens detail, Next/Previous
      pages) — satisfying SC-008's "verified by automated tests" commitment
      for FR-045/FR-046, not just T020's narrower focus-management scope; a
      quick manual spot-check alongside T037's live quickstart remains a
      useful supplement but is no longer the primary verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None — no tasks.
- **Foundational (Phase 2)**: BLOCKS every user story. Contains the frontend
  types (T001), the `conversations.ts` API module (T002), the shared
  `outcomeLabel` mapping (T003) and `usePanelFocus` hook (T004), and the
  route wired to a data-fetching substrate (T005–T007).
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (extends the
  `ConversationsPage.tsx`/`ConversationList.tsx` files US1 creates, and
  reuses `OutcomeBadge` from T008).
- **User Story 3 (Phase 5)**: Depends on Foundational + US1/US2 (extends
  `ConversationsPage.tsx`); independent of US4's pagination concern.
- **User Story 4 (Phase 6)**: Depends on Foundational + US3 (extends the
  same `ConversationsPage.tsx` filter-reload logic US3 builds so pagination
  correctly preserves active filters); independent of US2's detail concern.
- **User Story 5 (Phase 7)**: Depends on Foundational + at least one request
  path existing to test against (US1's list load, US2's detail load);
  test-only, no new implementation.
- **Polish (Phase 8)**: Depends on all desired stories being complete.

### Within Each User Story

- Implementation tasks precede their test tasks throughout, since every
  story's tests exercise real new behavior.
- Tasks touching the same file within a phase (e.g., `ConversationsPage.tsx`
  in T010 then T016/T022/T023/T030, or `ConversationDetailPanel.tsx` created
  once in T015) are sequential by construction — each later task extends
  what an earlier phase or story already created.

### Parallel Opportunities

- T003 and T004 (Foundational) are independent of T001/T002/T005–T007 and
  can run alongside them once the phase starts.
- T008 and T009 (US1) are independent files and can run in parallel; T014
  (US1's API-client unit test) is independent of T011–T013 and can run in
  parallel with them.
- T015 (US2, `ConversationDetailPanel.tsx`) and T020 (US2's accessibility
  test) are independent of each other's file until T016 wires them together.
- T021 (US3, `ConversationFilters.tsx`) and T029 (US4,
  `ConversationPagination.tsx`) are fully independent files and can be built
  in parallel with each other — though their respective
  `ConversationsPage.tsx` wiring (T022/T023 and T030) remains sequential
  within each story.
- T033, T034, T035, T038 (Polish) touch independent concerns/files and can
  run in parallel; T036 (the full backend regression run) and T037 (manual
  quickstart) are each independent of the other tasks but heavier, best run
  on their own; T039 is no longer marked `[P]` — it's now an automated test
  that depends on `ConversationsPage.tsx` and every US1–US4 control already
  existing, so it should run after those stories are complete rather than
  alongside the rest of Polish.

---

## Parallel Example: User Story 1

```bash
# Launch these together once Foundational (T001-T007) is done — different files:
Task: "Create apps/admin/src/components/conversations/OutcomeBadge.tsx"
Task: "Create apps/admin/src/components/conversations/ConversationList.tsx"
```

---

## Implementation Strategy

### MVP First (User Stories 1–2 Only)

1. Complete Phase 1: Setup (no tasks)
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1 — **STOP and VALIDATE**: confirm the real
   newest-first list renders against a real local backend
4. Complete Phase 4: User Story 2 — confirm selecting a conversation shows
   its full question/answer/outcome/sources/metadata and closing preserves
   list state
5. This alone already delivers the feature's core value (spec's own Goal:
   "understand real assistant usage... without exposing low-level RAG
   internals" is met the moment US2 lands)

### Incremental Delivery

1. Setup + Foundational → the shared API/route substrate exists
2. US1 → real newest-first list visible → **first checkpoint with real
   value**
3. US2 → full conversation detail visible — the P1 MVP loop is complete
4. US3 → the list can be narrowed by search/outcome/date
5. US4 → the full tenant history is reachable via pagination
6. US5 (P3) → session-expiration safety net proven, whenever convenient
7. Polish → build/lint/backend-regression gates, docs, live quickstart,
   responsive/accessibility checks

### Recommended Team Strategy

Given how much of this feature shares `ConversationsPage.tsx` across
stories (US1 creates its substrate; US2/US3/US4 each extend it further),
this feature is better suited to sequential single-developer implementation
in priority order than parallel multi-developer staffing — the exception is
the handful of genuinely independent new files noted under Parallel
Opportunities above (e.g. `ConversationFilters.tsx` and
`ConversationPagination.tsx` can be built by two people at once once US2
lands, since both only ever get wired into `ConversationsPage.tsx`
afterward, not built inside it).

---

## Notes

- `[P]` tasks touch different files with no dependency on an incomplete task
  in the same phase; tasks that extend a file an earlier phase or story
  already created are deliberately left sequential.
- `[Story]` labels map every user-story-phase task back to spec.md's
  US1–US5 for traceability.
- No task touches `src/shiruno/` — unlike Feature 014, this feature's
  research.md R1 found no backend gap at all; T036's full backend regression
  run exists purely to confirm nothing was inadvertently affected (FR-050,
  FR-051).
- Commit after each task or logical group; verify tests fail before their
  corresponding implementation task lands, where a test task follows its
  implementation task in the same phase.
- No constitution gate is pending — Principle XIV's frontend stack was
  already approved for `apps/*` by Feature 013's v4.2.0 amendment, and this
  feature introduces no new technology (plan.md Constitution Check).
