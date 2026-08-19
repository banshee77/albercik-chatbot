# Data Model: Public Website Chat Widget

Phase 1 output for `/speckit-plan`. This feature introduces **no server-side
persistence, no database table, no Python dataclass** — everything below is
either (a) a client-side-only, ephemeral JS data shape, held in
`sessionStorage` and never sent anywhere but back to the existing chat
endpoint, or (b) the existing, unmodified wire contract this feature
depends on and must not change. Spec source: spec.md's "Key Entities"
section; FR-006/007/015/015a.

## Client-side shapes (JavaScript, `chat.js` — no Python type)

### ChatMessage (in-memory / `sessionStorage`)

| Field | Type | Notes |
|---|---|---|
| `role` | `"user" \| "assistant"` | Who this turn belongs to. |
| `text` | `string` | The question (for `role: "user"`) or the answer text (for `role: "assistant"`) — always rendered via `textContent`, never interpreted as markup (FR-021/022). |
| `sources` | `string[]` | For an assistant message from a `grounded` outcome only: the deduplicated, first-seen-order list of source `label`s (FR-009a, FR-014). Empty for every other outcome and for all `role: "user"` messages. |

**Validation rules** (client-side, defensive — this is ephemeral UI state,
not a security boundary; the actual boundary is the untouched server-side
`ChatRequest`/`ChatResponse` contract below):
- `role` is always one of the two literal values above.
- `sources` is never populated from anything but a `grounded` response's
  `sources[].label` values — never from `document_id` (FR-014/SC-006).

### ChatSession (in-memory / `sessionStorage`)

| Field | Type | Notes |
|---|---|---|
| `messages` | `ChatMessage[]` | Ordered oldest-first; the full history rendered into the message log on panel open. |

**Lifecycle**: created empty on first page load with no existing
`sessionStorage` entry; persists across navigation between the site's
public pages within the same browser tab (Clarification, 2026-08-19);
discarded automatically by the browser when the tab/window closes
(`sessionStorage`'s native lifetime — no explicit app code deletes it).
Never written to any server-side store, never tied to an account or
device identity (FR-015). The **panel's own open/closed UI state is
explicitly excluded from this persisted shape** — it is pure transient
runtime state, always starting closed on a fresh page load, per
Clarification (2026-08-19) / FR-015a.

**Storage key**: a single namespaced `sessionStorage` key (e.g.
`albertos-chat-history`) holding `ChatSession.messages` as a JSON string.
A read or parse failure (corrupted content, storage unavailable in a
private-browsing context) is treated as "start with an empty session," not
a fatal error.

## Existing wire contract this feature depends on (unmodified)

Source of truth: `src/albercik_chatbot/api/schemas.py` and
`src/albercik_chatbot/api/routers/chat.py` — reproduced here only for
reference; this feature does not add to, remove from, or otherwise change
either file.

### Request — `POST /api/v1/chat`

| Field | Type | Notes |
|---|---|---|
| `question` | `string` | The **only** field the widget is ever allowed to send (FR-007). The endpoint's `extra="forbid"` validation independently guarantees any other field fails the request server-side regardless of what the client attempts. |

### Response (HTTP 200) — `ChatResponse`

| Field | Type | Notes |
|---|---|---|
| `outcome` | `"grounded" \| "insufficient_information" \| "out_of_scope" \| "unavailable"` | Drives which UI branch renders (FR-009–012). |
| `answer` | `string` | Already a safe, user-facing, Polish string in every outcome — rendered via `textContent` (FR-021). |
| `sources` | `{document_id: uuid, label: string}[]` | Only ever non-empty for `grounded`. The widget reads `.label` only (FR-014/SC-006); `.document_id` is never rendered. |
| `request_id` | `uuid` | Not used by this feature's UI; present for backend correlation only. |

### Response (HTTP 503) — same `ChatResponse` shape

The existing backend already pairs the `unavailable` outcome with HTTP 503
and a safe, friendly `answer` string
(`"Chatbot jest obecnie niedostępny. Spróbuj ponownie później."` —
`application/ask_question.py`) — not a bare error payload. See research.md
§1 for why the widget reuses this text directly rather than a second,
duplicate client-side string.

### Response (HTTP 429 / other 4xx) — `ErrorResponse` (generic, existing)

| Field | Type | Notes |
|---|---|---|
| `detail` | `string` | A generic, already-safe message (e.g. `"Too many requests."`) — the widget does **not** display this raw string to avoid coupling its own copy to backend wording it doesn't own; it shows its own friendly Polish message instead (FR-018), optionally incorporating the separate `Retry-After` **header** value for 429 (FR-019). |

## Relationships (summary)

```text
ChatSession (sessionStorage, client-only)
   └── ChatMessage[]  (role, text, sources[])
              ↑ built from ↓
POST /api/v1/chat  (existing, unmodified)
   request:  {question}
   response: {outcome, answer, sources[{document_id, label}], request_id}
             — outcome drives which ChatMessage.text/sources gets built
```

No entity here has a database row, a migration, or a Python type — the
only "model" work in this feature is the shape of transient browser state
and how it maps onto the pre-existing, untouched API contract.
