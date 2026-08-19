# Feature Specification: Public Website Chat Widget

**Feature Branch**: `006-public-chat-widget`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Integrate the existing Albertos AI chatbot into the existing public Albertos website as a modern, accessible chat widget, reusing the existing POST /api/v1/chat endpoint exactly as-is, with no changes to RAG/retrieval/LLM/rate-limiting/budget/prompt-injection/admin-auth controls."

## Clarifications

### Session 2026-08-19

- Q: When a visitor navigates from one public page to another while the chat panel is open, should the panel automatically reopen on the new page (restoring its open/closed state), or should it always start closed on a fresh page load even though the conversation history is preserved? → A: Panel always starts closed on a fresh page load; only the conversation history carries over.
- Q: If the chat API ever responds with an HTTP status this widget doesn't have a specific message for (e.g. a 422 for a too-long question), what should the widget show? → A: Treat any status other than 200/429/503 as the same generic friendly error already used for network failures and unparseable responses — a single fallback bucket, with no client-side question-length limit added.
- Q: When a grounded answer's sources list contains the same source label more than once, should the widget show that label once or repeated as returned? → A: Deduplicate by label, preserving first-seen order — each distinct source appears once.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visitor asks a question and gets a grounded answer (Priority: P1)

A prospective member is reading the public website and has a question the
page content doesn't fully answer (e.g. "o której godzinie są treningi dla
początkujących w Grodzinie?"). Instead of hunting through the schedule page,
they open the chat launcher, type their question, and receive a direct
answer, with the source pages it was drawn from, without leaving the page
they were on.

**Why this priority**: This is the entire reason the widget exists — turning
the site's existing knowledge base into an instantly answerable
conversation. Without this, there is no feature.

**Independent Test**: On any public page, open the launcher, submit a
question known to be answerable from site content, and confirm an answer
with sources appears in the panel without a full page reload.

**Acceptance Scenarios**:

1. **Given** a visitor on any of the 8 public pages, **When** they activate
   the chat launcher, **Then** a panel opens showing the assistant's title,
   a short scope explanation, and an empty message area with a text input,
   send button, and close button.
2. **Given** the panel is open, **When** the visitor types a question and
   submits it, **Then** their question appears in the message history, a
   loading state is shown, and — once the backend responds with a
   `grounded` outcome — the answer appears in the message history attributed
   to the assistant, followed by a compact list of the sources it cites.
3. **Given** an answer has just been shown, **When** the visitor asks a
   second, unrelated question, **Then** the request is sent to the backend
   as an independent question (not combined with prior turns) and the new
   answer is appended below the earlier exchange.

---

### User Story 2 - Visitor honestly told when a question is out of scope or unanswerable (Priority: P2)

A visitor asks something the assistant has no grounding for (e.g. a
scheduling question with no matching content) or something entirely
unrelated to the club (e.g. a general trivia question). The widget must
never fabricate an answer or pretend to be a general-purpose assistant — it
tells the visitor plainly what it can and can't do.

**Why this priority**: Trust is the second most important property after
the happy path — a chatbot that overclaims or gives a confusing non-answer
actively damages the club's credibility on its own public page.

**Independent Test**: Submit a question engineered to return
`insufficient_information`, and separately one engineered to return
`out_of_scope`, and confirm each produces a distinct, friendly, honest
message rather than a blank or generic-looking answer.

**Acceptance Scenarios**:

1. **Given** the panel is open, **When** the backend returns
   `insufficient_information` for a submitted question, **Then** the panel
   shows a friendly message stating the assistant doesn't have enough
   information about that, without sources.
2. **Given** the panel is open, **When** the backend returns `out_of_scope`
   for a submitted question, **Then** the panel shows a friendly reminder of
   what the assistant can help with (training, schedule, trainers, sections,
   club information), reinforcing the scope notice shown when the panel
   first opened.

---

### User Story 3 - Visitor sees a clear message when the assistant is temporarily unavailable or the network fails (Priority: P3)

The backend, its rate limiter, or the visitor's own network connection
occasionally has a bad moment. The widget must degrade to a clear,
non-technical message rather than a stuck spinner, a blank panel, or an
error dump.

**Why this priority**: These conditions will happen in production (rate
limiting is an existing, intentional control) and a bad failure experience
here is the most visible way this feature could embarrass the site.

**Independent Test**: Simulate each of a 429 response, a 503 response, and a
network failure, and confirm each produces a distinct-enough, friendly,
Polish-language message with no raw error text, and that the panel remains
fully usable (input re-enabled, close button works) afterward.

**Acceptance Scenarios**:

1. **Given** a question is submitted, **When** the backend responds with
   HTTP 429, **Then** the panel shows a friendly "too many questions, please
   wait" message, incorporating the wait time if the backend supplied one,
   and the input is usable again once the wait state clears.
2. **Given** a question is submitted, **When** the backend responds with
   HTTP 503 (or the existing `unavailable` outcome), **Then** the panel
   shows a friendly temporary-unavailability message and the input becomes
   usable again for a retry.
3. **Given** a question is submitted, **When** the request fails before any
   response is received (network error) or the response body cannot be
   parsed, **Then** the panel shows a generic friendly error message, never
   the raw failure detail, and the visitor can try again.
4. **Given** any error state is being shown, **When** the visitor clicks the
   close button, **Then** the panel closes normally — an error never traps
   the visitor in the panel.

---

### User Story 4 - Visitor operates the widget entirely by keyboard (Priority: P4)

A visitor who cannot or does not use a mouse — including screen-reader
users — must be able to discover the launcher, open the panel, ask a
question, read the response, and close the panel using only the keyboard,
with focus landing in sensible, predictable places throughout.

**Why this priority**: Accessibility is a baseline quality bar for a public
site, not an optional polish pass, but it builds on the panel already
existing from User Story 1, so it is sequenced after the core conversational
value.

**Independent Test**: Using only the Tab, Enter/Space, and Escape keys
(no mouse), reach the launcher from any page, open the panel, confirm focus
moved into it, close it with Escape, and confirm focus returned to the
launcher.

**Acceptance Scenarios**:

1. **Given** a visitor is tabbing through a public page, **When** they reach
   the chat launcher, **Then** it has a visible focus indicator and a clear,
   descriptive label announced by assistive technology (e.g. "Zapytaj
   Albertos — otwórz czat"), and activating it with Enter or Space opens the
   panel.
2. **Given** the panel has just opened, **When** focus is evaluated,
   **Then** it has moved into the panel (e.g. to the text input or the
   panel's heading), not left behind on the page underneath.
3. **Given** the panel is open, **When** the visitor presses Escape,
   **Then** the panel closes and focus returns to the launcher control.
4. **Given** a question is submitted, **When** the assistant's answer (or an
   error/loading state) appears, **Then** it is exposed to assistive
   technology as a status update, not silently inserted with no
   announcement.

---

### User Story 5 - Visitor with JavaScript disabled still gets a fully usable public site (Priority: P5)

A visitor browsing with JavaScript disabled (or on a device/network where a
script fails to load) must still be able to read every page and use the
existing site navigation exactly as before this feature — the only thing
missing is the chat widget itself.

**Why this priority**: This is a non-regression guarantee for the site's
existing accessibility promise (established in the prior public-website
feature) rather than new value, so it is validated last, but it is a hard
constraint throughout implementation, not an afterthought.

**Independent Test**: Disable JavaScript (or fetch each page with a plain
HTTP client) and confirm all 8 public pages still render their full content
and navigation identically to before this feature, with no broken layout
or non-functional element left visibly stuck mid-page.

**Acceptance Scenarios**:

1. **Given** JavaScript is disabled, **When** any public page loads,
   **Then** the page's own content and navigation are fully present and
   usable exactly as without this feature.
2. **Given** JavaScript is disabled, **When** the visitor looks for the chat
   launcher, **Then** it is either absent or visibly inert — it never
   renders as a dead control that appears interactive but silently does
   nothing when activated.

---

### Edge Cases

- What happens if the visitor submits an empty or whitespace-only message?
  The widget must not send it to the backend as a question; the send
  control stays disabled or the empty submission is silently ignored.
- What happens if the visitor clicks send, then clicks it again (or presses
  Enter twice) before the first answer returns? Only one request is ever in
  flight per submission; the repeat activation is ignored until the first
  completes or errors.
- What happens if the visitor closes the panel while a question is still in
  flight, then reopens it? The pending request is allowed to complete in the
  background; if it later resolves, the answer is added to the message
  history so it is visible the next time the panel is open (the visitor
  never "loses" an answer they already asked for by closing the panel).
- What happens if the backend response is missing an expected field or is
  not valid JSON? This is treated the same as any other malformed-response
  failure — a generic friendly error, never a raw parsing exception.
- What happens if the backend returns an HTTP status this feature has no
  specific handling for (e.g. a validation error for an over-length
  question)? It falls into the same generic friendly-error fallback as a
  network failure or malformed response (FR-018a) — no distinct message is
  required, and no client-side question-length limit is enforced.
- What happens if a `grounded` answer is returned with an empty sources
  list? The answer is shown normally with no "Źródła:" line, since there is
  nothing to cite.
- What happens if a `grounded` answer's sources list contains the same
  label more than once (e.g. two chunks from the same file)? The displayed
  list shows that label only once, in its first-seen order (FR-009a).
- What happens on a very narrow (e.g. 320px) viewport? The launcher, panel,
  input, and controls all remain reachable and usable without horizontal
  scrolling or overlapping the on-screen keyboard's usable area.
- What happens if the visitor navigates to a different public page while the
  panel is open? The panel itself starts closed again on the new page (it is
  never auto-reopened, so focus is never moved into it without an explicit
  visitor action), but the message history already accumulated is preserved
  and reappears once the visitor reopens the panel on the new page.

## Requirements *(mandatory)*

### Functional Requirements

**Entry point & panel**

- **FR-001**: The system MUST display a persistent chat launcher labeled
  "Zapytaj Albertos" on every public website page, fixed in a consistent,
  non-obtrusive position that never obscures primary page content or
  navigation.
- **FR-002**: The launcher MUST be reachable and operable via keyboard alone
  and MUST carry a clear, descriptive accessible label distinct from its
  visible text if the visible text alone would be ambiguous to assistive
  technology.
- **FR-003**: The launcher MUST remain usable and appropriately sized on
  both mobile and desktop viewport widths.
- **FR-004**: Activating the launcher MUST open a chat panel containing: an
  assistant title, a short scope-explanation notice, the current message
  history, a text input, a send control, and a close control.
- **FR-005**: The panel's scope notice MUST clearly state the assistant only
  answers questions about the club (e.g. training, schedule, trainers,
  sections, club information) and MUST NOT imply it can answer arbitrary
  general-knowledge questions.

**API integration**

- **FR-006**: The system MUST submit every visitor question to the existing
  `POST /api/v1/chat` endpoint and MUST NOT introduce any other backend
  endpoint for chat functionality.
- **FR-007**: The request sent to the backend MUST contain only the question
  text field already accepted by that endpoint's existing contract — the
  widget MUST NOT offer, and the browser MUST NOT be able to submit, any
  control over provider, model, token limits, retrieval depth, system
  prompt, temperature, reasoning/thinking mode, retry behavior, or budget
  settings.
- **FR-008**: Each submitted question MUST be sent as an independent request
  — the widget MUST NOT bundle prior conversation turns into a request
  unless the existing backend contract already natively supports and
  expects that.

**Response handling**

- **FR-009**: For a `grounded` outcome, the widget MUST display the returned
  answer text and, when sources are present, a compact list of their
  labels.
- **FR-009a**: When the returned sources include the same label more than
  once, the compact list MUST show each distinct label only once,
  preserving the order it first appeared in, rather than repeating it.
- **FR-010**: For an `insufficient_information` outcome, the widget MUST
  display a friendly message stating the assistant doesn't have enough
  information to answer, and MUST NOT display a sources list.
- **FR-011**: For an `out_of_scope` outcome, the widget MUST display a
  friendly message reminding the visitor what the assistant can help with,
  and MUST NOT display a sources list.
- **FR-012**: For an `unavailable` outcome (or an equivalent HTTP 503
  response), the widget MUST display a friendly temporary-unavailability
  message.
- **FR-013**: The widget MUST NOT display raw backend exception text, stack
  traces, or internal error identifiers under any outcome.
- **FR-014**: Displayed source labels MUST NOT include internal database
  identifiers or other implementation details — only the human-readable
  label already provided by the backend.

**Session behavior**

- **FR-015**: Message history MUST be kept only in the visitor's browser for
  the duration of their browsing session (surviving navigation between
  public pages in the same tab) and MUST NOT be persisted to any server-side
  store, require an account, or be available across devices or after the
  tab/browser is closed.
- **FR-015a**: The panel's open/closed state MUST NOT persist across page
  navigation — every fresh page load starts with the panel closed,
  regardless of whether it was open on the previous page, even though the
  message history from earlier in the session is still shown once the
  visitor reopens it.

**Loading & duplicate submission**

- **FR-016**: While a question's request is in flight, the widget MUST show
  a visible loading state and MUST prevent a second submission of the same
  or a new question until the first completes or fails.
- **FR-017**: The panel's close control MUST remain usable at all times,
  including while a request is loading or an error is being shown.

**Error handling**

- **FR-018**: The widget MUST handle, with a distinct friendly Polish-
  language message for each: an HTTP 429 (rate-limited) response, an HTTP
  503 / `unavailable` response, a network-level failure (no response
  received), and a response that cannot be parsed as expected.
- **FR-018a**: Any backend response status other than the ones this feature
  defines specific handling for (200, 429, 503) MUST be treated as the same
  generic friendly error used for network failures and unparseable
  responses — a single fallback path, so every possible backend response is
  covered by defined behavior without hardcoding backend-internal limits
  (such as the configured maximum question length) into the client.
- **FR-019**: When an HTTP 429 response includes retry-wait information, the
  widget MAY surface a simple wait message reflecting it; when that
  information is absent, a generic rate-limit message MUST be shown
  instead.
- **FR-020**: After any error state, the visitor MUST be able to submit a
  new question without reloading the page.

**Security**

- **FR-021**: All assistant answer text and source labels returned by the
  backend MUST be treated as untrusted content and inserted into the page
  using a method that cannot execute embedded HTML, scripts, or event
  handlers.
- **FR-022**: The widget MUST NOT render backend-supplied content in any way
  that interprets it as HTML or markup — plain text display only.
- **FR-023**: This feature MUST NOT alter, weaken, or bypass any existing
  backend control (retrieval, answerability, rate limiting, budget
  enforcement, prompt-injection defenses, or administrative authentication).

**Progressive enhancement**

- **FR-024**: Every public page's existing content and navigation MUST
  remain fully present and usable when JavaScript is unavailable, exactly
  as before this feature.
- **FR-025**: The chat widget MAY be entirely unavailable when JavaScript is
  unavailable, but MUST NOT leave the page displaying a visibly broken,
  dead, or misleadingly interactive control in that case.

**Visual design & mobile**

- **FR-026**: The widget's visual design MUST be consistent with the
  existing public website's established look (palette, type, spacing,
  restraint) rather than a generic, off-the-shelf chat-widget appearance.
- **FR-027**: On small viewports, the open panel MAY occupy most of the
  viewport, but the message history MUST remain scrollable and the text
  input, send control, and close control MUST all remain reachable and
  usable with an on-screen keyboard present.
- **FR-028**: The panel MUST NOT take over the entire viewport on desktop
  widths.

**Accessibility**

- **FR-029**: Every interactive control in the widget (launcher, input, send,
  close) MUST be keyboard-operable with a visible focus indicator and a
  clear accessible label.
- **FR-030**: Opening the panel MUST move keyboard focus into it; closing
  the panel MUST return keyboard focus to the launcher.
- **FR-031**: Pressing Escape while the panel is open MUST close it.
- **FR-032**: Loading and error states MUST be exposed to assistive
  technology as status updates where practical, not conveyed by visual
  presentation alone.

### Key Entities

- **Chat Message**: A single turn in the visible conversation — who sent it
  (visitor or assistant), its text, and, for assistant messages, an
  optional list of source labels. Held only in the visitor's browser for the
  duration of the browsing session; never persisted server-side.
- **Chat Session**: The set of chat messages accumulated in one visitor's
  tab since it was opened. Ends when the tab or browser closes; not tied to
  any account or device identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A visitor can go from "question in mind" to "answer or clear
  explanation on screen" on any of the 8 public pages without a full page
  reload.
- **SC-002**: 100% of the 8 public pages expose a keyboard-reachable chat
  launcher with a descriptive accessible label.
- **SC-003**: A keyboard-only visitor can open the panel, submit a question,
  and close the panel again using only Tab, Enter/Space, and Escape.
- **SC-004**: Across all handled outcomes (grounded, insufficient
  information, out of scope, unavailable, rate-limited, network failure,
  malformed response), 0% of visible widget messages contain raw backend
  exception text, stack traces, or internal identifiers.
- **SC-005**: With JavaScript disabled, all 8 public pages remain 100%
  navigable and readable exactly as before this feature, with the chat
  widget simply absent.
- **SC-006**: Displayed source lists never include an internal database
  identifier — 0% occurrence across all grounded responses shown.
- **SC-007**: Rapidly repeated activation of the send control while a
  request is in flight results in exactly one backend request per submitted
  question, never more.
- **SC-008**: The project's full automated test suite, including new tests
  added for this feature, passes without requiring a live LLM provider, GPU,
  or browser-automation tooling.

## Assumptions

- Message history persists across navigation between the site's public
  pages within the same browser tab (via client-side, session-scoped
  storage), and is cleared when the tab or browser is closed — it is never
  written to any server-side store. (Resolved via clarification with the
  feature requester.)
- The existing `POST /api/v1/chat` endpoint's response already distinguishes
  the four outcomes named in this spec (`grounded`,
  `insufficient_information`, `out_of_scope`, `unavailable`) and already
  rejects any request body field beyond the question text — this feature
  relies on, and does not modify, that existing contract.
- If a question's in-flight request is still pending when the visitor closes
  the panel, the request is allowed to complete; its result is added to the
  message history for display the next time the panel is reopened, rather
  than being discarded.
- No fixed cap on stored message history length is required for this MVP;
  a typical single-visit conversation is short enough that unbounded
  in-memory storage for the session's duration is not a practical concern.
- An empty or whitespace-only message is never sent as a question; the send
  control is inert (or the input required) rather than issuing a backend
  request that would be rejected.
- The chat widget appears on every server-rendered public page, including
  any error page (e.g. a 404), since "every public page" is not scoped to
  only the 8 primary pages.
- No proactive greeting, unread-message badge, or attention-drawing
  animation is shown on page load — the launcher stays visually restrained
  until the visitor chooses to open it, consistent with the site's existing
  restrained design language.
