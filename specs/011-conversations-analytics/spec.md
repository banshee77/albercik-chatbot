# Feature Specification: Conversations & Analytics

**Feature Branch**: `011-conversations-analytics`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Feature 011 — Conversations & Analytics: persist and expose tenant-scoped conversation data (durable per-request records, admin conversation browsing, conversation detail with admin-only sources, analytics summary, knowledge gaps, most common questions, tenant-safe usage/cost visibility) on top of the Feature 009 tenant boundary and Feature 010 knowledge administration, backend-first, no frontend."

## Clarifications

### Session 2026-08-20

- Q: Which chat requests should get a persisted conversation record? → A: Only the five ChatResponse outcomes (grounded, insufficient_information, out_of_scope, unavailable, small_talk). Rate-limited (429) and payload/validation-rejected (400/413) requests — which never reach outcome classification at all today — are not persisted as conversation records.
- Q: Should an "unavailable" conversation record distinguish *why* the assistant was unavailable, or stay a single generic category? → A: Distinguish it with a small, safe failure-category breakdown (provider_error, budget_exceeded, kill_switch, concurrency_limit) rather than one undifferentiated category.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator reviews what visitors are asking (Priority: P1)

An administrator opens their conversation history and sees a chronological record of what their organization's visitors have asked the assistant, how each question was answered (grounded, insufficient information, out of scope, small talk, or unavailable), and when. They can filter by outcome, filter by date range, and search for specific wording, without ever seeing another organization's conversations.

**Why this priority**: This is the foundational transparency capability the rest of the feature depends on — without a trustworthy, tenant-scoped record of what happened, nothing else (analytics, knowledge gaps, common questions) can exist or be verified.

**Independent Test**: As an authenticated administrator, request the conversation list; confirm it reflects only your own organization's conversations, newest first, with accurate outcomes, and that filtering by outcome, by date range, and searching by question text all narrow the results correctly, including the case of zero matches.

**Acceptance Scenarios**:

1. **Given** an administrator's organization has had visitor conversations with a mix of outcomes, **When** they request the conversation list, **Then** each item shows at minimum its question, outcome, and when it happened, ordered newest first.
2. **Given** an administrator's organization has had no conversations yet, **When** they request the conversation list, **Then** they receive a valid empty result, not an error.
3. **Given** a conversation list request, **When** the administrator filters by outcome, by a date range, or searches by question text, **Then** only matching conversations for their own organization are returned.
4. **Given** an organization with more conversations than fit on one page, **When** an administrator pages through results, **Then** the results are complete, non-duplicated, and bounded to a reasonable maximum page size regardless of what the client requests.

---

### User Story 2 - Administrator inspects a single conversation in detail (Priority: P1)

An administrator opens one specific conversation to see exactly what was asked, what the assistant answered, how long it took, and — for a grounded answer — which of their knowledge documents supported it.

**Why this priority**: Understanding *why* the assistant answered the way it did (especially which sources it used) is the core diagnostic capability administrators need to trust and improve their knowledge base; it is equally P1 because the list view alone cannot deliver this value.

**Independent Test**: As an authenticated administrator, open a specific conversation belonging to your organization and confirm it shows the full question/answer/outcome plus operational metadata (timing, and — for a grounded answer — the source documents that supported it); confirm the same request against a nonexistent, or another organization's, conversation fails safely.

**Acceptance Scenarios**:

1. **Given** a grounded conversation belonging to an administrator's own organization, **When** they open its detail, **Then** they see the question, the answer, and the specific knowledge sources that supported the answer.
2. **Given** an insufficient-information, out-of-scope, small-talk, or unavailable conversation belonging to an administrator's own organization, **When** they open its detail, **Then** they see the question, the outcome, and the public answer actually shown to the visitor, without any fabricated source list.
3. **Given** an administrator, **When** they request the detail of a conversation that does not exist, **Then** the request fails safely with no further detail revealed.
4. **Given** an administrator, **When** they request the detail of a conversation belonging to a different organization, **Then** the request fails exactly the same way as requesting a nonexistent conversation.

---

### User Story 3 - Administrator sees an at-a-glance analytics summary (Priority: P1)

An administrator opens an analytics summary for a chosen date range and immediately understands how much their assistant is being used, how often it successfully answers versus falls short, how fast it responds, and how much of the underlying paid usage (tokens, provider, model) it is consuming.

**Why this priority**: Aggregate understanding is what turns raw conversation logs into an operational signal an administrator can act on day-to-day, without reading every individual conversation.

**Independent Test**: As an authenticated administrator, request the analytics summary for a date range; confirm the returned totals, outcome counts/rates, latency figures, and token/provider usage accurately reflect only your own organization's conversations in that range, including the case of zero activity.

**Acceptance Scenarios**:

1. **Given** an administrator's organization has a mix of outcomes over a date range, **When** they request the analytics summary for that range, **Then** it reports the total number of requests, a count and rate for each outcome, and latency and token/provider usage aggregates, all correct for that range.
2. **Given** an administrator's organization has had no activity in a chosen date range, **When** they request the summary, **Then** it returns a valid, clearly-zeroed result rather than an error.
3. **Given** no date range is supplied, **When** an administrator requests the summary, **Then** a sensible, documented default range is applied rather than scanning unbounded history.
4. **Given** small-talk conversations exist in the range, **When** the summary aggregates token/provider usage, **Then** small-talk conversations contribute to the request count but never to token or provider cost figures.

---

### User Story 4 - Administrator identifies recurring knowledge gaps (Priority: P1)

An administrator wants to know what their assistant repeatedly fails to answer, so they know what knowledge to add next. They open a knowledge-gaps view and see which questions (or clearly-equivalent variants of the same question) most often resulted in "insufficient information," ranked by how often they occur.

**Why this priority**: This closes the loop between conversation data and Feature 010's knowledge administration — it is the single most actionable output of this feature, directly answering "what should I add to my knowledge base next," so it carries the same priority as visibility itself.

**Independent Test**: As an authenticated administrator, seed a set of insufficient-information conversations (some identical, some differing only in case/whitespace, some genuinely different) and confirm the knowledge-gaps view groups and ranks them deterministically by frequency, using only your own organization's data.

**Acceptance Scenarios**:

1. **Given** an organization has multiple insufficient-information conversations, some of which are the same question repeated with different casing or spacing, **When** an administrator requests knowledge gaps, **Then** those variants are grouped together as one recurring gap, ranked by how often they occurred.
2. **Given** an organization has no insufficient-information conversations in the selected range, **When** an administrator requests knowledge gaps, **Then** they receive a valid empty result, not an error.
3. **Given** grounded, out-of-scope, small-talk, or unavailable conversations exist alongside insufficient-information ones, **When** an administrator requests knowledge gaps, **Then** only insufficient-information conversations contribute to the result.

---

### User Story 5 - Administrator reviews the most common questions overall (Priority: P2)

An administrator wants to understand what visitors ask most often overall — not just what the assistant fails to answer — to understand real usage patterns.

**Why this priority**: Valuable usage insight that complements the knowledge-gaps view, but secondary to understanding failures, which are more directly actionable.

**Independent Test**: As an authenticated administrator, seed a set of repeated and distinct questions across outcomes and confirm the most-common-questions view ranks them deterministically by frequency for a selected date range, using only your own organization's data.

**Acceptance Scenarios**:

1. **Given** an organization has some questions asked multiple times and others asked once, **When** an administrator requests the most-common-questions view for a date range, **Then** the most frequently asked questions are ranked first, deterministically.
2. **Given** no date range is supplied, **When** an administrator requests this view, **Then** the same documented default range used elsewhere in analytics applies.

---

### User Story 6 - No administrator can ever reach another organization's conversation or analytics data (Priority: P1)

Regardless of which capability is used — conversation list, conversation detail, analytics summary, knowledge gaps, common questions, or usage/provider metrics — an administrator from one organization can never see, infer the existence of, or affect another organization's data, even when they know or guess an identifier.

**Why this priority**: This is the non-negotiable security guarantee the entire feature exists inside of, mirroring the platform's existing tenant-isolation guarantee; every other story's value depends on this holding without exception.

**Independent Test**: With two organizations each holding their own conversation history, confirm systematically that every capability in this feature, when used by one organization's administrator, never surfaces the other organization's data, and that a cross-organization detail lookup is indistinguishable from a lookup of a nonexistent record.

**Acceptance Scenarios**:

1. **Given** two organizations each with their own conversation history, **When** one organization's administrator lists conversations, views a conversation's detail, requests the analytics summary, requests knowledge gaps, requests common questions, or reviews usage/provider metrics, **Then** only their own organization's data is ever visible.
2. **Given** an administrator, **When** their request includes an organization identifier in the body, query string, or headers, **Then** that value is disregarded entirely in favor of their authenticated organization.
3. **Given** a cross-organization conversation-detail attempt, **When** it is rejected, **Then** the response is indistinguishable from the response for a nonexistent conversation.

---

### User Story 7 - Everything that already worked keeps working (Priority: P1)

Every visitor chatting with the assistant, and every previously existing capability (public chat outcomes, small talk, source hiding, tenant isolation, knowledge administration), continues to behave exactly as before — this feature only adds an invisible recording layer and new administrator-facing read capabilities on top of the existing foundation. A conversation-recording problem must never make a visitor's chat experience worse.

**Why this priority**: This is a feature built directly on top of a live, working system, and it introduces a new write path (conversation persistence) on the public chat request. Regressing public chat behavior or reliability, or previously-shipped administrator capability, would be a failure regardless of how well the new analytics capabilities work.

**Independent Test**: Run the full existing automated suite (public chat outcomes, small talk, rate limiting, budget, tenant isolation, knowledge administration) unmodified in intent and confirm every test still passes; separately confirm a visitor still receives a normal, successful chat response even in a scenario where conversation recording itself cannot complete.

**Acceptance Scenarios**:

1. **Given** the public assistant, **When** a visitor asks a question that previously produced any existing outcome, **Then** the same question produces the same outcome and the same visible answer as before this feature.
2. **Given** the public chat widget, **When** a grounded answer is shown, **Then** source-hiding behavior and assistant identity/avatar presentation remain exactly as before this feature.
3. **Given** a scenario where conversation recording cannot complete for a given request, **When** the visitor's underlying chat answer was otherwise successfully produced, **Then** the visitor still receives that successful answer.
4. **Given** the existing tenant-isolation, knowledge-administration, rate-limit, budget, and provider tests, **When** the full automated suite runs, **Then** all of them still pass, unmodified in intent.

---

### Edge Cases

- What happens if a chat request succeeds (the visitor gets an answer) but the conversation record itself cannot be written? → The visitor's answer is unaffected; the gap is logged operationally so it is not silently invisible, without exposing conversation content in that log.
- What happens to a grounded conversation's recorded sources when the underlying knowledge document is later replaced or deleted? → The conversation's historical record continues to show the source evidence as it existed at answer time; it does not silently disappear or get reattributed to different content.
- What happens when an administrator requests knowledge gaps or common questions for a date range with no matching activity? → A valid empty result is returned, not an error.
- What happens when an administrator's search or filter combination matches nothing? → A valid empty result is returned, not an error.
- What happens when an administrator requests a page of conversations beyond the last available page? → A valid empty result is returned, not an error.
- What happens for a small-talk conversation when analytics aggregate token usage or provider/model breakdowns? → It contributes to overall request volume but contributes zero tokens and no provider/model usage row, since no paid provider call occurred.
- What happens for an unavailable (provider failure) conversation? → It is recorded with a safe, generic failure classification only; no raw provider error text, credentials, or internal detail is ever persisted or exposed.
- What happens if a public request includes an organization identifier of any kind? → It has no effect; ownership is always derived from the server-resolved public reference tenant.
- What happens to a request that is rejected by rate limiting, or by request-size/question-length validation, before it reaches outcome classification? → No conversation record is created for it; only requests that reach one of the five defined outcomes are persisted.
- What happens when the assistant is unavailable for different underlying reasons (provider failure vs. budget exhausted vs. kill switch vs. concurrency limit)? → Each is recorded with its own safe failure category, not collapsed into one undifferentiated case, so administrators can distinguish self-imposed throttling from an actual provider outage.

## Requirements *(mandatory)*

### Functional Requirements

**Conversation persistence**

- **FR-001**: System MUST persist a durable record for every public chat request that reaches one of the five defined outcomes (grounded, insufficient information, out of scope, unavailable, small talk), capturing at minimum: a stable identifier, the owning organization, the request's correlation identifier, the visitor's submitted question, the outcome, the assistant's public answer, and when it occurred.
- **FR-001a**: A request rejected before outcome classification — for example by rate limiting, or by request-size/question-length validation — MUST NOT produce a conversation record; these rejections never reach a request-correlated outcome today and persisting them would create an unauthenticated public write surface with no bound tied to legitimate usage.
- **FR-002**: Every persisted conversation record MUST belong to exactly one organization, with that ownership derived entirely server-side — never supplied or influenced by the public client.
- **FR-003**: Conversation persistence MUST NOT reduce the reliability of the public chat experience: a chat answer that was otherwise successfully produced MUST still reach the visitor even if the conversation record itself cannot be written.
- **FR-004**: A conversation-persistence failure MUST be logged operationally (so it is not silently invisible) without exposing conversation question/answer content in that log.

**Outcome-specific storage**

- **FR-005**: A grounded conversation's record MUST retain the question, the answer, and the specific knowledge source evidence that supported the answer at the time it was produced.
- **FR-006**: An insufficient-information conversation's record MUST retain the question and the actual public answer shown, and MUST NOT contain fabricated source evidence.
- **FR-007**: An out-of-scope conversation's record MUST retain the question and the actual public answer shown.
- **FR-008**: A small-talk conversation's record MUST retain the question and answer, MUST be identifiable by its outcome, and MUST NOT record any token usage or provider/model attribution, since no paid provider call occurs for small talk.
- **FR-009**: An unavailable conversation's record MUST retain the question, the safe public error response shown, and a safe failure category distinguishing *why* the assistant was unavailable (at minimum: provider error, budget exceeded, kill switch engaged, or concurrency limit reached); it MUST NOT retain raw provider exception text, stack traces, credentials, or any provider endpoint detail.
- **FR-010**: A grounded conversation's recorded source evidence MUST remain historically stable even if the underlying knowledge document is later replaced or deleted — it MUST NOT be recomputed from current knowledge-base state.

**Privacy by default**

- **FR-011**: Conversation records MUST NOT contain more than the observable application-level inputs, outputs, and safe operational metadata needed for this feature's stated capabilities.
- **FR-012**: Conversation records MUST NOT contain: IP address, browser fingerprinting data, raw authentication tokens, cookies, secrets, hidden model reasoning/chain-of-thought, complete HTTP headers, or provider request bodies beyond the safe application-level fields already required.
- **FR-013**: Any grouping identifier introduced to associate related messages MUST be opaque, non-secret, non-personally-identifying, safe to rotate or reset, and MUST NOT be usable to select or influence which organization a request is attributed to.

**Admin-only sources**

- **FR-014**: An authenticated administrator MUST be able to view the knowledge sources that supported one of their own organization's grounded conversations.
- **FR-015**: Source metadata shown to an administrator MUST remain compact and safe — it MUST NOT expose raw embedding vectors, internal storage locations, secrets, or another organization's documents.
- **FR-016**: Public visitors MUST continue to never see source metadata, exactly as already guaranteed by existing chat behavior.

**Conversation browsing**

- **FR-017**: An authenticated administrator MUST be able to list their own organization's conversations, ordered deterministically newest-first.
- **FR-018**: Conversation listing MUST support filtering by outcome, filtering by a date range, and free-text search over the question.
- **FR-019**: Conversation listing MUST be bounded: the server MUST enforce a maximum page size regardless of what a client requests, and MUST NOT allow an unbounded "return everything" request.
- **FR-020**: An administrator whose organization has no matching conversations MUST receive a valid, successful empty result rather than an error.
- **FR-021**: An authenticated administrator MUST be able to view the full detail of a single one of their own organization's conversations, including operational metadata (timing, and where applicable, provider/model and token usage) not shown in the list view.
- **FR-022**: A conversation-detail request for a nonexistent, or another organization's, conversation MUST fail the same way in both cases, revealing nothing about whether the record exists.

**Analytics summary**

- **FR-023**: An authenticated administrator MUST be able to request an analytics summary for their own organization over a date range, including at minimum: total request count, a count and rate per outcome, latency aggregates, and token/provider usage aggregates.
- **FR-024**: If no date range is supplied, a documented default range MUST be applied rather than scanning unbounded history.
- **FR-025**: An organization with no activity in the selected range MUST receive a valid, clearly-zeroed summary rather than an error.
- **FR-026**: Small-talk conversations MUST count toward total request volume in analytics but MUST NOT contribute to token usage or provider/model usage aggregates.

**Knowledge gaps and common questions**

- **FR-027**: An authenticated administrator MUST be able to request a ranked view of recurring insufficient-information questions for their own organization over a date range.
- **FR-028**: Knowledge-gap grouping MUST use only deterministic normalization (such as case and whitespace normalization); it MUST NOT merge questions using speculative semantic similarity.
- **FR-029**: Only insufficient-information conversations MUST contribute to the knowledge-gaps view; conversations with any other outcome MUST be excluded.
- **FR-030**: An authenticated administrator MUST be able to request a ranked view of their own organization's most frequently asked questions (across all outcomes) for a date range, using the same deterministic grouping approach as knowledge gaps.

**Usage and cost visibility**

- **FR-031**: Usage and provider/model metrics exposed to a tenant administrator MUST reflect only that administrator's own organization's usage — never platform-wide or another organization's usage.
- **FR-032**: The system MUST NOT expose invented or estimated monetary cost figures where no reliable, deterministic pricing source exists; token counts and provider/model identification MUST be exposed instead.

**Latency measurement**

- **FR-033**: The latency recorded and reported for a conversation MUST represent the end-to-end application processing time for that chat request, and MUST be clearly distinguished from any lower-level provider-internal timing that may separately be available.

**Tenant isolation**

- **FR-034**: Every conversation and analytics capability in this feature (list, detail, summary, knowledge gaps, common questions, usage/provider metrics) MUST derive organization context exclusively from the authenticated administrator's session, never from client-supplied input.
- **FR-035**: A cross-organization attempt on any capability in this feature MUST fail in a way that does not reveal whether the targeted record exists.
- **FR-036**: Usage/provider metrics exposed through any tenant-scoped admin capability introduced by this feature MUST be attributable to the correct organization with the same rigor as conversation records — an administrator MUST NOT be able to see usage figures that include another organization's activity.

**Auditability**

- **FR-037**: Administrator reads of conversation or analytics data introduced by this feature do NOT require per-row audit logging beyond what existing authentication and tenant-security auditing already provides.
- **FR-038**: Conversation question and answer content MUST NOT be written into application logs solely because it already exists in persisted conversation records.

**Preserving existing behavior**

- **FR-039**: The public chat request and response contract MUST remain unchanged by this feature — no new required field, no analytics opt-in field, and no admin-visible flag.
- **FR-040**: Public source-hiding behavior, small-talk behavior, and every previously existing chat outcome MUST remain unchanged by this feature.

### Key Entities

- **Conversation Record**: A durable record of one public chat request that reached one of the five defined outcomes (grounded, insufficient information, out of scope, unavailable, small talk) — requests rejected earlier (rate limiting, request-size/question-length validation) never produce one. Belongs to exactly one organization. Captures the visitor's question, the outcome, the assistant's public answer, when it happened, and — where applicable — operational metadata (timing, token usage, provider/model attribution, and for an unavailable outcome, a safe failure category distinguishing provider error / budget exceeded / kill switch / concurrency limit) and a stable snapshot of the knowledge sources that supported a grounded answer. Visible in full only to an authenticated administrator of the owning organization; the public visitor never sees another visitor's record or any organization's aggregate data.
- **Source Evidence Snapshot** (part of a Conversation Record, not a separately browsable entity): The specific knowledge evidence that supported a grounded answer at the moment it was produced, preserved independently of later changes to the underlying knowledge document.
- **Analytics Summary** (derived, not separately stored): An aggregate view, computed over an organization's own conversation records for a date range — outcome counts/rates, latency aggregates, and token/provider usage aggregates.
- **Knowledge Gap** (derived, not separately stored): A recurring, deterministically-grouped insufficient-information question for an organization, with its occurrence count and most recent occurrence.
- **Common Question** (derived, not separately stored): A deterministically-grouped, frequently-asked question for an organization across all outcomes, for a date range.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of public chat requests across all outcomes (grounded, insufficient information, out of scope, small talk, unavailable) produce exactly one durable conversation record attributed to the correct organization, verified by automated tests.
- **SC-002**: 0% of cross-organization attempts to list conversations, view conversation detail, view the analytics summary, view knowledge gaps, view common questions, or view usage/provider metrics succeed, verified by automated tests covering every one of those capabilities.
- **SC-003**: An administrator can retrieve a chronological, filterable, searchable view of their own organization's conversations, and every such request is bounded to a server-enforced maximum page size regardless of client input.
- **SC-004**: An administrator can identify their organization's most frequent unanswered questions, grouped deterministically, with zero LLM-based processing involved in producing that grouping.
- **SC-005**: An administrator's analytics summary accurately reflects outcome counts/rates, latency, and token/provider usage for their own organization's data only, verified against seeded fixtures with known expected aggregates.
- **SC-006**: 0% of sampled failure-scenario conversation records contain raw provider exception text, credentials, or provider endpoint detail, verified by automated tests.
- **SC-007**: Public chat behavior (all existing outcomes, small talk, source hiding) is unchanged after this feature, verified by the full pre-existing automated suite passing unmodified in intent.
- **SC-008**: A visitor's chat answer is still delivered successfully even in a seeded scenario where conversation recording itself cannot complete, verified by an automated test.
- **SC-009**: Small-talk conversations are visible in conversation history and counted in request-volume analytics while contributing zero token usage and zero provider/model attribution, verified by automated tests.

## Assumptions

- The public chat request/response contract (`POST /api/v1/chat`) is not modified by this feature; any conversation/session grouping identifier, if introduced at all, is additive, optional for the client to use, and never required to reach a functioning answer.
- For this feature, Albertos remains the only public chat installation; the server resolves the correct organization for every public chat request internally, without any client-supplied identifier.
- Analytics endpoints default to a 30-day lookback window when no date range is supplied, unless a different default is adopted during planning and documented there — the requirement is only that a bounded, documented default exists.
- Conversation records are retained indefinitely for this feature's MVP; no automated retention-cleanup mechanism is introduced. This is a known limitation to be revisited by a future privacy/production-hardening feature, not a compliance claim made by this feature.
- Full subject-erasure (GDPR-style deletion-on-request) tooling is out of scope; this feature only avoids designing conversation storage in a way that would make future deletion structurally difficult.
- Whether existing usage/provider accounting becomes directly tenant-owned, or is instead safely attributed to a tenant through its relationship to a conversation record, is an architecture decision left to planning — this specification only requires that the resulting tenant-scoped usage/provider visibility is never cross-tenant.
- No new administrator role or permission tier is introduced; every administrator retains full read access to their own organization's conversation and analytics data, consistent with the existing single-privilege-tier model.
- This feature's own automated verification does not require real Ollama, GPU resources, Anthropic credentials, or external network access; live end-to-end verification may additionally use the local Docker Compose stack.
- The future React Admin Platform frontend and any dedicated LLM/RAG observability platform remain explicitly out of scope; this feature only establishes the backend data contract those will eventually build on or complement.
