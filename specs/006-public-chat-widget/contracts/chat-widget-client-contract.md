# Contract: Chat Widget's Use of the Existing Chat API

Phase 1 output for `/speckit-plan`. This feature adds **no new backend
endpoint** — its only external interface is how `public_site/static/js/
chat.js` calls the existing, unmodified `POST /api/v1/chat` (contract
owned by `specs/001-albertos-rag-chatbot/contracts/openapi.yaml` and
`specs/004-rag-answerability-and-ollama-performance/contracts/
chat-endpoint-delta.md`). This document is the **client-side usage
contract**: exactly what the widget is allowed to send, and exactly how it
must interpret every possible response, so both are locked down and
testable independent of the (unmodified) server contract itself.

## Request the widget is allowed to send

```json
POST /api/v1/chat
Content-Type: application/json

{"question": "<visitor's exact text>"}
```

- **Exactly one field, always.** The widget MUST NOT construct a request
  body with any other key — not `model`, `provider`, `llm_provider`,
  `max_tokens`, `top_k`, `system_prompt`, `temperature`, `think`,
  `retries`, `retry_count`, `budget`, or any other name (spec FR-007).
  This is a client-side discipline requirement on top of, not instead of,
  the server's own `extra="forbid"` enforcement — belt and suspenders, not
  a substitute for it.
- No other header beyond `Content-Type: application/json` is required or
  sent (no auth header — the endpoint is public/unauthenticated).
- Each submission is a complete, independent request. Prior conversation
  turns held in the client's `ChatSession` are **never** included in the
  request body (spec FR-008) — the existing endpoint has no concept of
  multi-turn context, and this feature does not add one.

## Response → UI outcome mapping

| Condition | Widget behavior | Spec ref |
|---|---|---|
| `200` + `outcome: "grounded"` | Render `answer` (`textContent`); if `sources` is non-empty, render the deduplicated, first-seen-order `label` list as `"Źródła: a, b, c"` below the answer | FR-009, FR-009a |
| `200` + `outcome: "insufficient_information"` | Render `answer`; no sources line | FR-010 |
| `200` + `outcome: "out_of_scope"` | Render `answer`; no sources line | FR-011 |
| `200` + `outcome: "unavailable"` (theoretical — current backend always pairs this with 503) | Render `answer` | FR-012 |
| `503` | Attempt to parse the same `ChatResponse` shape and render its `answer`; if the body doesn't parse as that shape, show the generic fallback friendly message instead | FR-012, FR-018 |
| `429` | Show a friendly rate-limit message; if the `Retry-After` response **header** is present and a positive integer, incorporate the wait time | FR-018, FR-019 |
| Network failure (the `fetch` call itself throws/rejects) | Generic friendly fallback error | FR-018 |
| `200` response whose body is not valid JSON, or is valid JSON missing a string `outcome`/`answer` | Generic friendly fallback error ("malformed response") | FR-018 |
| Any other HTTP status (400, 404, 413, a hypothetical 422, 500, etc.) | Generic friendly fallback error — the same single fallback bucket as the two rows above, no status-specific message | FR-018a (Clarifications, 2026-08-19) |

Exactly one of the rows above applies to any given `fetch` outcome — there
is no status/body combination this feature leaves undefined.

## What the widget never does

- Never introduces a second endpoint, a WebSocket connection, or an SSE
  stream for chat (spec FR-006; Out of Scope: WebSockets, streaming
  tokens).
- Never reads or displays `sources[].document_id` (spec FR-014/SC-006).
- Never displays `detail` from a 429/4xx `ErrorResponse` body verbatim —
  always its own friendly Polish copy (spec FR-018).
- Never renders `answer` or any source `label` as HTML/markup — `Element.
  textContent` (or an equivalent safe text API) only, never `Element.
  innerHTML` with response-derived content (spec FR-021/022).

## Negative contract: no new server surface

Per spec FR-006/FR-023, this feature registers no new FastAPI route of any
kind. A test asserts this directly by construction: the shipped
`static/js/chat.js` source contains exactly one API path literal
(`/api/v1/chat`) and no other `/api/...`-shaped string — proving the
client has nothing else to call, rather than only trusting that the server
happens not to expose anything else.
