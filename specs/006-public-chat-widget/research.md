# Research: Public Website Chat Widget

Phase 0 output for `/speckit-plan`. This feature adds no new dependency and
no new backend endpoint, so most "research" here is about how to fit a
client-only integration into `public_site`'s existing, already-established
patterns (feature 005) rather than about technology selection.

## 1. What the existing `POST /api/v1/chat` contract actually guarantees

Read directly from `src/albercik_chatbot/api/schemas.py`,
`src/albercik_chatbot/api/routers/chat.py`, and
`src/albercik_chatbot/application/ask_question.py` (unmodified by this
feature):

- **Request**: `ChatRequest` has exactly one field, `question: str`
  (`min_length=1`, a dynamically-configured max length), and
  `model_config = ConfigDict(extra="forbid")`. Any other field in the body
  — `model`, `provider`, `max_tokens`, `top_k`, `system_prompt`,
  `temperature`, `think`, `retries`, `budget`, etc. — makes the *entire*
  request fail with `400`, server-side, unconditionally. This is already
  covered by `tests/contract/test_chat_no_client_override.py` for the
  general contract and `tests/contract/test_chat_no_client_override.py`
  (feature 002) for provider-selection fields specifically.
- **Response** (HTTP 200): `ChatResponse` = `{outcome, answer, sources,
  request_id}`. `outcome` is one of `"grounded" | "insufficient_information"
  | "out_of_scope" | "unavailable"`. `sources` is a list of
  `{document_id: uuid, label: str}` (only ever non-empty for `grounded`).
- **`unavailable` is always paired with HTTP 503, not 200** in the current
  implementation (`ask_question.py` returns `outcome="unavailable"` for a
  budget rejection, a concurrency-guard rejection, or an unsupported LLM
  answer; `chat.py`'s route sets `response.status_code = 503` whenever
  `result.outcome == "unavailable"`). Critically, **the 503 response body is
  still a well-formed `ChatResponse` JSON object** — `answer` is already a
  short, safe, Polish, user-facing string
  (`"Chatbot jest obecnie niedostępny. Spróbuj ponownie później."`), not an
  error/exception payload. Decision: the widget displays that
  backend-supplied `answer` text directly (via `textContent`, per Security)
  rather than duplicating a second, separately-authored "unavailable"
  string client-side — one message, one source of truth, and it already
  satisfies FR-012's "friendly temporary-unavailability message" and
  FR-013/FR-018a's "no raw internals" requirement, since `ask_question.py`
  deliberately never puts exception detail into that string.
- **429 (rate limit)**: raised by `RateLimitedError` before any provider
  call — response body is `{"detail": "Too many requests."}` (the generic
  `ErrorResponse` shape from `api/errors.py`), **not** a `ChatResponse` —
  it has no `outcome` field. `Retry-After` is set as a real response header
  (`infra/rate_limit.py`'s `retry_after_seconds`, confirmed by
  `tests/contract/test_chat_rate_limit.py`). Decision: the widget's 429
  handling reads the `Retry-After` header, not the body.
- **Any other 4xx** (400 bad request, 413 payload too large, a would-be 422
  from Pydantic's own validation on an over-length `question`) is likewise
  the generic `{"detail": ...}` `ErrorResponse` shape, no `outcome` field.

**Decision**: the client's response-handling logic branches on **HTTP
status first**, then on body shape, in this order:
1. `status === 200` → parse JSON; if it has a string `outcome` matching one
   of the four known values and a string `answer`, render per that
   `outcome` (FR-009–FR-012). Otherwise (malformed 200) → generic fallback
   error (FR-018).
2. `status === 429` → generic rate-limit message, augmented with the
   `Retry-After` header value when present and parseable as a positive
   integer (FR-019).
3. `status === 503` → attempt the same `ChatResponse` JSON parse as (1) and
   display its `answer` if shape-valid; otherwise fall back to a generic
   client-authored unavailable message. Either path satisfies FR-012.
4. Any other status, a thrown `fetch` exception (network failure), or a
   response body that fails the shape check in (1)/(3) → the single
   generic friendly fallback error (FR-018/FR-018a resolved in
   Clarifications).

This keeps the widget correct without hardcoding any backend-internal
threshold (e.g. the configured max question length) and without needing a
distinct message for every conceivable non-200 status.

## 2. Where the panel chassis lives: Jinja2, not JS-constructed DOM

Feature 005 already established the pattern this feature should extend,
not replace: `base.html` is the one shared layout every one of the 8 public
pages extends, and interactive chrome that must exist identically on every
page (the nav, the mobile-menu toggle) lives there as plain server-rendered
markup, with `site.js` only adding *behavior* on top of already-complete
HTML — never constructing that HTML from scratch client-side.

**Decision**: the chat launcher `<button>` and the full chat panel skeleton
(title, scope notice, empty message log, form, send/close controls, status
line) are added to `base.html` as static Jinja2/HTML, identical on every
page by construction (no per-page duplication, no risk of one page's copy
drifting from another's). `chat.js` never builds this chassis; it only:
toggles visibility/ARIA state, and appends individual message elements into
the already-existing log container using `document.createElement` +
`.textContent` (never `.innerHTML`, satisfying FR-021/FR-022 by
construction, not by convention).

**Alternative rejected**: constructing the entire panel via JS on
`DOMContentLoaded` (as some third-party chat widgets do) was considered and
rejected — it would duplicate the layout in a second language (JS template
strings) for no benefit, it is harder to keep visually consistent with the
Jinja2-rendered rest of the site, and it re-opens exactly the innerHTML-vs-
textContent risk this feature's Security requirements (FR-021/022) exist to
avoid, since panel-chassis construction is exactly the kind of code that
tempts a `.innerHTML = template literal` shortcut.

## 3. Progressive enhancement: reuse the existing `.js`-class mechanism

Feature 005 already solved "this control requires JS, and must not render
as a dead control without it" once, for the mobile-nav toggle: an inline,
synchronous `<script>` in `<head>` adds a `js` class to
`<html>` before first paint, and CSS only reveals JS-dependent chrome under
`.js …` selectors (see `base.html`'s
`<script>document.documentElement.classList.add("js");</script>` and
`site.css`'s `.js .nav-toggle` / `.js .primary-nav` rules).

**Decision**: the chat launcher and panel reuse this exact, already-proven
mechanism (`.js .chat-launcher { display: inline-flex; }`, panel likewise
hidden outside `.js`) rather than inventing a second no-JS-detection
technique. This directly satisfies FR-025 (no visibly broken/dead control
when JS is unavailable) and keeps the site with exactly one pattern for
this concern, not two.

## 4. Client-side session storage: `sessionStorage`, not `localStorage` or a bare JS variable

Per the resolved specification Clarification (message history persists
across navigation between pages within the same tab, cleared on tab/browser
close): a bare in-memory JS variable would reset on every page navigation
(this is a multi-page, non-SPA site — each page load is a fresh JS
context), failing that requirement outright. `localStorage` would survive
browser restarts and be shared across unrelated tabs, over-persisting
relative to "browsing session."

**Decision**: `window.sessionStorage`, a single JSON-encoded array under one
namespaced key (`albertos-chat-history`), holding
`{role: "user" | "assistant", text: string, sources: string[]}` entries.
Read once on `DOMContentLoaded` to repopulate the message log (still
hidden, since the panel itself never auto-opens per the Clarification);
written after every completed exchange. A defensive soft cap (last ~200
entries) is applied purely as implementation-level storage-quota insurance
(`sessionStorage` is typically limited to a few MB per origin) — this is an
engineering safety margin, not a product requirement, and does not
contradict the specification's "no fixed cap required" assumption, which
was about conversation UX, not about unbounded storage risk.
`JSON.parse`/`sessionStorage` failures (private-browsing quota errors,
corrupted content) are caught and treated as "no prior history" rather than
breaking the page.

## 5. Dialog pattern: WAI-ARIA APG "Dialog (Modal)"

FR-030/FR-031 (focus moves in on open, returns to launcher on close, Escape
closes) are exactly the WAI-ARIA Authoring Practices "Dialog (Modal)"
pattern's baseline requirements, regardless of whether the panel visually
dims the rest of the page — focus genuinely leaves the rest of the page
while the panel is open, which is what `aria-modal="true"` communicates to
assistive technology, independent of the visual "does it cover the whole
screen" question already answered by FR-028 (it must not, on desktop).

**Decision**: `role="dialog" aria-modal="true" aria-labelledby="<title id>"`
on the panel; a small (~20 line) hand-rolled focus trap (Tab/Shift+Tab wrap
within the panel's focusable elements while open) and an `Escape` keydown
listener scoped to the panel; on open, focus moves to the panel's heading
or the text input; on close, focus returns to the launcher button via a
stored reference — no library, matching Constitution Principle XIII
(Simplicity for MVP).

The message log itself uses `role="log" aria-live="polite"` (the standard
pattern for a growing chat transcript — each new message is announced
without re-announcing the whole history), and a separate `role="status"
aria-live="polite"` element carries transient loading/error text
(FR-032) — kept as its own region rather than folded into the message log,
so a screen-reader user reliably hears "Albertos AI pisze odpowiedź…" as a
single, distinct status update rather than it competing with conversation
content.

## 6. Duplicate-submission guard

**Decision**: a single module-scoped `requestInFlight` boolean in
`chat.js`. The form's submit handler returns immediately if it's already
`true`; the send control (and the input) get `disabled` while a request is
in flight; the guard is cleared in a `finally` block so it always resets
on success, a handled error, or an unexpected exception (FR-016/SC-007).
Per FR-017/US3 acceptance scenario 4, the **close** control is never part
of this guard — it is wired independently and stays clickable throughout.

## 7. Sources rendering: dedupe by label, compact join

**Decision**: from `body.sources` (`{document_id, label}[]`), extract only
`.label` (`document_id` is never read into the DOM — satisfies
FR-014/SC-006 by construction, not by a display-layer filter that could be
forgotten), deduplicate with a `Set` that preserves first-seen insertion
order (FR-009a), and join the result with `", "` behind a literal
`"Źródła: "` prefix — matching the example format in the specification.
When the deduplicated list is empty, no sources line is rendered at all
(FR-009).

## 8. Testing strategy without browser automation

Per spec SC-008 and the constitution's Testing Discipline principle
(external I/O must be mockable; no paid-provider or heavy tooling
dependency in the default suite), and per this feature's explicit
constraint (no browser automation required for the normal suite):

- **Markup + accessibility-attribute tests** (`tests/contract/`): the same
  `TestClient(create_app(llm_provider=FakeLLMProvider(), ...))` pattern
  already used by `tests/contract/test_public_site_pages.py` — fetch each
  of the 8 pages, assert the launcher and panel skeleton are present with
  the expected ids, `role`, `aria-*` attributes, and that the `chat.js`
  `<script>` tag is present. No JS execution needed for these assertions;
  they verify what the server actually sends.
- **Client-script static-source tests** (`tests/unit/`): read
  `static/js/chat.js` as plain text and assert, via string/regex checks:
  exactly one endpoint literal, `/api/v1/chat`, appears, and no other
  `/api/...` path literal does; the only key ever passed as the request
  body is `question` (no literal occurrence of `model`, `provider`,
  `max_tokens`, `top_k`, `system_prompt`, `temperature`, `think`,
  `retries`, `budget` as a JSON object key in a request-construction
  context); `.innerHTML` never appears anywhere in the file;
  `.textContent` is used for inserting message text; an `Escape` key check
  and `.focus()` calls are present. This proves the safety-relevant
  properties (FR-006/007/021/022) by inspecting the actual shipped source,
  without needing a Node.js test runner or a real browser.
- **Non-regression**: the full existing `tests/contract/test_chat*.py`
  suite is re-run unmodified — this feature does not touch `chat.py`,
  `schemas.py`, `ask_question.py`, or any RAG/provider/rate-limit/budget/
  auth code, so there is nothing in those files for this feature to
  regress, and the existing suite passing unmodified is the proof.

None of this requires a live Ollama/Anthropic provider, a GPU, or a browser
— matching SC-008 and the constitution's mockable-I/O requirement.
