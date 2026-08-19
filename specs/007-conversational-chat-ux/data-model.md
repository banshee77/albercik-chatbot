# Data Model: Conversational UX for Public Chat

Phase 1 output for `/speckit-plan`. This feature introduces **no new
database table, no migration, and no persisted server-side state** — it
adds one new in-process Python classification result type (never
persisted), extends one existing `Literal` type additively, and simplifies
one client-side JS shape (dropping a field the widget no longer renders).
Spec source: spec.md's "Key Entities" section; FR-001–005, FR-013–015,
FR-019.

## New: `SmallTalkCategory` / `SmallTalkClassification` (`domain/small_talk.py`)

Pure, in-process, never persisted — exists only for the duration of one
`ask_question()` call.

| Type | Shape | Notes |
|---|---|---|
| `SmallTalkCategory` | `Literal["greeting", "goodbye", "thanks", "courtesy", "capability", "identity"]` | The six intent categories from spec Scope §1/User Story 3. Internal to `domain/small_talk.py` and `application/ask_question.py` — never serialized to the wire; the API response only ever exposes the single outcome value `"small_talk"` (§3 below), not which category matched. |
| `classify_small_talk(question: str) -> SmallTalkCategory \| None` | function | Returns the matched category, or `None` if the whole, normalized message doesn't anchor-match any category's pattern set (research.md §2) — `None` means "not small talk," and the caller falls through to the existing `is_albertos_scope` → retrieval → LLM pipeline unchanged. |
| `small_talk_reply(category: SmallTalkCategory) -> str` | function | Returns the fixed, developer-authored Polish reply text for that category (research.md §5) — never derived from the input question, never templated with user-supplied text. |

**Validation rules**:
- `classify_small_talk` is a pure function of its `question: str` argument
  only — no database access, no provider call, no I/O (FR-002).
  Deterministic: the same input always yields the same output (FR-003).
- A message is only ever assigned a category when the *entire* normalized
  message is accounted for by that category's pattern (research.md §2) —
  never on a mere substring match (FR-004).

## Extended (additive): `Outcome` (`application/ask_question.py`)

| Before | After |
|---|---|
| `Literal["grounded", "insufficient_information", "out_of_scope", "unavailable"]` | `Literal["grounded", "insufficient_information", "out_of_scope", "unavailable", "small_talk"]` |

`AskQuestionResult` itself is unchanged in shape
(`outcome: Outcome; answer: str; sources: list[SourceReference] = []`) — a
small-talk result simply sets `outcome="small_talk"`, `answer=<reply
text>`, and leaves `sources` at its existing empty-list default. No new
field is added to the dataclass.

## Extended (additive): `ChatResponse.outcome` (`api/schemas.py`)

| Before | After |
|---|---|
| `Literal["grounded", "insufficient_information", "out_of_scope", "unavailable"]` | `Literal["grounded", "insufficient_information", "out_of_scope", "unavailable", "small_talk"]` |

No other field of `ChatRequest` or `ChatResponse` changes. `ChatRequest`
still accepts exactly one field, `question`, with `extra="forbid"` —
unchanged, so a client still cannot select or override classification via
the request body (FR-018/FR-019, spec's testing requirement 17).

### Response (HTTP 200) — `ChatResponse`, `small_talk` outcome

| Field | Value for `small_talk` |
|---|---|
| `outcome` | `"small_talk"` |
| `answer` | The fixed reply text for the matched category (research.md §5) |
| `sources` | `[]` (always empty — small talk never cites a document) |
| `request_id` | Present as normal, for backend correlation only; **no** corresponding `UsageRecord` row is created for a `small_talk` outcome (mirrors the existing `out_of_scope` behavior — see `application/ask_question.py`) |

## Client-side shape change: `ChatMessage` (`chat.js`, `sessionStorage`)

| Field | Before (feature 006) | After (this feature) | Notes |
|---|---|---|---|
| `role` | `"user" \| "assistant"` | unchanged | |
| `text` | `string` | unchanged | For a `small_talk` outcome, this is the canned reply text returned by the backend — rendered via `textContent`, same as every other outcome (FR-013). |
| `sources` | `string[]` (deduplicated labels, non-empty only for `grounded`) | **removed** | The public widget no longer renders a sources line for any outcome (FR-013). Existing `sessionStorage` entries written by feature 006 that still carry a populated `sources` array are read defensively (an extra key is simply ignored by the updated renderer) — no migration or clearing of existing session data is needed. |

**Lifecycle**: unchanged from feature 006 — `ChatSession` (`{messages:
ChatMessage[]}`) persists in `sessionStorage` across same-tab navigation,
starts empty on first load, panel always starts closed on a fresh page
load, and small-talk messages are appended through the exact same
`appendAndPersist()` path as any other message (FR-015/FR-016) — no
separate storage mechanism is introduced for small talk.

## New static asset (not a data model, listed for completeness)

`public_site/static/img/assistant-avatar.svg` — a static file, not
associated with any Python or JS runtime type. Referenced only via a CSS
`background-image` URL (research.md §6); has no request/response shape of
its own beyond the ordinary static-file GET the browser issues for it.

## Relationships (summary)

```text
POST /api/v1/chat  (existing endpoint, request contract unchanged)
   request:  {question}
        │
        ▼
application/ask_question.py
   rate limit → kill switch/budget → concurrency guard →
   [NEW] classify_small_talk(question) ──► matched? ──yes──► small_talk_reply(category)
        │ no                                                        │
        ▼                                                           │
   is_albertos_scope → retrieval → LLM → usage accounting            │
        │                                                            │
        ▼                                                            ▼
   response: {outcome, answer, sources[], request_id}  ◄─────────────┘
        │            (outcome ∈ {grounded, insufficient_information,
        │             out_of_scope, unavailable, small_talk})
        ▼
chat.js → ChatMessage{role, text}  (no `sources` field rendered)
        └── persisted in ChatSession (sessionStorage), unchanged lifecycle
```

No entity in this feature has a database row or a migration — the only
"model" additions are one in-process classification result type, one
additive `Literal` member on an existing type (shared by the Python
dataclass and the Pydantic response model), and one field removed from an
existing client-side JS shape.
