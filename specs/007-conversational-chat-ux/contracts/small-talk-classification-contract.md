# Contract: Small-Talk Classification on `POST /api/v1/chat`

Phase 1 output for `/speckit-plan`. This feature adds **no new endpoint**
— its only external interface is one additive change to the existing,
public `POST /api/v1/chat` contract (owned by `specs/001-albertos-rag-
chatbot/contracts/openapi.yaml`, extended by `specs/004-rag-answerability-
and-ollama-performance/contracts/chat-endpoint-delta.md`): one new
possible value of the response's `outcome` field. This document locks down
exactly what changes, what does not, and how any caller — the public
widget, a direct API client, or a future client — must interpret the new
value, so both are independently testable.

## Request contract — unchanged

```json
POST /api/v1/chat
Content-Type: application/json

{"question": "<caller's exact text>"}
```

- Still **exactly one field, always** — `extra="forbid"` is untouched.
  There is no field a caller can set to request, select, or override
  small-talk classification, or to force a message through/around it
  (spec FR-018; testing requirement 17). Classification is derived
  **solely** from the content of `question`.
- No new header, no new query parameter, no auth requirement added — the
  endpoint remains public and unauthenticated, exactly as before.

## Response contract — one additive `outcome` value

| Field | Before | After |
|---|---|---|
| `outcome` | `"grounded" \| "insufficient_information" \| "out_of_scope" \| "unavailable"` | adds `"small_talk"` |
| `answer` | `string` | unchanged shape; for `small_talk`, a fixed, non-templated Polish reply |
| `sources` | `{document_id, label}[]` | unchanged shape; always `[]` for `small_talk` |
| `request_id` | `uuid` | unchanged; present for `small_talk` too, but no `UsageRecord` row is written for a `small_talk` outcome |

A hypothetical caller that already treats an unrecognized `outcome` value
defensively (e.g. by falling back to displaying `answer` regardless of the
exact outcome string) would continue to work correctly without any change.
**The public widget's `chat.js` is not such a caller**: its existing
`handleResponse()` (feature 006) switches explicitly on each known
`outcome` string and treats anything it doesn't recognize as a malformed
response, routing it to the generic friendly-error fallback — the same
bucket used for network failures — rather than displaying `answer`. This
feature therefore MUST add an explicit `"small_talk"` branch to
`handleResponse()` (rendering `answer`, no sources) as part of its own
scope; without that branch, a `small_talk` response would incorrectly
surface as a generic error instead of the intended friendly reply. Any
caller written to switch/pattern-match **exhaustively** over exactly the
four pre-existing values, with no default branch — `chat.js` included —
needs updating to add this fifth case; this is the one integration-visible
consequence of the change, and it is the reason this feature adds the
value rather than silently reusing `"grounded"`
(spec Clarifications, 2026-08-19).

## Classification semantics (informative, not part of the wire contract)

The `outcome: "small_talk"` value is returned when — and only when — the
entire message, after normalization, matches one of six intent categories:
greeting, goodbye, thanks, courtesy, capability question, or identity
question (spec Scope §1, User Story 3). Which of the six matched is
**not** exposed on the wire; only the caller-visible `answer` text differs
per category. A message that combines a greeting/courtesy phrase with any
additional, unaccounted-for content (most commonly a real question) never
receives `outcome: "small_talk"` — it is evaluated by the existing,
unmodified scope/retrieval/LLM pipeline exactly as if the small-talk
phrase weren't there (spec FR-004, User Story 2).

## Safeguards contract — every existing control still applies

Per spec Clarifications (2026-08-19) and SC-009: a message that would be
rejected by an existing pre-classification safeguard is rejected the same
way today, regardless of whether it would otherwise have classified as
small talk:

| Safeguard | Still applies to a small-talk-shaped message? |
|---|---|
| HTTP/payload size validation | Yes, unchanged |
| Question-length validation (`ChatRequest` validator) | Yes, unchanged |
| Rate limiting | Yes, unchanged — a small-talk message counts against the same per-source rate limit as any other message |
| LLM kill switch / budget check | Yes, unchanged — if the kill switch is off or the budget is exhausted, the request still resolves to `outcome: "unavailable"` *before* small-talk classification is ever reached, exactly as today for a real question |
| Concurrency guard | Yes, unchanged — acquiring a concurrency slot happens before classification |

Only the embedding/retrieval/LLM-call step itself is skipped for a
`small_talk` outcome — no safeguard upstream of that step is bypassed,
weakened, or reordered.

## What this feature never does

- Never adds a new endpoint, WebSocket, or SSE stream for small talk
  (Out of Scope).
- Never lets a client select, name, or override which category matched, or
  force/prevent classification, through any request field (FR-018).
- Never changes the meaning, shape, or presence of any pre-existing
  `outcome` value, or of `sources`/`request_id`/`answer` for any
  non-`small_talk` outcome (FR-014).
- Never invents a factual claim about Albertos through this path — the
  reply text for every category is a fixed, developer-authored constant,
  never derived from retrieval, the LLM, or the caller's input text
  (FR-005; Constitution Principle III).

## Negative contract: no new server surface

This feature registers no new FastAPI route. `application/ask_question.py`
gains one new internal branch; `api/routers/chat.py` is unmodified (no new
`Depends()`, no new response model, no new status code). A contract test
asserts the app's route table is unchanged in count/paths from before this
feature, mirroring how feature 006 proved the same negative for its own
scope.
