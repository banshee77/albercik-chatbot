# Feature Specification: Knowledge Base UI

**Feature Branch**: `014-knowledge-base-ui`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Feature 014 — Knowledge Base UI: replace the Shiruno Admin Platform's Feature 013 Knowledge placeholder with the first complete customer-facing knowledge-management workflow — health summary, document list, upload, document detail, re-index, replace, and delete — consuming the existing Feature 010 tenant-scoped Knowledge API exactly as it exists today, without redesigning the knowledge backend, without exposing RAG/embedding/chunking internals, and without becoming a second security boundary."

## Clarifications

### Session 2026-08-20

- Q: Should the Replace action be offered on a document that is currently in the "Processing" status, or only on documents that are "Ready" or "Failed"? → A: Replace is available regardless of status (Ready, Processing, or Failed) — including as a recovery path for a document stuck in Processing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator sees whether their knowledge base is ready (Priority: P1)

A customer administrator opens Knowledge from the application shell and immediately understands the state of their organization's knowledge base — how many documents exist, how many are ready, how many failed, and whether the assistant currently has enough knowledge to answer questions — without needing to understand embeddings, chunks, or RAG internals.

**Why this priority**: This is what turns the Feature 013 placeholder into a real product surface. Without it, nothing else in this feature is reachable, and it delivers standalone value for any tenant that already has documents (e.g., provisioned via the existing CLI) even before upload is used.

**Independent Test**: Log in as a tenant administrator with existing knowledge documents, open Knowledge, and confirm the health summary and document list both reflect that tenant's real data from the existing Feature 010 API.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator whose tenant has knowledge documents, **When** they open `/app/knowledge`, **Then** they see a health summary (document counts by status, chunk count, and whether the assistant is ready to answer) and a list of their documents with human-readable status.
2. **Given** a tenant with no knowledge documents yet, **When** the administrator opens Knowledge, **Then** they see a clear, intentional empty state (not a broken-looking empty table) with a prominent way to upload their first document.
3. **Given** the Knowledge page is loading its initial data, **When** the health summary and document list have not yet arrived, **Then** the administrator sees an explicit loading state, not a blank or broken-looking page.
4. **Given** the backend is unreachable or returns an error while loading Knowledge, **When** that failure occurs, **Then** the administrator sees a distinct, safe failure state (never rendered as if the knowledge base were simply empty) with a way to retry.

---

### User Story 2 - Administrator uploads a document and it becomes usable knowledge (Priority: P1)

A customer administrator uploads a new document, watches it move from "processing" to "ready," and trusts that the assistant can now use it — all without leaving the Knowledge page or asking a developer for help.

**Why this priority**: This is the feature's core value-creation flow — the one explicitly named in the brief's User Experience Goal (Login → Knowledge → Upload → ready → assistant can use it). Without it, the page is read-only and the tenant still depends on the CLI to add knowledge.

**Independent Test**: While on the Knowledge page, select and upload a valid document, and confirm the document list and health summary both update to reflect it — without a full browser reload — ending in a "Ready" status.

**Acceptance Scenarios**:

1. **Given** the administrator is on the Knowledge page, **When** they choose the upload action, select a file, and confirm, **Then** the upload button becomes disabled and an explicit "uploading and indexing" state is shown for the duration of the request.
2. **Given** a successful upload, **When** the request completes, **Then** the document list and health summary both refresh to include it, its resulting status is visible, and the administrator sees clear success feedback — with no full-page reload required.
3. **Given** an upload that the backend rejects (e.g., unsupported file type, file too large, unprocessable content), **When** the failure is returned, **Then** the administrator sees one safe, specific, user-facing message — never raw backend exception text, a stack trace, an internal URL, or embedding/provider detail.
4. **Given** an upload already in progress, **When** the administrator attempts to submit another upload for the same action before it completes, **Then** the duplicate submission is prevented.

---

### User Story 3 - Administrator recovers a failed document without developer help (Priority: P1)

A customer administrator sees that a document failed to process, understands why in plain language, and fixes it themselves — either by re-indexing or replacing it — without needing CLI or developer assistance.

**Why this priority**: The brief calls this out as a first-class goal ("recover from failed indexing without developer/CLI assistance"). A knowledge UI that can create failures but not explain or recover from them would leave tenants stuck exactly where today's CLI-only workflow leaves them.

**Independent Test**: With a document in a failed state, open its detail, confirm the sanitized failure reason and available recovery actions are shown, trigger re-index, and confirm the outcome (success or a new safe failure message) is reflected without the previously-working parts of the knowledge base appearing broken.

**Acceptance Scenarios**:

1. **Given** a document with a failed status, **When** the administrator views it (in the list and in its detail), **Then** its status reads "Failed" using text (not color alone), together with a sanitized, safe failure message.
2. **Given** a failed document, **When** the administrator views its available actions, **Then** re-index and/or replace are offered as recovery actions, and the document is never presented as currently usable by the assistant.
3. **Given** the administrator triggers re-index on a failed document, **When** the request is in flight, **Then** duplicate re-index submissions for that document are prevented and an intentional pending state is shown.
4. **Given** a re-index that fails again, **When** the failure is returned, **Then** the administrator sees a safe message and — critically — any other document that was already working continues to be presented as ready, never as broken by an unrelated action.
5. **Given** a re-index that succeeds, **When** the request completes, **Then** the document's status and the health summary both refresh to reflect the recovery.

---

### User Story 4 - Administrator replaces outdated knowledge safely (Priority: P2)

A customer administrator replaces a document that is now outdated with a new version, understanding that the current knowledge keeps serving the assistant until the replacement succeeds, and that the old version is retired automatically only once it does.

**Why this priority**: Important for keeping knowledge current over time, but the tenant can already operate (view, create, and recover knowledge) without it — it refines the ongoing-maintenance experience rather than gating first use.

**Independent Test**: Select an existing ready document, replace it with a new file, confirm the current document keeps being represented as active while the replacement processes, and confirm the new version becomes active (and the old one is retired) only once the replacement succeeds.

**Acceptance Scenarios**:

1. **Given** any document owned by the tenant — regardless of whether its current status is Ready, Processing, or Failed — **When** the administrator chooses Replace, **Then** they are asked to select a new file and give one clear, lightweight confirmation before the request is sent — the UI explains that the new document supersedes the current one only after it succeeds.
2. **Given** a replacement in progress, **When** the request is in flight, **Then** duplicate replace submissions for that document are prevented and a pending state is shown.
3. **Given** a replacement that succeeds, **When** the request completes, **Then** the document list, the document's detail (if open), and the health summary all refresh, and the new version is shown as the active document.
4. **Given** a replacement that fails, **When** the failure is returned, **Then** the administrator sees a safe message, and the original document continues to be represented as active and usable — never as removed or broken by the failed attempt.

---

### User Story 5 - Administrator deletes knowledge that is no longer needed (Priority: P2)

A customer administrator removes a document they no longer want the assistant to use, with a deliberate confirmation step that names the document being deleted.

**Why this priority**: Necessary for full lifecycle ownership, but less frequent and lower-risk-to-defer than creating, viewing, or recovering knowledge.

**Independent Test**: Delete an existing document, confirm the confirmation step names it by its safe display name, confirm it, and verify it disappears from the list and the health summary updates — without a full page reload.

**Acceptance Scenarios**:

1. **Given** the administrator chooses to delete a document, **When** the confirmation step appears, **Then** it identifies the document by its safe, user-facing filename and explains that the assistant will no longer be able to use it.
2. **Given** the delete confirmation is showing, **When** the administrator confirms, **Then** the confirmation control is disabled while the request is in flight, preventing duplicate submissions.
3. **Given** a successful delete, **When** the request completes, **Then** the document no longer appears in the active list, the health summary refreshes, and the administrator sees success feedback — with no full page reload.
4. **Given** a delete that fails, **When** the failure is returned, **Then** the administrator sees a safe, generic message, consistent with the centralized API error handling, and the document's presence in the list reflects the backend's actual current state.

---

### User Story 6 - A session that expires mid-action is handled safely (Priority: P3)

While uploading, replacing, re-indexing, or deleting, an administrator's session becomes invalid (expired or revoked). The Knowledge page notices via the existing centralized handling, clears its state, and returns the administrator to login — never leaving a dialog that implies the action succeeded, and never continuing to display that tenant's knowledge data.

**Why this priority**: This reuses Feature 013's existing centralized session-expiration mechanism rather than introducing new behavior; it is a safety net around the higher-priority stories above, not a new user journey.

**Independent Test**: While a knowledge mutation (upload, replace, re-index, or delete) is in flight, simulate the backend rejecting the request for authentication reasons, and confirm the administrator is returned to login with no stale success dialog and no knowledge data left visible.

**Acceptance Scenarios**:

1. **Given** an administrator on the Knowledge page, **When** any knowledge request (initial load or a mutation) is rejected for authentication reasons, **Then** the frontend clears authenticated state and redirects to login exactly as Feature 013's existing mechanism already does elsewhere in the shell.
2. **Given** a mutation was in flight when the session was invalidated, **When** the redirect happens, **Then** no dialog or status is left implying that mutation succeeded, and no previously loaded document or health data remains visible afterward.

---

### Edge Cases

- What happens when a document has no stored content left to re-index (e.g., it failed before any content was ever persisted)? → Re-index is not treated as a silent success; the administrator sees a safe message directing them to replace the document instead, matching the existing backend behavior.
- What happens when two administrators (or two tabs) both replace the same document at nearly the same time? → Exactly one replacement can win; the backend is authoritative. The losing request's attempt is shown as a safe failure, and the frontend does not assume no one else can act on the same document — it does not implement any client-side locking.
- What happens when a document that is already "processing" receives another re-index request? → The backend rejects it; the frontend surfaces this as a safe message and does not present it as a new failure of the document itself.
- What happens when a re-index attempt on an already-"ready" document fails? → The document keeps its "Ready" status and keeps being presented as usable; the failure is communicated as an issue with the most recent action, not as the document becoming broken.
- What happens if an administrator navigates away from Knowledge while a mutation is still in flight? → The mutation's outcome is not lost: on return to Knowledge, the page reloads current state from the backend rather than trusting any stale in-memory assumption.
- What happens when the tenant's knowledge base is completely empty? → A clear, intentional empty state is shown (never an empty table that looks broken), with a prominent upload action.
- What happens when the backend returns a document lifecycle value the frontend does not explicitly recognize? → It is presented using a safe, generic fallback label rather than the raw internal value, and is never assumed to be either "Ready" or "Failed" by default.
- What happens when an administrator replaces a document that is still "Processing" (e.g., stuck after a crashed or interrupted request)? → Replace is offered regardless of the document's current status; it is a legitimate self-service recovery path for a stuck Processing document, exactly as it is for a Failed one (Clarifications, 2026-08-20).

## Requirements *(mandatory)*

### Functional Requirements

**Knowledge health & overview**

- **FR-001**: The system MUST display, on the Knowledge page, the current tenant's knowledge health: total document count, ready count, processing count, failed count, active chunk count, and whether the knowledge base is ready for the assistant to use — sourced from the existing tenant-scoped knowledge-health data.
- **FR-002**: The system MUST NOT display a raw internal tenant identifier, an embedding vector, or internal provider/model configuration anywhere on the Knowledge page.
- **FR-003**: When the tenant has no knowledge documents, the system MUST show an intentional, clearly-worded empty state with a prominent way to upload a first document — never an empty table presented as if data failed to load.

**Document list**

- **FR-004**: The system MUST display only knowledge documents belonging to the authenticated administrator's own tenant, exactly as returned by the existing tenant-scoped document-list data.
- **FR-005**: The system MUST present each document's status using human-readable text (e.g., "Ready," "Processing," "Failed") rather than raw internal status values, and MUST NOT communicate status using color alone.
- **FR-006**: The system MUST use the ordering already provided by the backend and MUST NOT impose a different client-side ordering.
- **FR-007**: The system MUST NOT present a retired/soft-deleted document as an active document; only documents the backend returns as active are shown.
- **FR-008**: If the backend returns a document lifecycle value the frontend does not explicitly recognize, the system MUST present it using a safe, generic fallback label rather than inventing behavior or defaulting it to "Ready" or "Failed."

**Upload**

- **FR-009**: The system MUST provide an accessible upload action allowing the administrator to select and submit a file to be added to their tenant's knowledge base.
- **FR-010**: Once a file is selected, the system MUST display the selected filename before submission.
- **FR-011**: While an upload request is in flight, the system MUST disable further submission of that same upload action and MUST show an explicit "uploading and indexing" state; it MUST NOT fabricate a numeric progress percentage the backend does not provide.
- **FR-012**: On successful upload, the system MUST refresh the document list and the health summary, present the resulting document's status, and communicate success — without requiring a full browser page reload.
- **FR-013**: On upload failure, the system MUST present one safe, specific, user-facing message reflecting the backend's own sanitized failure reason (e.g., unsupported file type, file too large, unprocessable content), and MUST NOT render raw backend exception text, a stack trace, an internal URL, an embedding/provider detail, or a secret.

**Document detail**

- **FR-014**: The system MUST allow the administrator to inspect a document's detail, showing at minimum: filename, status, content type, relevant lifecycle dates (uploaded/updated/indexed), and — when failed — its sanitized failure message.
- **FR-015**: The system MUST NOT show a document's raw file-system location, raw chunk text, raw embeddings, or the tenant's internal identifier in the document detail view.

**Failure recovery: re-index and replace**

- **FR-016**: For a failed document, the system MUST make its failure state visible and actionable, offering the recovery action(s) the backend permits for that document (re-index and/or replace), and MUST NOT imply the document is currently usable by the assistant.
- **FR-017**: The system MUST provide a re-index action for eligible documents that is described honestly as rebuilding the search index from the document's already-stored content — the system MUST NOT imply that re-index re-reads the original source file or recomputes how the document was split into chunks.
- **FR-018**: While a re-index request for a document is in flight, the system MUST disable duplicate re-index submission for that specific document, while leaving navigation and actions on unrelated documents available.
- **FR-019**: On re-index success, the system MUST refresh the affected document's state and the health summary, and communicate success.
- **FR-020**: On re-index failure, the system MUST show a safe message and MUST NOT represent a document that the backend still reports as "ready" as broken or unusable — a failed re-index attempt on an already-working document must never regress its presented status.
- **FR-021**: The system MUST provide a Replace action for any document owned by the tenant regardless of its current status (Ready, Processing, or Failed) — including as a self-service recovery path for a document stuck in Processing — that lets the administrator select a new file, and MUST require one clear, lightweight confirmation before submitting the replacement.
- **FR-022**: The Replace confirmation MUST communicate that the current document keeps serving the assistant while the replacement is processed, and that it is retired only once the replacement succeeds.
- **FR-023**: While a replace request for a document is in flight, the system MUST disable duplicate replace submission for that document and show an intentional pending state.
- **FR-024**: On replace success, the system MUST refresh the document list, the open document detail (if any), and the health summary, and present the new version as the active document.
- **FR-025**: On replace failure, the system MUST show a safe message and continue presenting the original (pre-replace) document as active and usable — never as removed or broken by the failed attempt.

**Delete**

- **FR-026**: The system MUST provide a Delete action for documents owned by the current tenant, gated by a deliberate confirmation step that identifies the document by its safe, user-facing filename (e.g., `Delete "treningi.pdf"?`) and explains that the assistant will no longer be able to use it.
- **FR-027**: While a delete request is in flight, the system MUST disable the delete confirmation control to prevent duplicate submission.
- **FR-028**: On successful delete, the system MUST remove the document from the active list, refresh the health summary, and communicate success — without requiring a full browser page reload.
- **FR-029**: On delete failure, the system MUST show a safe, generic message consistent with the centralized API error handling, and MUST NOT interpret a "not found" response as proof that another tenant's document exists.

**Tenant boundary & API access**

- **FR-030**: All knowledge-management network requests MUST go through the existing centralized frontend API boundary — no ad-hoc request MUST be issued directly from a page or component.
- **FR-031**: The system MUST NOT send a tenant identifier on any knowledge request as a way to select or authorize which tenant's data is affected, MUST NOT provide any control to choose a different tenant, and MUST NOT construct a knowledge request URL using a tenant slug or ID.

**Session lifecycle**

- **FR-032**: If a knowledge request (initial load or any mutation) is rejected for authentication reasons, the system MUST invalidate the frontend's authenticated state and redirect to login, using the existing centralized session-expiration handling — the same behavior already required for every other protected part of the shell.
- **FR-033**: When a session is invalidated during a mutation, the system MUST NOT leave any dialog or status implying that mutation succeeded, and MUST NOT continue to display previously loaded knowledge data after the redirect.

**Loading & error states**

- **FR-034**: The system MUST show an explicit loading state during the Knowledge page's initial data load, distinct from both the empty-knowledge-base state and the loaded-with-data state.
- **FR-035**: The system MUST present an initial page/backend load failure as a distinct state from an empty knowledge base, and MUST offer a way to retry the load.
- **FR-036**: The system MUST show an explicit loading state for an individual in-flight mutation without causing the entire page to flash or re-render as if nothing is currently loaded.

**Accessibility & responsiveness**

- **FR-037**: Every knowledge-management action (upload, view detail, re-index, replace, delete, and their confirmations) MUST be operable using the keyboard alone.
- **FR-038**: Any confirmation dialog used by this feature MUST manage focus appropriately for its mechanism and MUST be understandable to screen-reader users, including for the delete confirmation's destructive intent.
- **FR-039**: The Knowledge page MUST remain usable on narrower desktop/laptop-class viewport widths, adapting a wide document list through an appropriate technique (e.g., horizontal scrolling, responsive layout, or selective column reduction) while keeping every action reachable.

**Non-regression**

- **FR-040**: This feature MUST NOT change the semantics, behavior, or contract of the existing public chat endpoint, RAG retrieval, answerability, small-talk, public source hiding, observability, or Conversation Record behavior.
- **FR-041**: This feature MUST NOT change the existing Feature 010 Knowledge API's contract; any backend change is only acceptable if it is additive, tenant-safe, and required by a genuine gap that cannot be solved in the frontend alone.

### Key Entities

- **Knowledge Health Summary**: The tenant's current knowledge-base standing as shown to the administrator — total/ready/processing/failed document counts, active chunk count, and whether the assistant is ready to answer from this knowledge. Read-only, always sourced from the existing tenant-scoped health data, never client-computed.
- **Knowledge Document (as presented)**: One tenant-owned document as the administrator sees it — safe filename, human-readable status, content type, relevant lifecycle dates, and (when failed) a sanitized failure message. Never includes raw file-system paths, chunk text, embeddings, or the tenant's internal identifier.
- **Document Action**: One of the lifecycle actions available for a given document depending on its current state and what the backend permits — Upload (creates a new document), Re-index (rebuild the search index from stored content), Replace (supersede with a new file), Delete (retire permanently). Every action is subject to the tenant boundary and centralized API/auth handling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can go from opening Knowledge to seeing a newly-uploaded document reach "Ready" status without leaving the page or reloading the browser, verified by an automated test.
- **SC-002**: 100% of documents and health figures shown on the Knowledge page come from the authenticated administrator's own tenant-scoped data — never a client-supplied, cached-elsewhere, or cross-tenant value — verified by automated tests.
- **SC-003**: 0% of backend failures surfaced on the Knowledge page include raw exception text, a stack trace, an internal URL, an embedding/provider detail, or a secret, verified by automated tests covering upload, replace, re-index, and delete failure paths.
- **SC-004**: 100% of failed documents present at least one recovery action (re-index and/or replace, as permitted) and are never presented as currently usable by the assistant, verified by an automated test.
- **SC-005**: A failed re-index or replace attempt on a document the backend still reports as "ready" never causes that document's presented status to regress, verified by an automated test.
- **SC-006**: After a successful upload, replace, or delete, 100% of the document list and health summary updates are visible without a full browser page reload, verified by automated tests.
- **SC-007**: Every interactive element in the upload, replace, re-index, and delete flows — including confirmations — is operable using the keyboard alone, verified by automated tests.
- **SC-008**: A session invalidated mid-mutation (upload, replace, re-index, or delete) always results in the administrator being returned to login with no stale success indication and no previously-visible knowledge data remaining on screen, verified by an automated test.
- **SC-009**: The production frontend build, type check, and lint all complete successfully with zero errors, verified by an automated build gate.
- **SC-010**: The full pre-existing backend automated test suite (Feature 010 knowledge, Feature 011 conversations/analytics, Feature 012 observability, tenant isolation, public chat contract) continues to pass unmodified in intent.

## Assumptions

- The existing Feature 010 backend currently accepts plain-text (`.txt`) document uploads up to its own configured maximum size; this specification does not add new frontend-side file-type or size rules beyond giving early, non-authoritative feedback for obviously invalid selections — the backend's own validation remains authoritative, consistent with the brief's explicit instruction not to invent duplicate validation rules.
- "Re-index" is offered only where the existing backend's document lifecycle already permits it (a currently-processing document cannot be re-indexed again until it finishes); "Replace" has no such backend-imposed status restriction and is available regardless of a document's current status, per Clarifications (2026-08-20). This specification does not change which states the backend itself permits for either action — it only decides, where the backend allows more than one answer, what the frontend exposes.
- The document detail view's presentation mechanism (inline panel, drawer, modal, or a nested route) is left to the planning phase to decide based on what best fits the existing Feature 013 shell, consistent with this project's precedent of deferring pure implementation-shape decisions to `/speckit-plan`.
- No new backend endpoint or database entity is required for this feature; it consumes the existing Feature 010 API as-is. Any backend change surfaced during planning is expected to be additive and narrowly scoped (e.g., exposing a currently-missing but genuinely UI-blocking field), not a redesign of document lifecycle.
- Conversations UI (Feature 015) and Analytics Dashboard (Feature 016) remain out of scope; the Conversations and Analytics placeholders introduced by Feature 013 are unchanged by this feature.
- The following are explicitly out of scope for this feature and are not addressed by its requirements: a raw document content/chunk viewer, direct chunk or knowledge-text editing, manual embedding/chunking controls (chunk size, overlap, embedding model/provider, similarity threshold, retrieval top-K), bulk upload or bulk delete, multi-select actions, folder-based ingestion, drag-and-drop as a required interaction, a platform-level or cross-tenant knowledge view, a tenant switcher, and any new client-side data-fetching/state-management library adopted merely for this feature's own convenience. Each remains a possible future, separately-justified addition.
