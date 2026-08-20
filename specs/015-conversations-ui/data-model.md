# Phase 1 Data Model: Conversations UI

This feature introduces **no new persistence model** — it is a pure
frontend consumer of the existing `ConversationRecord` table via Feature
011's `/api/v1/admin/conversations*` API (research.md R1). The entities
below are the frontend's **presentation-layer types**
(`apps/admin/src/api/types.ts`), each a direct, non-duplicating mirror of
the public admin API response shape documented in
`specs/011-conversations-analytics/contracts/conversations-api.md` — never
the backend's internal `ConversationRecord` SQLAlchemy model (FR-040).

## `ConversationOutcome`

```ts
export type ConversationOutcome =
  | 'grounded'
  | 'insufficient_information'
  | 'out_of_scope'
  | 'unavailable'
  | 'small_talk'
```

The five backend-recognized outcome values (contracts/conversations-api.md
§ query parameters). Mapped to a customer-facing label exclusively through
`outcomeLabel()` (research.md R7) — no component compares against these
string literals directly for display purposes, only for filtering.

## `ConversationSummary` (list row)

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Row identity/selection key only; never displayed. |
| `request_id` | `string` | Always present (backend never nulls it); not shown in the list — only in detail's secondary "Technical details" area. |
| `question` | `string` | Displayed as-is; never logged (FR-044). |
| `outcome` | `ConversationOutcome` | Mapped via `outcomeLabel()` before display (FR-007). |
| `created_at` | `string` (ISO datetime) | Formatted with `Date.toLocaleString()`, matching `DocumentTable`'s existing `updated_at` treatment. |
| `latency_ms` | `number` | Shown where useful (spec.md §1); always present. |

No field here is ever a raw tenant identifier, provider metric, or full
answer text (FR-003) — this mirrors the backend's own "intentionally
lightweight" list response (contracts/conversations-api.md).

## `ConversationListResponse`

| Field | Type | Notes |
|---|---|---|
| `items` | `ConversationSummary[]` | Already newest-first from the backend (FR-001, FR-002) — never re-sorted client-side. |
| `total` | `number` | Count matching current filters, independent of `limit`/`offset` (research.md R11). |
| `limit` | `number` | Echoes the effective (clamped) page size the backend applied. |
| `offset` | `number` | Echoes the effective (clamped) offset the backend applied. |

## `ConversationListParams` (request shape, not a response type)

| Field | Type | Notes |
|---|---|---|
| `q` | `string \| undefined` | Omitted entirely when empty (research.md R8) — never sent as `q=`. |
| `outcome` | `ConversationOutcome \| undefined` | Omitted for "All" (FR-013). |
| `start_date` | `string \| undefined` | Bare `YYYY-MM-DD` from the native date input (research.md R10). |
| `end_date` | `string \| undefined` | End-of-day timestamp derived from the native date input (research.md R10) — never the bare date. |
| `limit` | `number \| undefined` | Fixed constant (research.md R11); not user-adjustable. |
| `offset` | `number \| undefined` | Reset to `0` by every search/filter/date change (FR-011, FR-014, FR-016). |

**Deliberately absent**: no `tenant_id` field exists on this type at all
— not optional, not defaulted, not present (FR-041, constitution Principle
II "Frontend is never a security boundary").

## `ConversationSource`

| Field | Type | Notes |
|---|---|---|
| `document_id` | `string` | Historical snapshot value; never used to look up the document's *current* state (FR-028). |
| `label` | `string` | The only field actually rendered (e.g. `treningi.txt`). |

## `ConversationDetail`

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Not displayed. |
| `request_id` | `string` | Shown only in the secondary "Technical details" area, copyable (FR-038). |
| `question` | `string` | Displayed prominently, separate from the answer (FR-024). |
| `answer` | `string` | Displayed prominently, separate from the question. |
| `outcome` | `ConversationOutcome` | Drives which outcome-specific detail block renders (FR-031–FR-034). |
| `created_at` | `string` (ISO datetime) | Formatted with `Date.toLocaleString()`. |
| `latency_ms` | `number` | Shown in the compact operational-metadata area (FR-035). |
| `sources` | `ConversationSource[] \| null` | `null` for every outcome except `grounded` (data-model.md of Feature 011); rendered only when non-`null` (FR-028–FR-030). |
| `provider_name` | `string \| null` | `null` when no provider call occurred (e.g. `small_talk`) — absence shown naturally, never a fabricated value (FR-036). |
| `provider_model` | `string \| null` | Same nullability as `provider_name`. |
| `input_tokens` | `number \| null` | Same nullability as `provider_name`. |
| `output_tokens` | `number \| null` | Same nullability as `provider_name`. |
| `safe_failure_category` | `SafeFailureCategory \| null` | Non-`null` only when `outcome = "unavailable"` (FR-033). |

**Deliberately absent**: `provider_metrics` is never declared on this type
(research.md R4, satisfying FR-037 structurally) and `tenant_id` never
appears (FR-025, FR-041).

## `SafeFailureCategory`

```ts
export type SafeFailureCategory =
  | 'provider_error'
  | 'budget_exceeded'
  | 'kill_switch'
  | 'concurrency_limit'
```

Displayed (when present) through a small customer-facing mapping alongside
`outcomeLabel()`'s "Assistant unavailable" text — never the raw enum value
and never a raw provider exception (FR-033).

## Frontend-only presentation state (not persisted, not part of the API contract)

These exist only inside `ConversationsPage`'s React state — never sent to
the backend as an identifier, never written to storage (FR-044, spec.md
§29):

- `status: 'loading' | 'loaded' | 'error'` — list-level, mirrors
  `KnowledgePage`'s existing `PageStatus` (research.md R12).
- `offset: number`, fixed `limit` — pagination cursor (research.md R11).
- `search: string`, `outcomeFilter: ConversationOutcome | 'all'`,
  `dateFrom: string`, `dateTo: string` — the four active filters.
- `selectedConversationId: string | null` — which row's detail is open;
  clearing it (Close) never mutates any of the state above (FR-027).
- `detailStatus: 'idle' | 'loading' | 'loaded' | 'error'`,
  `detail: ConversationDetail | null` — the detail panel's own
  independent loading/error state (FR-023, FR-026), separate from the
  list's `status`.

## State transitions

```text
list status:  loading → loaded ⇄ (search/filter/date/page change → loading → loaded)
                       → error → (retry → loading → loaded | error)

detail status (per selected id): idle → loading → loaded
                                              → error
                       closing (selectedConversationId → null) discards
                       detail/detailStatus without touching list status,
                       offset, search, outcomeFilter, dateFrom, dateTo (FR-027)
```

No entity in this feature has a lifecycle of its own to model — a
`ConversationRecord` is immutable from the frontend's point of view (Feature
015 is read-only, FR-049); the only "state transitions" are the page's own
UI status enums above.
