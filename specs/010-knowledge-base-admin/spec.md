# Feature Specification: Knowledge Base Administration

**Feature Branch**: `010-knowledge-base-admin`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Feature 010 — Knowledge Base Administration. Build the first real customer-facing administration capability on top of the Feature 009 tenant foundation: let a tenant administrator safely list, upload, replace, delete, and re-index the knowledge used by their Shiruno assistant, and query whether their knowledge base is healthy and ready for chat — all strictly tenant-isolated, backend-first (no React admin UI yet)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator sees the current state of their knowledge base (Priority: P1)

An administrator opens their knowledge management view and sees every document their organization has uploaded — its name, its processing status (still processing, ready, or failed), when it was added or last changed, and a safe explanation if something went wrong — along with an at-a-glance summary of whether their assistant currently has any usable knowledge at all.

**Why this priority**: Nothing else in this feature is trustworthy without this — an administrator who can't see what their knowledge base actually contains can't safely upload, replace, delete, or recover anything. This is the foundation every other story depends on.

**Independent Test**: As an authenticated administrator, request the document list and the health summary; confirm both reflect only documents belonging to your own organization, with accurate status and no missing/incorrect states, including the case of having zero documents.

**Acceptance Scenarios**:

1. **Given** an administrator's organization has documents in different processing states, **When** they request their document list, **Then** each document shows its filename, processing status, created/updated timestamps, and — for failed documents — a safe, non-technical explanation of what went wrong.
2. **Given** an administrator's organization has no documents at all, **When** they request their document list, **Then** they receive a valid empty list, not an error.
3. **Given** an administrator's organization has a mix of ready, processing, and failed documents, **When** they request the knowledge-base health summary, **Then** it accurately reports counts by status, a total count of currently usable knowledge, whether the assistant currently has any retrieval-ready knowledge, and when knowledge was last successfully indexed.
4. **Given** an administrator's organization has zero ready documents, **When** they request the health summary, **Then** it clearly indicates the assistant is not yet ready to answer from their knowledge, without erroring.

---

### User Story 2 - Administrator uploads new knowledge and it becomes usable (Priority: P1)

An administrator uploads a new document. The system validates it, processes it, and — once processing succeeds — the assistant can immediately draw on it to answer questions. If processing fails, the administrator sees a safe, understandable explanation and the assistant is never left claiming to know something it doesn't.

**Why this priority**: Uploading new knowledge is the core value of a knowledge base — without it, there is nothing to manage, replace, or serve to the assistant.

**Independent Test**: Upload a valid document as an authenticated administrator; confirm it reaches a ready state and that a question about its content produces a grounded answer citing it. Separately, upload content designed to fail processing and confirm it reaches a failed state with a safe explanation and never becomes usable.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator, **When** they upload a valid, supported document, **Then** it is stored under their own organization, processed, and reaches a ready state usable by the assistant.
2. **Given** an authenticated administrator, **When** their upload fails existing validation (unsupported type, oversized, invalid content), **Then** it is rejected exactly as it already is today, with nothing stored.
3. **Given** an authenticated administrator, **When** their upload passes validation but fails during processing (e.g., an internal indexing failure), **Then** the document reaches a failed state, is never usable by the assistant, and the administrator sees a safe, actionable explanation rather than raw technical detail.
4. **Given** any upload attempt, **When** the request includes an organization identifier in its body, query string, or headers, **Then** that value has no effect — the document is always owned by the uploader's own authenticated organization.

---

### User Story 3 - Administrator safely replaces outdated knowledge (Priority: P1)

An administrator has a document that's gone stale — for example, last year's class schedule — and uploads its replacement. The assistant keeps answering correctly from the old schedule the entire time the new one is being processed. Only once the new content is fully validated and ready does it take over; if anything goes wrong during that process, the old schedule keeps working, uninterrupted.

**Why this priority**: This is the feature's signature capability and its main safety guarantee: an administrator must never be able to accidentally take their assistant's knowledge offline by trying to update it. Given the same priority weight as upload because a knowledge base that can only grow, never be safely corrected, is not genuinely manageable.

**Independent Test**: Replace an existing ready document with new valid content; confirm the assistant answers from the old content until the new content is ready, then from the new content afterward, and that the old content is no longer used. Separately, replace a document with content that fails processing and confirm the original document and its answers are completely unaffected.

**Acceptance Scenarios**:

1. **Given** an administrator's ready document, **When** they upload valid replacement content for it, **Then** the replacement is validated and processed the same way a new upload would be.
2. **Given** a replacement that is still being processed, **When** the assistant is asked a question the original document would have answered, **Then** it still answers from the original document.
3. **Given** a replacement that finishes processing successfully, **When** the assistant is next asked a relevant question, **Then** it answers from the new content, and the old content no longer participates in answers.
4. **Given** a replacement that fails processing, **When** the assistant is asked a question the original document would have answered, **Then** it still answers correctly from the original, unaffected document.
5. **Given** an administrator, **When** they attempt to replace a document belonging to a different organization, **Then** the attempt fails the same way as trying to replace a document that doesn't exist.

---

### User Story 4 - Administrator removes knowledge they no longer want (Priority: P2)

An administrator deletes a document that's no longer relevant. It immediately stops being used to answer questions.

**Why this priority**: Important for keeping a knowledge base accurate and relevant, but less urgent than the ability to see, add, and safely update knowledge — a stale document that's merely still present is a smaller problem than one an administrator can't safely replace.

**Independent Test**: Delete an existing document as its owning administrator and confirm it no longer appears in the list or contributes to answers. Separately, confirm an administrator cannot delete another organization's document.

**Acceptance Scenarios**:

1. **Given** an administrator's own document, **When** they delete it, **Then** it no longer appears in their document list and no longer contributes to any answer.
2. **Given** an administrator, **When** they attempt to delete a document belonging to a different organization, **Then** the attempt fails the same way as deleting a document that doesn't exist, revealing nothing about the other organization's document.
3. **Given** an administrator, **When** they attempt to delete a document that is already deleted or never existed, **Then** the attempt fails safely and consistently.

---

### User Story 5 - Administrator recovers or refreshes existing knowledge (Priority: P2)

A document failed to process, or an administrator simply wants to regenerate a document's retrieval data using current settings without re-uploading it. They request re-indexing, and the system regenerates that document's usable knowledge from its real stored content — never fabricating success.

**Why this priority**: Valuable operational recovery and maintenance capability, but secondary to the primary upload/replace/delete/visibility workflows most administrators will use most often.

**Independent Test**: Request re-indexing of an administrator's own document and confirm the resulting knowledge is regenerated and usable. Separately, confirm an administrator cannot re-index another organization's document, and that re-indexing never changes which organization owns the document or lets the requester influence provider/model/chunking settings.

**Acceptance Scenarios**:

1. **Given** an administrator's own existing document, **When** they request re-indexing, **Then** the system regenerates its retrieval data from real stored content and it remains (or becomes) usable by the assistant.
2. **Given** a re-index request, **When** it is processed, **Then** the document's owning organization is unchanged and the request cannot influence which embedding provider, model, or chunking settings are used.
3. **Given** an administrator, **When** they attempt to re-index a document belonging to a different organization, **Then** the attempt fails the same way as re-indexing a document that doesn't exist.

---

### User Story 6 - No administrator can ever reach another organization's knowledge (Priority: P1)

Regardless of which knowledge operation is attempted — viewing, uploading, replacing, deleting, re-indexing, or checking health — an administrator from one organization can never see, affect, or even detect the existence of another organization's knowledge, even when they know or guess a document's identifier.

**Why this priority**: This is the non-negotiable security guarantee the entire feature exists inside of. Every other story's value depends on this holding without exception.

**Independent Test**: With two organizations each holding their own documents, confirm systematically that every knowledge operation performed by one organization's administrator against the other organization's data is blocked, and that the failure response does not reveal whether the targeted document exists.

**Acceptance Scenarios**:

1. **Given** two organizations each with their own documents, **When** one organization's administrator lists, views, replaces, deletes, re-indexes, or checks health, **Then** only their own organization's data is ever visible or affected.
2. **Given** an administrator, **When** their request includes an organization identifier in the body, query string, or headers, **Then** that value is disregarded entirely in favor of their authenticated organization.
3. **Given** a cross-organization attempt on any knowledge operation, **When** it is rejected, **Then** the response is indistinguishable from the response for a nonexistent document.

---

### User Story 7 - Everything that already worked keeps working (Priority: P1)

Every visitor chatting with Albertos, and every previously existing administrator capability, continues to behave exactly as before — this feature only adds new administrator capability on top of the existing foundation.

**Why this priority**: This is a feature built directly on top of a live, working system. Regressing public chat behavior or previously-shipped admin behavior would be a failure regardless of how well the new capabilities work.

**Independent Test**: Run the full existing automated suite (public chat outcomes, small talk, rate limiting, budget, Feature 009 tenant-isolation tests) unmodified in intent and confirm every test still passes; separately confirm the public Albertos site and assistant behave identically to before this feature.

**Acceptance Scenarios**:

1. **Given** the public assistant, **When** a visitor asks a question that previously produced any existing outcome (grounded, insufficient information, out of scope, unavailable, small talk), **Then** the same question produces the same outcome as before this feature.
2. **Given** the public chat widget, **When** a grounded answer is shown, **Then** source-hiding behavior and assistant identity/avatar presentation remain exactly as before this feature.
3. **Given** the existing Feature 009 tenant-isolation, rate-limit, budget, and provider tests, **When** the full automated suite runs, **Then** all of them still pass, unmodified in intent.

---

### Edge Cases

- What happens if an administrator tries to replace or re-index a document that has already been deleted? → The attempt fails the same safe way as operating on a nonexistent document.
- What happens if an administrator requests re-indexing of a document that is currently still processing? → The request is not accepted while processing is already underway, to avoid two conflicting regenerations racing each other; the administrator is told the document is currently processing.
- What happens if a replacement is requested for a document that is itself a not-yet-ready replacement? → Only a document that is currently the tenant's active, ready knowledge (or a failed document being recovered) may be replaced or re-indexed; the exact eligibility rule is a planning-phase detail, but the outcome must never allow two competing "new" versions to both become active.
- What happens to the knowledge-base health summary while a document is mid-upload, mid-replacement, or mid-re-index? → It reflects the current true state at query time, including a "processing" count; a document does not count as ready until processing genuinely completes.
- What happens if an administrator uploads a replacement whose content is functionally identical to the current document? → Treated like any other replacement — validated, processed, and only takes over once ready; no special-casing for "no meaningful change."
- What happens to a document's failure explanation once it is successfully replaced or re-indexed? → It no longer applies once the document reaches ready state; a stale failure explanation must not be shown once the document is genuinely ready.

## Requirements *(mandatory)*

### Functional Requirements

**Tenant-scoped visibility**

- **FR-001**: System MUST return, for an authenticated administrator, only knowledge documents owned by their own organization.
- **FR-002**: Any organization identifier supplied by the client (request body, query string, or header) MUST have no effect on which organization's documents are visible or affected by any knowledge operation.
- **FR-003**: The document list MUST expose, per document, at minimum: a stable identifier, filename/display name, content type, processing status, creation and last-updated timestamps, and — when processing failed — a safe failure summary.
- **FR-004**: The document list and any per-document view MUST NOT expose filesystem paths, internal storage locations, raw embedding vectors, credentials, provider internals, or unsanitized technical error detail.
- **FR-005**: Document listing order MUST be deterministic and newest-first, consistent with the existing listing behavior.
- **FR-006**: An administrator whose organization has zero documents MUST receive a valid, successful empty list rather than an error.

**Upload**

- **FR-007**: An authenticated administrator MUST be able to upload a new knowledge document, subject to the same validation, size, and content-safety controls already in effect.
- **FR-008**: An uploaded document MUST be owned by the uploading administrator's own authenticated organization; no client-supplied value may determine ownership.
- **FR-009**: A successfully processed upload MUST reach a ready state and become usable by the assistant; a failed upload MUST reach a failed state and MUST NOT become usable by the assistant.

**Document lifecycle**

- **FR-010**: Every knowledge document MUST expose one of at least three lifecycle states to the administrator: processing, ready, or failed.
- **FR-011**: A document MUST NOT be reported as ready unless its processing has genuinely and successfully completed.
- **FR-012**: A document that fails processing MUST NOT leave any content that participates in the assistant's answers.
- **FR-013**: When processing fails, the administrator-visible explanation MUST be safe (no stack traces, raw provider responses, credentials, or internal hostnames) while remaining operationally useful (e.g., indicating what went wrong and that retrying or replacing is the next step).

**Replace**

- **FR-014**: An authenticated administrator MUST be able to replace one of their own existing documents with new content.
- **FR-015**: Replacement content MUST undergo the same validation and processing as a new upload before it can become the organization's active knowledge for that document.
- **FR-016**: The previously active knowledge MUST remain active and usable by the assistant for the entire duration that a replacement is being processed.
- **FR-017**: If replacement processing fails, the previously active knowledge MUST remain completely active and unaffected — the assistant MUST NOT lose knowledge solely because a replacement attempt failed.
- **FR-018**: Once a replacement successfully reaches a ready state, the previously active knowledge for that document MUST be retired from the assistant's answers, and the new content MUST become the active source.
- **FR-019**: An administrator MUST NOT be able to replace a document belonging to a different organization.

**Delete**

- **FR-020**: An authenticated administrator MUST be able to delete one of their own organization's documents.
- **FR-021**: A deleted document's knowledge MUST NOT participate in the assistant's answers after deletion.
- **FR-022**: An administrator MUST NOT be able to delete a document belonging to a different organization; such an attempt MUST fail the same way as deleting a document that does not exist.

**Re-index**

- **FR-023**: An authenticated administrator MUST be able to request re-indexing of one of their own existing documents.
- **FR-024**: Re-indexing MUST regenerate embeddings for the document's already-persisted chunk text using the currently configured embedding provider; it does NOT recompute chunk boundaries, since the full original source text is not retained separately from its already-chunked pieces — changing chunk boundaries requires replacing the document (re-upload) instead. The requester MUST NOT be able to supply or override the embedding provider, embedding model, chunk size, overlap, or similarity settings.
- **FR-025**: Re-indexing MUST NOT change which organization owns the document.
- **FR-026**: An administrator MUST NOT be able to re-index a document belonging to a different organization; such an attempt MUST fail the same way as re-indexing a document that does not exist.
- **FR-027**: Re-indexing MUST be based on the document's genuine, durably stored source content; the system MUST NOT report a re-index as successful without actually regenerating retrieval data from real source content.

**Knowledge-base health**

- **FR-028**: System MUST provide an authenticated, organization-scoped summary of knowledge-base health, including at minimum: document counts by status, a total count of currently active retrievable knowledge units, whether the organization currently has any retrieval-ready knowledge, and when knowledge was last successfully indexed.
- **FR-029**: The health summary MUST reflect only the authenticated administrator's own organization — never another organization's data or platform-wide totals.
- **FR-030**: An organization with no ready documents MUST receive a valid health summary that clearly indicates the assistant is not yet ready to answer from their knowledge, not an error.

**Cross-tenant isolation**

- **FR-031**: Every knowledge-management operation (list, view, upload, replace, delete, re-index, health) MUST derive organization context exclusively from the authenticated administrator's session, never from client-supplied input.
- **FR-032**: A cross-organization attempt on any knowledge-management operation MUST fail in a way that does not reveal whether the targeted document exists.

**Authentication / authorization**

- **FR-033**: Every knowledge-management operation MUST require valid, active administrator authentication; missing, malformed, expired, or invalid authentication MUST be rejected using the same generic failure behavior already used elsewhere.
- **FR-034**: An administrator belonging to a deactivated organization MUST be denied access to every knowledge-management operation, consistent with existing tenant-status enforcement.

**Auditability**

- **FR-035**: Document upload, replacement, deletion, and re-index actions MUST produce a structured audit record identifying the organization and administrator responsible.
- **FR-036**: Audit records for knowledge-management actions MUST NOT include document content, credentials, or authentication tokens.

**Preserving existing behavior**

- **FR-037**: The public assistant's request/response contract and all of its existing outcome types MUST remain unchanged by this feature.
- **FR-038**: Retrieval configuration (similarity threshold, result limits, embedding defaults, answer-generation behavior) MUST remain unchanged by this feature, except that re-indexing intentionally applies the currently configured rules to a specific document's content.
- **FR-039**: Public-facing source citation and source-hiding behavior MUST remain unchanged by this feature.

### Key Entities

- **Knowledge Document**: A single unit of tenant-owned knowledge. Belongs to exactly one organization. Exposes an identifier, filename/display name, content type, lifecycle status (processing, ready, or failed), a safe failure summary when applicable, and creation/update timestamps. Underlies the assistant's answers only while in a ready, non-deleted, non-retired state.
- **Document Chunk** (existing concept, unchanged): The retrievable unit derived from a knowledge document's content. Only chunks belonging to a currently active, ready document participate in the assistant's retrieval.
- **Knowledge Base** (conceptual only — not a newly introduced stored entity): The aggregate of an organization's active knowledge documents and their chunks, summarized through the health view. Not modeled as a separate persisted entity for this feature.
- **Replacement**: The relationship between a document being retired and the successor document that takes over its role once ready. Exact representation is a planning-phase decision; the business rule is that a replacement never leaves the organization with a gap where neither the old nor new knowledge is usable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of document list, detail, and health requests return only the requesting administrator's own organization's data, verified by automated cross-tenant tests.
- **SC-002**: 100% of cross-organization replace, delete, and re-index attempts are blocked and behave identically to operating on a nonexistent document.
- **SC-003**: 100% of successful uploads, replacements, and re-index operations reach a ready state that is genuinely usable by the assistant on the very next relevant question.
- **SC-004**: 0% of failed processing attempts (upload, replace, or re-index) leave content usable by the assistant.
- **SC-005**: 100% of replacement attempts — whether they succeed or fail — leave the organization with at least one working version of the knowledge whenever a working version existed beforehand; there is never a window where neither version is usable.
- **SC-006**: An administrator with no knowledge yet receives a clear "not ready" state from both the document list and the health summary, with zero errors, on the first request.
- **SC-007**: 100% of the pre-existing automated suite (public chat outcomes, small talk, rate limiting, budget, provider behavior, and Feature 009 tenant-isolation tests) continues to pass, unmodified in intent, after this feature.
- **SC-008**: 100% of administrator-visible failure messages, sampled across test scenarios, contain no stack traces, raw provider responses, credentials, or internal hostnames.

## Assumptions

- Replacement is treated as producing a distinct successor document that becomes active only once ready, with the predecessor retired at that point — not an in-place mutation of the original document — because processing takes real time and the original must keep serving the assistant throughout that window. The exact data representation of this relationship is a planning-phase decision.
- Whether re-indexing regenerates a document's knowledge from previously retained extracted source content, or effectively requires the administrator to supply the content again, is a planning-phase architecture decision explicitly deferred by the feature request; this specification only requires that re-indexing never fabricates success without genuinely regenerating retrieval data from real, durable source content.
- A per-document detail view is assumed useful and tenant-scoped like every other operation, but its exact necessity and shape (beyond what the list already provides) is a planning-phase decision.
- No new administrator role or permission tier is introduced; every administrator retains full management rights over their own organization's knowledge, consistent with the existing single-privilege-tier model.
- The existing CLI is not extended for knowledge management as part of this feature unless planning identifies a concrete, necessary operational or testing gap; the authenticated HTTP API is the primary interface, since the future admin frontend — not shell access — is how customers will eventually manage knowledge.
- No object storage or cloud-specific storage service is introduced; knowledge remains stored within the existing database-centric architecture.
- Only Albertos holds real production knowledge during this feature; cross-organization isolation is proven using a second, test-only organization, consistent with how Feature 009 proved isolation.
- This feature's own automated verification does not require real Ollama, GPU resources, Anthropic credentials, or external network access; live end-to-end verification may additionally use the local Docker Compose stack.
- The future React Admin Platform frontend, Conversations & Analytics, and any dedicated observability platform remain explicitly out of scope; this feature only establishes the backend knowledge-management capability those will eventually build on or complement.
