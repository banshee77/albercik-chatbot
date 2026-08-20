# Phase 0 Research: Conversations UI

No `NEEDS CLARIFICATION` markers remain in `spec.md` (confirmed during
`/speckit-clarify`), so this phase resolves implementation-shape questions
the spec deliberately deferred to planning, grounded in the actual current
state of `src/shiruno/api/routers/conversations.py`,
`specs/011-conversations-analytics/contracts/conversations-api.md`,
`specs/011-conversations-analytics/data-model.md`, and the existing
`apps/admin/src/` Feature 013/014 code.

## R1: No new backend endpoint or contract change

**Decision**: Consume `GET /api/v1/admin/conversations` and
`GET /api/v1/admin/conversations/{conversation_id}` exactly as implemented
today. No backend file is touched by this feature.

**Rationale**: Both routes already exist, are tenant-scoped via
`get_current_administrator` + `get_current_tenant`, and return exactly the
fields the spec requires (FR-001 through FR-041 cross-checked against
`contracts/conversations-api.md` line-by-line: `id`, `request_id`,
`question`, `answer`, `outcome`, `created_at`, `latency_ms`, `sources`,
`provider_name`, `provider_model`, `input_tokens`, `output_tokens`,
`provider_metrics`, `safe_failure_category`). Unlike Feature 014 (which
needed an additive CORS fix), no gap exists here — `DELETE` isn't used by
this read-only feature, and `GET` was already allowed for Feature 013.

**Alternatives considered**: Adding a `has_next` field to the list response
— rejected; the client can derive it from `total`, `limit`, and `offset`
(already present) without a backend change (constraint: "avoid backend
changes" unless a genuine gap exists).

## R2: No `api/client.ts` changes needed

**Decision**: `conversations.ts` builds its query string with
`URLSearchParams` and calls the existing `request<T>(path, init)` exactly
as `knowledge.ts` does for its `GET` calls — no multipart body, no `204`
response, so neither of Feature 014's two `client.ts` extensions (R2 in
that feature) is relevant here.

**Rationale**: Every Conversations request is a plain authenticated `GET`;
`client.ts` already attaches the bearer token, maps 401/403 to the
centralized session-expiration handler, and returns a safe generic message
on network/server failure (FR-042, FR-006, FR-026) with zero new code.

## R3: `apps/admin/src/api/conversations.ts` mirrors `knowledge.ts`

**Decision**:

```ts
export interface ListConversationsParams {
  q?: string
  outcome?: ConversationOutcome
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export async function listConversations(
  params: ListConversationsParams = {},
): Promise<ConversationListResponse> { … }

export async function getConversation(id: string): Promise<ConversationDetail> { … }
```

**Rationale**: Same thin-async-function-over-`request()` shape already
established by `knowledge.ts` and `admin.ts` (FR-039). `ListConversationsParams`
omits `tenant_id` entirely — there is no field a caller could set to select
a tenant (FR-041 satisfied structurally, not just by convention).

## R4: `provider_metrics` is never part of the frontend `ConversationDetail` type

**Decision**: The TypeScript `ConversationDetail` interface deliberately
does **not** declare a `provider_metrics` field, even though the backend
JSON response includes one (contracts/conversations-api.md line 72). No
frontend code ever reads `.provider_metrics`.

**Rationale**: FR-037 requires raw `provider_metrics` is never rendered.
Omitting it from the type is a stronger, structural guarantee than "just
don't render it" — no component can accidentally reference a field
TypeScript doesn't know exists, and a future edit that tried to display it
would need to first (re-)add the field, making the violation visible in
review. This is the same "keep frontend types aligned with the public API,
not an excuse to mirror every backend field" instruction FR-040 already
states.

## R5: Detail presentation — inline panel below the list (Feature 014 pattern), not a new side-panel layout

**Decision**: `ConversationDetailPanel` renders as a plain `<section>`
appended below `ConversationList` inside `ConversationsPage` — the same
structural pattern as `KnowledgePage.tsx` → `DocumentDetailPanel`. It is
**not** a CSS grid "list | side panel" two-column layout, and not a
`<dialog>`.

**Rationale**: The spec's own Assumptions section defers this exact choice
to planning "based on what best fits... Feature 014's precedent." Feature
014's actual implementation (verified: `DocumentDetailPanel` is a plain
`<section>`, not a dialog or a CSS-grid panel) already satisfies every
requirement the brief's "side panel / drawer" language was chasing — list
stays visible and interactive, detail loads independently, closing returns
to unchanged list state — without introducing new layout CSS or a new
interaction pattern this codebase doesn't already have. Reusing it keeps
this feature a pure additive extension, consistent with Simplicity
(Principle XIII) exactly as Feature 014 argued for the same choice.

**Alternatives considered**: A true two-column side-panel (CSS grid/flex,
list left, detail right) — rejected as unnecessary new layout work for an
MVP with no existing precedent; a modal `<dialog>` via `showModal()` —
rejected because that traps focus and makes the background inert, directly
contradicting the requirement that "the list MUST remain visible and
usable" while detail is open (FR-022).

## R6: New `usePanelFocus` hook for the inline detail panel's focus management

**Decision**: Add `apps/admin/src/hooks/usePanelFocus.ts`, a small hook
mirroring the existing `useDialogElement.ts` pattern but for a plain
(non-`<dialog>`) section: on open, it focuses the panel's heading
(`tabIndex={-1}` on an `<h2>` ref) and records `document.activeElement`;
on close, it restores focus to that recorded element (the row's select
button in `ConversationList`).

**Rationale**: FR-047 requires the detail view to "move focus into itself
intentionally when opened" and "return focus appropriately when closed" —
a stricter requirement than Feature 014 actually implements for its own
inline `DocumentDetailPanel` (verified: no focus management exists there
today; only the nested Replace/Delete `<dialog>`s use `useDialogElement`).
Since R5 rules out a real `<dialog>` for the panel itself (focus-trapping
would block the list), the existing `useDialogElement` hook cannot be
reused as-is — it hard-codes `dialog.showModal()`/`dialog.close()`. A
small sibling hook that keeps only the focus-in/focus-out behavior (no
modal semantics) is the minimal addition that satisfies FR-047 without
introducing a focus-trap library or duplicating `useDialogElement`'s
`<dialog>`-specific calls.

**Alternatives considered**: Reusing `useDialogElement` by wrapping the
panel in a non-modal `<dialog>` shown via `.show()` instead of
`.showModal()` — rejected: non-modal `<dialog>` still requires the same
polyfill complexity in `tests/setup.ts` for a semantic (`<dialog>` outside
a modal flow) this codebase doesn't otherwise use, and buys nothing over a
plain `<section>` + a focused ref, which is simpler and requires no jsdom
polyfill changes.

## R7: Outcome label mapping — new `outcomeLabel.ts`, mirrors `statusLabel.ts`

**Decision**: Add `apps/admin/src/components/conversations/outcomeLabel.ts`:

```ts
const OUTCOME_LABELS: Record<string, string> = {
  grounded: 'Answered',
  insufficient_information: 'Knowledge gap',
  out_of_scope: 'Out of scope',
  unavailable: 'Assistant unavailable',
  small_talk: 'Small talk',
}
const FALLBACK_LABEL = 'Unknown'
export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABELS[outcome] ?? FALLBACK_LABEL
}
```

**Rationale**: Exact same shape as the existing, already-reviewed
`statusLabel.ts` (FR-007, FR-009) — a plain lookup with a safe fallback for
an outcome value the frontend doesn't recognize, reused by both the list
row and the detail view so the mapping only exists once.

## R8: Search — explicit submit, not debounced

**Decision**: The question search is a `<form onSubmit>` containing one
labeled `<input type="search">` and a "Search" button (Enter also
submits). Submitting reloads the list with `q` set and `offset` reset to
`0`; there is no debounce timer.

**Rationale**: The spec explicitly allows either "submitted intentionally
or with a simple debounced strategy if planning justifies it" (spec.md
§4). This codebase has no existing debounce utility, and introducing one
(a `useDebouncedValue` hook, a timer to clean up, and the associated test
complexity of advancing fake timers) is unjustified complexity for an MVP
whose own success criteria only require "one filtering action" (SC-001) —
not necessarily a keystroke-driven one. Explicit submit is the simpler
choice under Simplicity (Principle XIII) and needs no `setTimeout`
cleanup in tests.

## R9: Outcome filter and date range apply immediately on change

**Decision**: The outcome filter is a native `<select>` whose `onChange`
immediately reloads the list (offset reset to `0`). The date range is two
native `<input type="date">` elements whose `onChange` immediately reloads
the list (offset reset to `0`) — no separate "Apply" button.

**Rationale**: Unlike free-text search, a `<select>` change and a native
date-picker's `onChange` already represent one discrete, intentional user
action (not a per-keystroke event), so there's no debounce concern to
justify a submit step. This matches the spec's own layout sketch (`[
Outcome ▼ ] [ Date range ▼ ]` as filters, distinct from the search box's
explicit `[ Search questions... ]` field).

## R10: "To" date is sent as end-of-day, not midnight

**Decision**: When the administrator selects a "To" date (e.g.
`2026-08-20`), the frontend sends
`end_date=2026-08-20T23:59:59.999` — not the bare date — to the backend.
"From" is sent as the bare date (`2026-08-20`), which the backend/Pydantic
already parses as `2026-08-20T00:00:00`.

**Rationale**: `list_conversations.py` filters with
`ConversationRecord.created_at <= end_date` (verified directly in source).
A bare date string parsed by Pydantic's `datetime` becomes midnight
(`00:00:00`), which would silently exclude every conversation that
happened later that same day — directly contradicting the ordinary
meaning of selecting "20 Aug" as an end date in a date-range picker.
Computing the inclusive end-of-day boundary is a pure frontend
presentation decision (how a date-only UI control maps to the existing
datetime-bound query parameter); it requires no backend change and keeps
the backend's inclusive-bound contract exactly as documented.

## R11: Pagination state — `offset`/`limit` in `ConversationsPage`, Previous/Next derived from `total`

**Decision**: `ConversationsPage` keeps `offset` (default `0`) and a fixed
`limit` (`20`, matching `CONVERSATION_LIST_DEFAULT_PAGE_SIZE`) in React
state. After each load, `Previous` is disabled when `offset === 0`; `Next`
is disabled when `offset + limit >= total` (both computed from the
response's own `total`/`limit`/`offset`, never assumed).

**Rationale**: FR-018 through FR-020 require using the backend's own
pagination mechanism and correct disabled semantics without a pagination
library. `total` is already returned by every list response
(contracts/conversations-api.md), so no extra request or client-side
counting is needed to compute both button states.

## R12: Tests mock `api/conversations.ts` at the module boundary

**Decision**: Every Conversations component/behavior test uses
`vi.mock('../src/api/conversations')`, following exactly the same pattern
`knowledge-*.test.tsx` already uses for `api/knowledge.ts` (Principle XI,
"Frontend quality gates" — no real backend/network/Ollama/Phoenix
dependency). `testUtils.tsx` gains one new `renderConversationsPage()`
helper alongside the existing `renderKnowledgePage()`.

**Rationale**: `ConversationsPage`, like `KnowledgePage`, reads no auth
context directly (`Header`/`Nav` own that via `ProtectedLayout`), so a
direct component render (not a full route render) is sufficient and
avoids unrelated setup, exactly matching the existing
`renderKnowledgePage()` doc comment's own reasoning.

## R13: Request ID copy — plain `navigator.clipboard.writeText`, stubbed per-test

**Decision**: The "Technical details" `<details>` section's copy control
calls `navigator.clipboard.writeText(requestId)` directly — no new
dependency. `@testing-library/user-event`'s `userEvent.setup()` already
installs its own `Clipboard` stub on `navigator.clipboard` (confirmed
empirically: it overrides a plain `navigator.clipboard = {...}`/
`Object.defineProperty` replacement set up before `setup()` runs) — so the
one test exercising copy behavior calls `userEvent.setup()` first, then
`vi.spyOn(navigator.clipboard, 'writeText')` on user-event's own stub,
rather than replacing `navigator.clipboard` itself. `tests/setup.ts`
(shared globally) is not changed.

**Rationale**: `navigator.clipboard.writeText` is a standard, dependency-free
Web API already available in every evergreen browser this project targets
(Technical Context). jsdom itself does not implement the Clipboard API, but
`@testing-library/user-event` — already a project dependency — provides a
working stub the moment `setup()` runs, so spying on it is simpler and more
reliable than fighting its installation order with a manual replacement.
