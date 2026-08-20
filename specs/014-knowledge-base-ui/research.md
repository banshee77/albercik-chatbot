# Phase 0 Research: Knowledge Base UI

**Feature**: `014-knowledge-base-ui` | **Spec**: [spec.md](./spec.md)

## R1. Existing Feature 010 contract — consumed exactly as-is, zero backend changes

**Decision**: This feature makes no backend change at all. It consumes the
existing `/api/v1/documents` surface (`documents.py`,
`specs/010-knowledge-base-admin/contracts/documents-api-delta.md`) exactly
as it exists today:

| Operation | Method & path | Response |
|---|---|---|
| List | `GET /api/v1/documents` | `DocumentSummary[]`, ordered `uploaded_at DESC`, excludes soft-deleted (`deleted_at IS NULL`) |
| Health | `GET /api/v1/documents/health` | `KnowledgeHealthResponse` |
| Detail | `GET /api/v1/documents/{id}` | `DocumentSummary` |
| Upload | `POST /api/v1/documents` (multipart, field `file`) | `DocumentSummary`, `201` |
| Replace | `POST /api/v1/documents/{id}/replace` (multipart, field `file`) | `DocumentSummary`, `201` |
| Re-index | `POST /api/v1/documents/{id}/reindex` | `DocumentSummary`, `200` |
| Delete | `DELETE /api/v1/documents/{id}` | `204`, empty body |

`DocumentSummary`: `id`, `filename`, `content_type`, `status`
(`"processing" | "ready" | "failed"`), `uploaded_at`, `updated_at`,
`indexed_at`, `error_message`. `KnowledgeHealthResponse`: `documents`
(`{total, ready, processing, failed}`), `chunks`, `ready_for_chat`,
`last_indexed_at`. Every field this feature needs (FR-001, FR-014) is
already present — verified directly against `api/schemas.py`.

**Rationale**: Confirms spec's own Assumption ("no new backend endpoint or
database entity is required") against the actual current implementation,
not just the brief. Every error path already returns the safe
`{"detail": "..."}` shape `register_exception_handlers` produces for every
`AppError` subclass, which the existing `api/client.ts` already parses
(research.md R7 of Feature 013) — no new error-mapping code is needed on
the frontend either.

**Alternatives considered**: None — the spec explicitly forbids redesigning
Feature 010 for UI convenience (FR-041), and this research confirms no gap
exists that would require it.

## R2. Centralized client: two required extensions, not a new client

**Decision**: `apps/admin/src/api/client.ts` (Feature 013) gets exactly two
additive extensions, in place — no second HTTP client is introduced:

1. **Multipart bodies.** `request()` currently always sets
   `Content-Type: application/json` unconditionally. Upload and Replace
   need to POST a `FormData` body instead (the browser must set its own
   `multipart/form-data; boundary=...` header — setting `Content-Type`
   manually on a `FormData` request breaks the boundary and the backend's
   `UploadFile` parsing). `request()` is changed to only set
   `Content-Type: application/json` when `init.body` is **not** a
   `FormData` instance; callers passing `FormData` get no forced header,
   letting `fetch` set it.
2. **`204 No Content` responses.** `request()` currently always calls
   `await response.json()` on success, which throws on the DELETE
   endpoint's empty `204` body (a real bug this feature's Delete action
   would hit immediately). `request()` is changed to short-circuit to
   `undefined` on a `204` (or otherwise empty) success response instead of
   parsing JSON.

Both changes are backward-compatible with every existing Feature 013
caller (`auth.ts`, `admin.ts`) — neither sends `FormData` nor expects a
`204`, so their behavior is unchanged.

**Rationale**: FR-030 requires every knowledge request to go through the
existing centralized boundary — "centralized" means extended in place when
a new, legitimate request shape appears, not bypassed with a second
fetch helper. Discovering both gaps now (rather than mid-implementation)
avoids a broken Delete action or a broken Upload action shipping first and
being patched later.

**Alternatives considered**: A separate `multipartRequest()` helper in
`knowledge.ts` — rejected; it would duplicate the token-attachment, 401/403
handling, and error-mapping logic `client.ts` already owns, directly
violating FR-030's "one centralized boundary, not ad-hoc" language and
Feature 013's own R7 rationale.

## R3. `api/knowledge.ts` — one new module, mirrors `auth.ts`/`admin.ts`

**Decision**: `apps/admin/src/api/knowledge.ts` exports exactly the seven
functions the spec's Document Action entity names, each a thin wrapper over
`request()`:

```text
listDocuments(): Promise<DocumentSummary[]>
getKnowledgeHealth(): Promise<KnowledgeHealthResponse>
getDocument(id: string): Promise<DocumentSummary>
uploadDocument(file: File): Promise<DocumentSummary>
replaceDocument(id: string, file: File): Promise<DocumentSummary>
reindexDocument(id: string): Promise<DocumentSummary>
deleteDocument(id: string): Promise<void>
```

`uploadDocument`/`replaceDocument` build a `FormData` with the file under
the field name `file` (matching `UploadFile` parameter name in
`documents.py`) and pass it as `request()`'s body (R2). No function ever
constructs a URL containing a tenant slug/ID or accepts one as a parameter
(FR-031) — tenant scoping is entirely server-derived from the bearer token,
exactly as `admin.ts`'s `getMe()` already works.

**Rationale**: Matches Feature 013's existing `api/` module shape exactly
(one small file per resource, no class, no generic "resource client"
abstraction) — Principle XIII.

## R4. Document detail — inline panel within `/app/knowledge`, no nested route

**Decision**: Document detail is shown as an inline expand/detail panel
within the same `/app/knowledge` page, driven by a `selectedDocumentId`
piece of local page state (not a URL param, not a second route).
Selecting a document (e.g., clicking its row/its name) sets
`selectedDocumentId`; the panel renders that document's already-fetched
`DocumentSummary` from the in-memory list (no second network round-trip
just to open detail, since the list already has every field the detail
view needs — R1's field table shows `getDocument(id)` returns nothing the
list response doesn't already include). `getDocument(id)` is still
implemented (R3) for a future feature that might deep-link to one
document, but the Knowledge page itself does not call it in the MVP flow.

**Rationale**: The spec explicitly defers this presentation-shape decision
to planning (spec Assumptions). A nested route (`/app/knowledge/:id`)
would need route-param parsing, a redirect-if-not-found path, and — per
FR-024 — detail must refresh in place after a replace succeeds, which is
simpler as "re-render the panel from updated list state" than as
"re-fetch a route param's data." An inline panel keeps all Knowledge state
in one component tree, avoids a second loading state to design (FR-036
already requires *not* flashing the whole page for one in-flight action),
and matches Principle XIII (no more routing surface than the feature
needs). Revisit only if a future feature needs a shareable per-document
URL.

**Alternatives considered**: Modal/drawer overlay — rejected as
unnecessary visual weight for what is fundamentally "more detail about a
row already on screen," and inline keeps keyboard/focus flow simpler
(FR-037) since nothing needs to trap focus outside a dialog just to view
metadata (dialogs are reserved for the two flows that actually need
confirmation — R5). Nested route — rejected per rationale above.

## R5. Confirmation dialogs — native `<dialog>`, no custom modal framework

**Decision**: The Replace confirmation and the Delete confirmation both
use the native HTML `<dialog>` element, opened via `showModal()` and
closed via `close()`/the browser's own Escape handling, not a hand-rolled
overlay `<div>` or a new dependency. A dialog receives initial focus on
its first focusable control when opened and returns focus to the control
that triggered it on close (both native `<dialog>` behaviors when using
`showModal()`, needing only a small `ref`-based effect to move focus to
that dialog's primary control) — satisfying FR-038 without hand-building a
focus trap.

**Rationale**: `<dialog>` is supported in every evergreen browser this
project already targets (Feature 013's Target Platform), requires zero new
dependency (Principle XIII, spec's explicit "no heavy design-system
dependency"), and the brief itself names `<dialog>` as an acceptable
mechanism as long as "its accessibility [is implemented] intentionally" —
which `showModal()`'s built-in top-layer/focus semantics make
straightforward compared to reimplementing a modal's ARIA semantics by
hand.

**Alternatives considered**: A custom `role="dialog"` overlay component —
rejected; it would require manually implementing focus trapping,
Escape-to-close, and inert-background semantics that `<dialog>` already
provides natively, for no functional benefit. A confirmation library —
rejected outright as a new dependency for two dialogs.

## R6. Status vocabulary — small fixed map, safe fallback, text-first

**Decision**: One small `statusLabel(status: string): string` mapping
function: `"processing" → "Processing"`, `"ready" → "Ready"`,
`"failed" → "Failed"`, any other value → a generic fallback label (e.g.
`"Unknown"`) rather than guessing (FR-008). The rendered status is always
text (inside the document row and the detail panel) — never conveyed by
background color alone (FR-005); a color-coded visual accent MAY
accompany the text but is never the only signal, satisfying SC's
accessibility requirement without needing an icon library.

**Rationale**: `DocumentStatus` (`persistence/models.py`) is a 3-value
`StrEnum` today (R1) — the fallback branch is defensive/forward-compatible
rather than something the current backend can actually trigger, matching
FR-008's own "do not invent behavior" instruction.

## R7. File-selection constraint — extension hint from a stable constant, size limit deliberately not duplicated

**Decision**: The upload `<input type="file">` sets
`accept=".txt,text/plain"` and the frontend performs one lightweight,
early client-side check — the selected file's name does not end in
`.txt` — showing an inline "Only .txt files are accepted." message
*before* submitting, mirroring `_ingest_content.py`'s own
`_ALLOWED_EXTENSION = ".txt"` constant (a hardcoded constraint with no
settings knob, i.e. genuinely stable). The frontend does **not**
duplicate the byte-size check: `MAX_UPLOAD_SIZE_BYTES` (`config.py`) is an
operator-configurable `Settings` value (env-overridable, default
5,000,000), not a stable constant — hardcoding "5 MB" client-side risks
silently drifting from whatever an operator has actually configured. A
too-large file is instead rejected by the backend's existing
`PayloadTooLargeError` (`413`, safe detail already surfaced by `client.ts`
unchanged), exactly like every other backend-validated case (empty file,
non-UTF-8, no meaningful content).

**Rationale**: Spec Assumptions/FR-013 explicitly forbid inventing
duplicate validation rules not derived from a *stable documented*
constraint — the extension check qualifies (a literal, non-configurable
constant in source); the size limit does not (a configurable setting).
This is the one place this feature's own research diverges from a naive
reading of "mirror the backend" into two different, individually-justified
answers for two constraints that look similar but aren't.

## R8. Data refresh after mutation — explicit reload, no cache library

**Decision**: One small `reloadKnowledge()` function on the Knowledge page
— `Promise.all([listDocuments(), getKnowledgeHealth()])` — called once on
mount and again after every successful mutation (upload, replace,
re-index, delete), replacing the page's `documents`/`health` state
wholesale from the fresh response. No per-item optimistic update, no
partial patch, no cache/invalidation library.

**Rationale**: Exactly the "Preferred MVP" strategy the spec's own brief
names (mutation success → reload list → reload health), and Principle
XIII: React's built-in `useState`/`useEffect` are sufficient for one
page's own data, so React Query/TanStack Query (spec's explicit
Non-Goal) is not introduced. A full reload after each mutation is also
what correctly reflects R11 (`replace_document`'s server-side race
resolution) and R-reindex's "document may or may not have changed
status" without the frontend trying to predict the outcome itself.

## R9. Component layout — `src/components/knowledge/` subfolder

**Decision**: New Knowledge-specific components live under a new
`apps/admin/src/components/knowledge/` subfolder — `HealthSummary.tsx`,
`DocumentTable.tsx`, `DocumentDetailPanel.tsx`, `UploadControl.tsx`,
`ReplaceDialog.tsx`, `DeleteDialog.tsx`, `StatusBadge.tsx` — while
`KnowledgePlaceholder.tsx` is deleted and replaced by
`apps/admin/src/routes/KnowledgePage.tsx` (same `routes/` folder as every
other page, per Feature 013's existing convention), which owns the
page-level state (R8) and composes the `knowledge/` components.

**Rationale**: Feature 013's flat `src/components/` (four small, generic
shell components: `Header`, `Nav`, `LoadingState`, `ErrorMessage`) stays
flat and reusable; this feature's ~7 new, Knowledge-specific components
are cohesive to one page and would otherwise nearly double that directory
with single-purpose files, so a subfolder keeps `components/` navigable
(Principle XII, "keep modules cohesive") without introducing a new
architectural pattern — `LoadingState`/`ErrorMessage` from Feature 013 are
still reused as-is inside the new components, not duplicated.

## R10. Testing approach — mock `api/knowledge.ts`, reuse Feature 013's test harness

**Decision**: Every Knowledge test mocks `apps/admin/src/api/knowledge.ts`
at the module boundary (`vi.mock`, matching every existing Feature 013 test
— `login.test.tsx`, `route-protection.test.tsx`, etc.), never a real
network call. A new small test helper,
`renderKnowledgePage()` in `tests/testUtils.tsx`, renders
`<AuthContext.Provider value={authenticatedValue}><KnowledgePage /></AuthContext.Provider>`
directly — reusing the direct-context-injection pattern
`route-protection.test.tsx` already established for deterministic,
non-async-race test setup — rather than re-running the full login flow in
every Knowledge test file. Session-expiration-during-mutation tests
(US6) mock `global.fetch` directly instead (matching
`session-expiration.test.tsx`'s existing pattern), since that scenario
specifically needs to exercise the real `client.ts` 401/403 →
`unauthorizedHandler` path, not a mocked `knowledge.ts`.

**Rationale**: Reuses two patterns Feature 013 already validated working
rather than inventing a third. No Playwright/Cypress, no MSW, no GPU,
Ollama, or Phoenix dependency — matching Feature 013's R10 and this
feature's own explicit testing constraints.

## R11. `replace_document`'s race-loss and re-index's no-regression guarantees — frontend implication

**Decision**: No frontend code branches on *why* a replace failed
(race-loss vs. validation failure vs. embedding failure) — `replace_document`
already returns a normal `DocumentSummary` with `status: "failed"` and a
safe `error_message` in every failure case, including the race-loss
message (`"This document was already replaced by another request."`,
`replace_document.py`), so the frontend's existing failure-path FR-025
("show a safe message, keep the original document active") already
handles it correctly without special-casing concurrency. Similarly,
`reindex_document`'s guarantee that a failed re-index never regresses an
already-`ready` document's `status` (`reindex_document.py`) means the
frontend's refresh-after-mutation (R8) is sufficient — re-fetching the
list after a failed re-index will show the document exactly as the
backend already protects it, with no frontend-side "don't downgrade
status" logic needed.

**Rationale**: Confirms spec's Edge Cases and FR-020/FR-025 are backed by
actual backend guarantees, not just described behavior this feature would
need to defensively re-implement — the frontend can trust a plain reload
(R8) to reflect these invariants correctly every time.

## R12. CORS `allow_methods` was missing `DELETE` — one-line additive backend fix

**Decision**: `src/shiruno/main.py`'s conditional `CORSMiddleware`
registration (added by Feature 013, research.md R8 of that feature) set
`allow_methods=["GET", "POST"]` — correct for what Feature 013 itself
needed (`POST /auth/login`, `GET /admin/me`), but Feature 014 is the first
feature to send a browser `DELETE` request (`deleteDocument`, R3). Without
`DELETE` in the allow-list, the browser's CORS preflight (`OPTIONS`) for
the delete request itself returns `400 Bad Request` before the real
`DELETE` is ever sent — confirmed by live browser QA (Playwright), not
caught by any existing automated test, since `tests/unit/
test_cors_configuration.py` asserted `allow_origins` but never
`allow_methods`. Fixed by adding `"DELETE"` to the existing list —
`allow_methods=["GET", "POST", "DELETE"]` — and extending that same test
with an assertion covering all three methods, so this can't silently
regress again.

**Rationale**: This is exactly the case spec.md's own Assumptions
paragraph anticipates and pre-authorizes: "a genuine UI-blocking contract
gap... cannot be solved safely in the frontend... additive and
tenant-safe... explicitly documented" (FR-041). CORS is enforced by the
browser against the server's response headers — no frontend-side
workaround exists for a missing allowed method. The fix widens nothing
about *who* can call the API (still gated by the existing narrow
origin allow-list, FR-024) or *what* they can do once authenticated
(no authorization logic touched) — it only lets a `DELETE` request's
preflight succeed for an already-narrowly-allowed origin.

**Alternatives considered**: None — this is the only correct fix; routing
delete through a `POST` with a method-override header, or any other
workaround, would be a strictly worse, less-standard design change to
dodge a one-line, already-narrowly-scoped CORS configuration fix.
