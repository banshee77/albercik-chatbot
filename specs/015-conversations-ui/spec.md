# Feature Specification: Conversations UI

**Feature Branch**: `015-conversations-ui`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Feature 015 — Conversations UI: replace the Shiruno Admin Platform's Feature 013 Conversations placeholder with a complete, read-only, tenant-scoped conversation-review screen — browse, search, filter by outcome and date, paginate, and inspect conversation detail (question, answer, outcome, grounded sources, and safe operational metadata) — consuming the existing Feature 011 Conversations API exactly as it exists today, without redesigning the backend, without exposing RAG/trace/provider internals, and without becoming a second security boundary."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator sees how visitors are using the assistant (Priority: P1)

A customer administrator opens Conversations from the application shell and immediately sees a readable, newest-first list of recent interactions between visitors and their assistant — what was asked, and in plain language whether it was answered — without needing to understand retrieval, embeddings, or providers.

**Why this priority**: This is what turns the Feature 013 placeholder into a real product surface. Nothing else in this feature is reachable without it, and it delivers standalone value for any tenant that already has conversation history.

**Independent Test**: Log in as a tenant administrator whose tenant has conversation records, open Conversations, and confirm the list reflects that tenant's real, newest-first data from the existing Feature 011 API, with an intentional loading state beforehand and a distinct empty state if the tenant has none.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator whose tenant has conversation records, **When** they open Conversations, **Then** they see a list of recent conversations ordered newest-first, each showing its question, a human-readable outcome label (not a raw backend enum value, and not conveyed by color alone), and when it happened.
2. **Given** the Conversations list is loading its initial data, **When** the response has not yet arrived, **Then** the administrator sees an explicit loading state, never a blank page and never the empty state shown prematurely.
3. **Given** a tenant with no conversation records at all, **When** the administrator opens Conversations, **Then** they see a clear "no conversations yet" state, distinct from a filtered-empty result.
4. **Given** the backend is unreachable or returns an error while loading the list, **When** that failure occurs, **Then** the administrator sees a safe, generic failure message with a way to retry, and no stale or fabricated data is shown as if the request had succeeded.

---

### User Story 2 - Administrator inspects one conversation in full (Priority: P1)

An administrator selects a conversation from the list and reviews its full detail — the visitor's question, the assistant's answer, its outcome, and (when relevant) which knowledge sources grounded the answer and what it cost to produce — without losing their place in the list.

**Why this priority**: Understanding *why* an interaction turned out the way it did is the feature's core value; a list of questions and outcome labels alone does not let an administrator judge assistant quality or spot a knowledge gap.

**Independent Test**: From a loaded list, select a grounded conversation and confirm its detail view shows the question, the answer, the outcome, its historical source labels, and its operational metadata (latency, provider, model, tokens) exactly as returned by the existing detail API — then close it and confirm the list is unchanged.

**Acceptance Scenarios**:

1. **Given** an administrator has the conversation list open, **When** they select a conversation, **Then** its detail loads and displays independently of the list (the list remains visible/usable and is not replaced by a full page navigation or a page-wide loading state).
2. **Given** a selected conversation is "Answered" (grounded), **When** its detail loads, **Then** the administrator sees the question and answer displayed clearly and separately, plus the historical source labels recorded for that specific interaction — never sources reconstructed from the tenant's current knowledge base.
3. **Given** a selected conversation has operational data available (latency, provider, model, token counts), **When** the detail is shown, **Then** that data appears in a compact, clearly-labeled area that does not visually dominate the question and answer.
4. **Given** a selected conversation has no LLM usage to report (e.g., small talk), **When** the detail is shown, **Then** the absence of that data is presented naturally (e.g., omitted or marked not applicable) — never as a zero value invented by the frontend.
5. **Given** detail loading fails for a selected conversation, **When** the failure occurs, **Then** the administrator sees a safe, generic detail-level error while the underlying list remains fully usable, and the failure is never interpreted or displayed as evidence that a conversation belonging to another tenant exists.
6. **Given** the administrator closes the open detail, **When** they return to the list, **Then** their current search text, outcome filter, date range, and page are all exactly as they were before the conversation was opened.

---

### User Story 3 - Administrator narrows the list to find what they're looking for (Priority: P2)

An administrator searches for conversations containing a particular word or phrase, filters the list to a specific outcome (e.g., only knowledge gaps), and/or restricts it to a date range, to answer a specific question about assistant usage rather than scrolling the full history.

**Why this priority**: Valuable for real investigative use once conversation volume grows, but a tenant can already get value from Story 1 and 2 alone on a smaller history; filtering refines the experience rather than gating first use.

**Independent Test**: With a loaded list, enter a search term and confirm the list reflects a fresh server-side query for that term (not a client-side filter of already-loaded rows); clear it and confirm the full list returns; apply an outcome filter and confirm only matching results are requested and shown; apply a date range and confirm it is sent to the API; confirm each of these resets the list back to its first page.

**Acceptance Scenarios**:

1. **Given** the administrator types a search term into the question search field and submits it, **When** the search executes, **Then** the list re-queries the backend's search capability for that term and displays only matching results, returning to the first page.
2. **Given** an active search term, **When** the administrator clears it, **Then** the unfiltered (or otherwise-filtered) list is restored via a fresh server query, not a locally cached copy.
3. **Given** the administrator selects an outcome filter (e.g., "Knowledge gap"), **When** the filter is applied, **Then** only conversations of that backend outcome are requested and shown, and the list returns to its first page.
4. **Given** the administrator sets a "from" and/or "to" date, **When** the range is applied, **Then** it is sent to the backend as the effective filter for the list request, and the list returns to its first page.
5. **Given** search text, an outcome filter, and/or a date range are active and together match no conversations, **When** the list loads, **Then** the administrator sees a "no conversations match the selected filters" state — visibly distinct from the "no conversations yet" state — with a clear way to clear the active filters.
6. **Given** filters are cleared from the filtered-empty state, **When** the clear action is used, **Then** the list reloads unfiltered from the first page.

---

### User Story 4 - Administrator pages through a large volume of conversations (Priority: P2)

An administrator moves forward and backward through pages of results using simple Previous/Next controls, always drawing from the backend's own paginated results rather than the whole tenant history at once.

**Why this priority**: Necessary once a tenant accumulates more conversations than fit on one screen, but the feature is still useful for a smaller tenant without it; it is a scaling refinement layered on Stories 1–3.

**Independent Test**: With enough conversation records to span multiple pages, confirm Next loads the next bounded page from the backend, Previous returns to the prior one, Previous is disabled on the first page, Next is disabled on the last page, and no request ever asks the backend for an unbounded result set.

**Acceptance Scenarios**:

1. **Given** more results exist than fit on the current page, **When** the administrator selects Next, **Then** the next page of results loads from the backend with the same active search/filter/date state.
2. **Given** the administrator is on a page after the first, **When** they select Previous, **Then** the prior page loads.
3. **Given** the administrator is on the first page of results, **When** the list is shown, **Then** Previous is disabled and communicated as such (not merely styled differently).
4. **Given** the administrator is on the last page of available results, **When** the list is shown, **Then** Next is disabled and communicated as such.
5. **Given** any list request (initial, searched, filtered, or paginated), **When** it is issued, **Then** it always requests a bounded page of results, never the tenant's full conversation history in one call.

---

### User Story 5 - A session that expires mid-browse is handled safely (Priority: P3)

While browsing, searching, filtering, paginating, or viewing a conversation's detail, an administrator's session becomes invalid. Conversations notices via the existing centralized handling, clears its state, and returns the administrator to login — never leaving previously-loaded conversation content on screen.

**Why this priority**: Reuses Feature 013's existing centralized session-expiration mechanism rather than introducing new behavior; it is a safety net around the higher-priority stories above, not a new user journey.

**Independent Test**: While a list or detail request is in flight, simulate the backend rejecting it for authentication reasons, and confirm the administrator is redirected to login with no conversation content left visible.

**Acceptance Scenarios**:

1. **Given** an administrator on the Conversations page, **When** any conversation request (initial load, search, filter, date range, pagination, or detail) is rejected for authentication reasons, **Then** the frontend clears authenticated state and redirects to login exactly as Feature 013's existing mechanism already does elsewhere in the shell.
2. **Given** a conversation's question, answer, or metadata was visible when the session was invalidated, **When** the redirect happens, **Then** none of that content remains visible afterward.

---

### Edge Cases

- What happens when a conversation's outcome is `unavailable` and the backend recorded no safe failure category? → The administrator sees a safe, generic "Assistant unavailable" state without a category detail, never a fabricated reason.
- What happens when a grounded conversation's historical source snapshot is empty? → No sources are shown and none are invented from the tenant's current knowledge base; the section is simply omitted or shown as having none.
- What happens when the administrator sets a "from" date later than the "to" date? → The date range control communicates the invalid state clearly and does not silently submit a query the backend would reject or misinterpret.
- What happens when a selected conversation's detail request returns "not found" (e.g., a cross-tenant ID guessed by URL manipulation, or a record removed by backend policy)? → The administrator sees the same safe detail-level error as any other detail failure; the UI never treats a 404 as confirmation that a foreign-tenant conversation exists.
- What happens when the administrator reopens detail for a different conversation while one is already open? → The panel updates to the newly selected conversation's own detail and loading/error state, without corrupting the underlying list's search/filter/date/page state.
- What happens when the backend returns an outcome value the frontend does not explicitly recognize? → It is shown using a safe, generic fallback label rather than being guessed as one of the five known outcomes.
- What happens on a narrow viewport? → The list and detail remain usable (e.g., detail becomes a full-width stacked view) without requiring a separate mobile application.
- What happens if the administrator submits an empty search after having typed a term? → The list returns to its unfiltered (or otherwise still-active-filtered) state via a fresh server query, not by hiding rows client-side.

## Requirements *(mandatory)*

### Functional Requirements

**Conversation list**

- **FR-001**: The system MUST display, on the Conversations page, a list of the authenticated administrator's own tenant's conversation records only, exactly as returned by the existing tenant-scoped conversation-list data, ordered newest-first as provided by the backend.
- **FR-002**: The system MUST NOT independently re-sort the list in a way that contradicts the backend's ordering.
- **FR-003**: Each row MUST show, at minimum, the visitor's question, a human-readable outcome label, and when the conversation occurred; the system MUST NOT display a raw internal tenant identifier, raw provider metrics, request internals, or the full answer text in the list.
- **FR-004**: The system MUST show an explicit loading state during the list's initial load, distinct from both the empty state and the loaded-with-data state, and MUST NOT show the empty state before the first request completes.
- **FR-005**: When the tenant has no conversation records at all, the system MUST show an intentional "no conversations yet" state.
- **FR-006**: When a list request fails, the system MUST show a safe, generic user-facing error with a way to retry, and MUST NOT render raw backend exception text or display stale/empty data as if the request had succeeded.

**Outcome presentation**

- **FR-007**: The system MUST map each backend outcome value (`grounded`, `insufficient_information`, `out_of_scope`, `unavailable`, `small_talk`) to a human-friendly, customer-facing label, and MUST NOT display the raw backend enum string anywhere in the list or detail view.
- **FR-008**: Outcome MUST be distinguishable without relying on color alone (e.g., accompanying text or an icon with a text label).
- **FR-009**: If the backend returns an outcome value the frontend does not explicitly recognize, the system MUST present it using a safe, generic fallback label rather than guessing one of the known outcomes.

**Search**

- **FR-010**: The system MUST provide an accessible, labeled search control over the visitor's question text that queries the backend's existing search capability; it MUST NOT filter only the currently-loaded page of results on the client.
- **FR-011**: Submitting a search MUST reset the list to its first page while preserving any other active filters.
- **FR-012**: Clearing the search term MUST restore the list to its unfiltered (or otherwise still-active-filtered) state via a fresh server request.

**Outcome filter**

- **FR-013**: The system MUST provide a way to filter the list by outcome, including an "All" option, using the backend's existing filter contract; applying it MUST NOT fetch the unfiltered list and filter it locally.
- **FR-014**: Applying or changing the outcome filter MUST reset the list to its first page while preserving any other active filters.

**Date range filter**

- **FR-015**: The system MUST provide a simple "from" / "to" date range control compatible with the backend's date filter contract; the system MUST NOT request an unbounded history by default beyond whatever default the backend itself applies.
- **FR-016**: Applying or changing the date range MUST reset the list to its first page while preserving any other active filters.
- **FR-017**: If the administrator sets an invalid date range (e.g., "from" later than "to"), the system MUST handle this intentionally (e.g., prevent submission with a clear message) rather than silently submitting it.

**Pagination**

- **FR-018**: The system MUST use the backend's own pagination mechanism, providing Previous and Next controls; it MUST NOT implement infinite scrolling or fetch more than one bounded page per request.
- **FR-019**: Every list request the client issues (initial, searched, filtered, or paginated) MUST request a bounded page of results; the client MUST NOT request an unbounded result set.
- **FR-020**: Previous MUST be disabled, with that disabled state clearly communicated, when no earlier page exists; Next MUST be disabled, with that disabled state clearly communicated, when no later page exists.

**Empty and filtered-empty states**

- **FR-021**: When search, outcome, and/or date filters are active and match no conversations, the system MUST show a "no conversations match the selected filters" state, visibly distinct from the "no conversations yet" state, and MUST offer a clear way to clear the active filters.

**Conversation detail**

- **FR-022**: Selecting a conversation MUST load its detail from the existing tenant-scoped conversation-detail data, independently of the list (the list MUST remain visible and usable; opening detail MUST NOT block or replace the whole page).
- **FR-023**: Conversation detail MUST have its own loading state, distinct from the list's loading state.
- **FR-024**: Conversation detail MUST display, at minimum: the question, the answer, the outcome (using the same human-readable mapping as the list), and when the conversation occurred.
- **FR-025**: The system MUST NOT display, anywhere in conversation detail: a raw internal tenant identifier, raw authentication data, raw provider exception text, hidden model reasoning, raw OpenTelemetry/trace internals, or raw retrieval/embedding/chunk data.
- **FR-026**: When a detail request fails, the system MUST show a safe, generic detail-level error while the list remains usable, and MUST NOT treat a "not found" response as confirmation that a conversation belonging to another tenant exists.
- **FR-027**: Closing the detail view MUST return the administrator to the list with its current search text, outcome filter, date range, and page unchanged.

**Grounded sources**

- **FR-028**: For a conversation whose outcome is grounded, the system MUST display the historical source labels exactly as recorded for that specific interaction (the point-in-time snapshot), and MUST NOT reconstruct or infer sources from the tenant's current knowledge base state.
- **FR-029**: If a grounded conversation's recorded source snapshot is empty, the system MUST NOT fabricate source labels; it MUST present the absence naturally.
- **FR-030**: The system MUST NOT display source labels for a non-grounded conversation unless the backend actually returned them for that record.

**Outcome-specific detail presentation**

- **FR-031**: For `insufficient_information`, the system MUST present a "Knowledge gap" state that indicates the assistant could not answer from the knowledge available at the time, and MUST NOT phrase this as the assistant having given a wrong answer.
- **FR-032**: For `out_of_scope`, the system MUST present a neutral label indicating the request was outside the assistant's scope, and MUST NOT phrase this as a system failure.
- **FR-033**: For `unavailable`, the system MUST present a safe, customer-understandable operational state (e.g., "Assistant unavailable"), optionally reflecting a safe failure category if the backend provided one, and MUST NOT display raw provider exception text or internal URLs.
- **FR-034**: For `small_talk`, the system MUST display the conversation like any other, and MUST NOT show fabricated provider, model, or token data where the backend recorded none.

**Operational metadata**

- **FR-035**: Where present on a conversation, the system MUST display response latency, provider, model, input tokens, and output tokens in a compact, clearly-labeled metadata area that does not visually dominate the question and answer content.
- **FR-036**: Where a piece of operational metadata is absent for a given conversation (e.g., no LLM call occurred), the system MUST present its absence naturally rather than inventing a placeholder or zero value.
- **FR-037**: The system MUST NOT display raw `provider_metrics` (or any other raw provider-internal payload) anywhere in conversation detail.

**Request ID**

- **FR-038**: If shown, the request identifier MUST be presented in a secondary, non-prominent area of the detail view (e.g., a "Technical details" section) and MUST be copyable; the system MUST NOT display a trace identifier or a link into an observability tool.

**Centralized API boundary & types**

- **FR-039**: All conversation list and detail network requests MUST go through a centralized frontend API module dedicated to conversations, itself built on the existing shared API client (base URL, authentication header, 401/403 handling, safe error mapping); no component MUST issue a request for conversation data directly.
- **FR-040**: Frontend types describing conversation list and detail data MUST mirror the public admin API contract's fields, not internal persistence-model fields.

**Tenant boundary**

- **FR-041**: The system MUST NOT send a tenant identifier on any conversation list or detail request as a way to select or scope data, MUST NOT provide a tenant selector control, and MUST NOT construct a conversation request using a tenant slug or ID; all scoping remains enforced by the authenticated backend identity.

**Session lifecycle**

- **FR-042**: If a conversation request (initial load, search, filter, date range, pagination, or detail) is rejected for authentication reasons, the system MUST invalidate the frontend's authenticated state and redirect to login using the existing centralized session-expiration handling.
- **FR-043**: When a session is invalidated while conversation content is visible, the system MUST NOT continue displaying that content after the redirect.

**Privacy**

- **FR-044**: The system MUST NOT write conversation questions, answers, or other conversation content to the browser console, MUST NOT persist conversation content in local or session storage, MUST NOT send it to any third-party frontend analytics service, and MUST NOT include it in a URL query string.

**Accessibility & responsiveness**

- **FR-045**: The search input, outcome filter, date range controls, and Previous/Next controls MUST each be operable using the keyboard alone and MUST have accessible labels; Previous/Next MUST expose their disabled state through an accessible mechanism, not styling alone.
- **FR-046**: Conversation rows MUST be keyboard-reachable and operable to open detail.
- **FR-047**: The detail view MUST use a clear heading structure, MUST move focus into itself intentionally when opened, and MUST return focus appropriately when closed.
- **FR-048**: The Conversations page MUST remain usable on narrower desktop/laptop-class viewport widths, adapting the list/detail layout (e.g., a stacked or full-width detail view) without requiring a separate mobile application.

**Non-mutation & non-regression**

- **FR-049**: This feature MUST be read-only: it MUST NOT provide any way to edit a question or answer, delete a conversation record, rerun or regenerate an answer, manually change an outcome, alter recorded sources, or attach notes, tags, or assignments.
- **FR-050**: This feature MUST NOT change the semantics, behavior, or contract of the public chat endpoint, conversation recording, Knowledge administration, RAG behavior, public source hiding, or observability instrumentation.
- **FR-051**: This feature MUST NOT change the existing Feature 011 Conversations API's contract; any backend change is only acceptable if it is additive, tenant-safe, and required by a genuine gap that cannot be solved in the frontend alone.

### Key Entities

- **Conversation Summary (as presented)**: One tenant-owned interaction as it appears in the list — question, human-readable outcome label, and timestamp (and latency where useful). Never includes the full answer, raw outcome enum text, raw provider metrics, or the tenant's internal identifier.
- **Conversation Detail (as presented)**: The full record of one interaction as the administrator sees it — question, answer, outcome, timestamp, historical grounded source labels (grounded only), and operational metadata (latency, provider, model, input/output tokens) where recorded. A point-in-time snapshot, never re-derived from the tenant's current knowledge base or provider configuration.
- **Grounded Source Label**: One source label recorded historically against a specific grounded conversation at the time it was answered. Admin-only; never reconstructed from current Knowledge state.
- **Operational Metadata**: The safe, customer-understandable subset of response latency, provider, model, and token usage associated with one conversation. Excludes raw `provider_metrics` and any other provider-internal payload.
- **Outcome**: One of the backend's five recognized interaction outcomes (`grounded`, `insufficient_information`, `out_of_scope`, `unavailable`, `small_talk`), each mapped to a distinct, non-color-only, customer-facing label.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can locate a specific past conversation among recent history using search, an outcome filter, or a date range — or a combination — in a single filtering action, verified by automated tests.
- **SC-002**: 100% of outcomes shown in the list and detail views use a human-readable label; 0% render the raw backend enum string, verified by automated tests.
- **SC-003**: 100% of conversations and their detail shown to an administrator originate from that administrator's own tenant-scoped data — never a client-supplied, cached-elsewhere, or cross-tenant value — verified by automated tests.
- **SC-004**: 0% of backend failures surfaced on the Conversations page (list or detail) include raw exception text, a stack trace, an internal URL, or a raw provider payload, verified by automated tests covering both list and detail failure paths.
- **SC-005**: Opening and then closing a conversation's detail never changes the underlying list's active search text, outcome filter, date range, or current page, verified by an automated test.
- **SC-006**: Every list request issued by the client requests a bounded page of results; 0% of requests omit a page-size bound, verified by an automated test.
- **SC-007**: Grounded conversation detail displays only the historical source snapshot recorded for that interaction; 0% of displayed sources are derived from the tenant's current knowledge base state, verified by an automated test.
- **SC-008**: Every interactive element in the search, filter, pagination, and detail-open/close flows is operable using the keyboard alone, verified by automated tests.
- **SC-009**: A session invalidated during any list, search, filter, pagination, or detail interaction always results in the administrator being returned to login with no previously-visible conversation content remaining on screen, verified by an automated test.
- **SC-010**: The production frontend build, type check, and lint all complete successfully with zero errors, verified by an automated build gate.
- **SC-011**: The full pre-existing backend automated test suite (Feature 011 conversations/analytics, Feature 012 observability, tenant isolation, public chat contract) continues to pass unmodified in intent.

## Assumptions

- Exact outcome label wording is finalized during planning using this specification's suggested defaults (`grounded` → "Answered", `insufficient_information` → "Knowledge gap", `out_of_scope` → "Out of scope", `unavailable` → "Assistant unavailable", `small_talk` → "Small talk") unless planning identifies a clearly better customer-facing phrasing.
- The request identifier, when shown, is kept in a secondary "Technical details" area rather than shown prominently by default, per this specification's preferred direction; planning may adjust the exact placement so long as it remains non-prominent and copyable.
- The conversation detail view's presentation mechanism (inline side panel, drawer, or another lightweight pattern) is left to the planning phase to decide based on what best fits the existing Feature 013 shell and Feature 014's precedent, consistent with this project's practice of deferring pure implementation-shape decisions to `/speckit-plan`.
- Whether filter/detail state is kept in React state only or reflected in the URL is left to planning; if URL state is adopted, it must be applied consistently and tested, and no new global state-management library is introduced solely for this purpose.
- No new backend endpoint or database entity is required for this feature; it consumes the existing Feature 011 Conversations API as-is. Any backend change surfaced during planning is expected to be additive and narrowly scoped, not a redesign of `ConversationRecord`.
- The backend's `/conversations` list endpoint applies no default or maximum lookback window when no date range is supplied (unlike the separate analytics endpoints); this specification does not add a client-side default date restriction beyond what the backend itself enforces.
- Analytics Dashboard (Feature 016) remains out of scope; this feature does not implement aggregate knowledge-gap charts, topic clustering, or sentiment analysis.
- The following are explicitly out of scope for this feature and are not addressed by its requirements: conversation mutation of any kind (edit, delete, rerun, manual outcome change, notes/tags/assignment), CSV/JSON/PDF export, real-time updates (WebSockets, SSE, or polling), a threaded multi-message conversation view, a raw RAG/trace/prompt/chunk viewer, Phoenix integration within Admin, a tenant switcher, and any new client-side data-fetching or state-management library adopted merely for this feature's own convenience. Each remains a possible future, separately-justified addition.
