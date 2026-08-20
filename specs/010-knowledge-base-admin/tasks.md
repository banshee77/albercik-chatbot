---

description: "Task list for Feature 010 — Knowledge Base Administration"
---

# Tasks: Knowledge Base Administration

**Input**: Design documents from `/specs/010-knowledge-base-admin/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included — the spec's Testing Requirements section explicitly mandates automated tests for every isolation/safety/concurrency property, and constitution Principle XI makes this NON-NEGOTIABLE.

**Organization**: Tasks are grouped by user story from spec.md. Story *labels* keep the spec's declared priority (P1: US1, US2, US3, US6, US7; P2: US4, US5), but **phase order** follows real buildable dependency — US6 (cross-tenant proof) needs the detail/replace/reindex endpoints US1/US3/US5 create, so it is phased after them despite being P1, exactly mirroring Feature 009's US4 precedent. See Dependencies & Execution Order below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US7, per spec.md
- File paths are exact and relative to the repository root.

## Path Conventions

Single existing backend project — `src/shiruno/`, `tests/`, `alembic/versions/` at repository root (plan.md's Structure Decision; no new project is created).

---

## Phase 1: Setup

No setup tasks are required. This feature extends the existing `shiruno`
backend project in place — no new dependency, tool, or project
scaffolding is introduced (plan.md Technical Context: zero new
dependencies).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, retrieval-safety, response-shape, and shared-logic
changes every later phase depends on.

**⚠️ CRITICAL**: No user story task may start until this phase is
complete. In particular, T004's retrieval filter is what makes every
later story's "failed/in-flight knowledge never leaks into retrieval"
claim actually true, and T007's shared ingestion helper is what both
upload (US2) and replace (US3) build on.

- [X] T001 [P] Add `updated_at` (`NOT NULL`, `server_default=func.now()`, `onupdate=func.now()`), `indexed_at` (nullable), `safe_error_message` (nullable `Text`), and `replaces_document_id` (nullable, FK → `knowledge_documents.id`) to `KnowledgeDocument` in `src/shiruno/persistence/models.py` (data-model.md)
- [X] T002 Create Alembic migration `add_knowledge_document_lifecycle_metadata` in `alembic/versions/` — add `updated_at` nullable → backfill `= uploaded_at` for every row → assert none remain NULL → set `NOT NULL`; add `indexed_at` nullable → backfill `= uploaded_at` for rows where `status = 'ready'` (left `NULL` otherwise); add `safe_error_message` nullable (no backfill); full reversible `downgrade()` dropping all three columns (data-model.md "Migration plan" §1; depends on T001)
- [X] T003 Create Alembic migration `add_knowledge_document_replaces_document_id` in `alembic/versions/` (revises T002's migration) — add nullable self-referential FK `replaces_document_id` (no backfill — `NULL` is correct for every pre-existing row); full reversible `downgrade()` (data-model.md "Migration plan" §2; depends on T002)
- [X] T004 [P] Add `KnowledgeDocument.status == DocumentStatus.ready` to the `WHERE` clause of `search_similar_chunks` in `src/shiruno/persistence/repositories.py`, alongside the existing `deleted_at.is_(None)` filter (research.md §1, data-model.md "Retrieval query"; depends on T001)
- [X] T005 [P] Add `content_type`, `updated_at`, `indexed_at`, `error_message` fields to `DocumentSummary` in `src/shiruno/api/schemas.py` (contracts/documents-api-delta.md "DocumentSummary"; depends on T001)
- [X] T006 [P] Add `"document_replace"` and `"document_reindex"` to the `AuditAction` literal in `src/shiruno/infra/audit.py`
- [X] T007 Extract the chunk/embed/persist/status-transition logic currently inline in `upload_document()` into a new shared helper in `src/shiruno/application/_ingest_content.py`; refactor `src/shiruno/application/upload_document.py` to call it, preserving upload's exact existing behavior. On failure, set `safe_error_message` to one of a small, fixed set of generic, developer-authored strings (e.g., `"Embedding generation failed. Retry indexing or replace the document."`) — **never** derived from, or containing any part of, the raw exception's message, type, or `str(exc)`; this is what makes sanitization a structural guarantee rather than a hope (research.md §10; depends on T001)
- [X] T008 Update `documents.py`'s `_to_summary` helper in `src/shiruno/api/routers/documents.py` to populate the new `DocumentSummary` fields — `content_type` constant `"text/plain"` (research.md §6), `updated_at`, `indexed_at`, `error_message` from `safe_error_message` (depends on T005, T007)

**Checkpoint**: Schema, retrieval safety, response shape, and shared
ingestion logic are all in place. `uv run pytest tests/contract
tests/unit tests/integration -q` should still collect and run (green on
everything not yet touched by a later phase — the new columns are all
nullable-or-server-defaulted, so no existing `KnowledgeDocument(...)`
construction in the test suite needs to change). User story work can now
begin.

---

## Phase 3: User Story 1 - Administrator sees the current state of their knowledge base (Priority: P1) 🎯 MVP

**Goal**: List, single-document detail, and a tenant-scoped health
summary — the foundation every other story depends on being trustworthy.

**Independent Test**: quickstart.md §3–§4 — request the document list,
a document's detail, and the health summary as an authenticated
administrator; confirm accurate status/timestamps/error info and a valid
empty state when the tenant has no documents.

### Tests for User Story 1

- [X] T009 [US1] Extend `tests/contract/test_documents_lifecycle.py`: list items include correct `content_type`/`updated_at`/`indexed_at`/`error_message`; an administrator with zero documents receives a valid empty list, not an error
- [X] T010 [P] [US1] Create `tests/contract/test_documents_detail.py`: `GET /documents/{id}` returns an administrator's own document; returns `404` for a nonexistent, foreign-tenant, or soft-deleted/retired document id — all three cases identical
- [X] T011 [P] [US1] Create `tests/contract/test_documents_health.py`: health summary correctly reports `documents.{total,ready,processing,failed}`, `chunks` (only chunks of currently `ready` documents), `ready_for_chat`, and `last_indexed_at` across a mix of document states; an administrator with zero documents receives `200` with all-zero counts and `ready_for_chat: false`, not an error (FR-030)

### Implementation for User Story 1

- [X] T012 [US1] Add `KnowledgeHealthResponse` (with a nested document-counts model) to `src/shiruno/api/schemas.py` (contracts/documents-api-delta.md "GET /documents/health")
- [X] T013 [P] [US1] Create `src/shiruno/application/get_document.py`: tenant-scoped single-document fetch, raising the existing `NotFoundAppError` for missing/foreign-tenant/deleted documents
- [X] T014 [P] [US1] Create `src/shiruno/application/knowledge_health.py`: tenant-scoped document counts by status, active chunk count (chunks belonging to the tenant's currently `ready`, non-deleted documents), `ready_for_chat = ready > 0`, `last_indexed_at = MAX(indexed_at)` over the tenant's `ready` documents (depends on T004)
- [X] T015 [US1] Add `GET /documents/health` to `src/shiruno/api/routers/documents.py` — **must be registered before** `GET /documents/{document_id}` (research.md §2 routing note; depends on T012, T014)
- [X] T016 [US1] Add `GET /documents/{document_id}` to `src/shiruno/api/routers/documents.py`, registered after `/health` (depends on T013, T015)

**Checkpoint**: `uv run pytest tests/contract/test_documents_lifecycle.py tests/contract/test_documents_detail.py tests/contract/test_documents_health.py -q` passes independently.

---

## Phase 4: User Story 2 - Administrator uploads new knowledge and it becomes usable (Priority: P1)

**Goal**: Confirm the existing, tenant-scoped upload path (refactored in
Foundational to share ingestion logic with replace) still behaves
correctly and now exposes the new lifecycle fields — and that a failed
upload genuinely never becomes retrievable, now enforced structurally by
T004's filter rather than merely by convention.

**Independent Test**: quickstart.md §4 — upload valid content and confirm
it becomes usable by the assistant; upload content that fails processing
and confirm it never does.

### Tests for User Story 2

- [X] T017 [US2] Extend `tests/contract/test_documents_upload.py`: a successful upload's response includes correct `content_type`/`updated_at`/`indexed_at`/`error_message: null`
- [X] T018 [US2] Add an opt-in `.error` attribute to `tests/fakes/fake_embedding_provider.py` (mirroring `FakeLLMProvider`'s existing pattern) that `embed_query`/`embed_passages` raise when set. Extend `tests/contract/test_documents_upload.py`: configure the fake provider's `.error` to an exception carrying deterministic, deliberately unsafe content — e.g. `Exception("Traceback (most recent call last): ... ConnectionError to http://embedding-internal.example:9999 using key sk-test-do-not-leak-12345")` — and assert the failed upload's `error_message` is exactly the fixed generic string from T007 (never containing `"Traceback"`, `"embedding-internal.example"`, or `"sk-test-do-not-leak-12345"` anywhere in the HTTP response body), remains non-null and operationally useful, reaches `status: "failed"`, has zero chunks that satisfy the retrieval filter, and that a chat question about its content produces `insufficient_information`, never `grounded`

**Checkpoint**: `uv run pytest tests/contract/test_documents_upload.py -q` passes independently — no new implementation beyond Foundational's T007/T008 was needed for this story.

---

## Phase 5: User Story 3 - Administrator safely replaces outdated knowledge (Priority: P1)

**Goal**: Replace creates a new successor document and retires the
predecessor only once the successor is genuinely ready; a failed
replacement never affects the predecessor; and — the corrected,
non-negotiable part — two concurrent replace requests for the same
document can never both succeed, enforced by a PostgreSQL row lock, not
merely documented as a limitation.

**Independent Test**: quickstart.md §5–§6 — replace a document with valid
content and confirm the assistant answers from the new content while the
old content is retired; replace with content that fails and confirm the
original is completely unaffected; run two concurrent replace requests
against the same document and confirm exactly one wins.

### Tests for User Story 3

- [X] T019 [US3] Create `tests/contract/test_documents_replace.py`: a successful replace produces a new document id, retires the predecessor (excluded from list/detail thereafter), and a relevant chat question answers from the new content; a failed replace (fake embedding provider raises) leaves the predecessor completely unaffected — still `ready`, still answering; replacing a nonexistent, foreign-tenant, or already-deleted/retired document returns `404`
- [X] T020 [P] [US3] Create `tests/integration/test_replace_concurrency.py`: drive two concurrent replace requests for the same predecessor explicitly (e.g., pause one request after its embedding step but before its row-lock step, using a second thread/session to issue and complete the competing replace first) and assert exactly one succeeds (`status: "ready"`, predecessor retired) while the other reaches `status: "failed"` with the specific race-loss message and never becomes retrievable (research.md §3)

### Implementation for User Story 3

- [X] T021 [US3] Create `src/shiruno/application/replace_document.py`: look up the predecessor tenant-scoped (raise `NotFoundAppError` if missing/foreign-tenant/deleted/ineligible), create the successor row (`status = processing`, `replaces_document_id = predecessor.id`), call `_ingest_content` for validation/chunking/embedding (depends on T007)
- [X] T022 [US3] Implement the row-locked activate/retire step in `replace_document.py`: `SELECT ... FOR UPDATE` on the predecessor, re-check `deleted_at IS NULL` under the lock; if eligible, set `predecessor.deleted_at = now` and `successor.status = ready` / `indexed_at = now`; if the lock reveals the predecessor was already retired by a concurrent winner, set `successor.status = failed` with the specific safe race-loss message (research.md §3; data-model.md "Concurrency invariant"; depends on T021)
- [X] T023 [US3] Add `POST /documents/{document_id}/replace` to `src/shiruno/api/routers/documents.py` with `document_replace` audit logging (depends on T022, T006)

**Checkpoint**: `uv run pytest tests/contract/test_documents_replace.py tests/integration/test_replace_concurrency.py -q` passes independently. This is the point at which the feature's core, non-negotiable safety guarantee (never lose working knowledge, never race into two active successors) is proven end-to-end.

---

## Phase 6: User Story 5 - Administrator recovers or refreshes existing knowledge (Priority: P2)

**Goal**: Re-index regenerates embeddings for a document's already-stored
chunk text using the current embedding provider — a genuine operation,
not a fabricated one — and never regresses a document that was already
working.

**Independent Test**: quickstart.md §7 — re-index an existing document
and confirm its embeddings are regenerated and it remains usable; confirm
re-indexing a foreign-tenant document is blocked and that the endpoint
accepts no client-supplied provider/model/chunking overrides.

### Tests for User Story 5

- [X] T024 [US5] Create `tests/contract/test_documents_reindex.py`: a successful re-index keeps the same document id, reaches `status: "ready"` with a later `indexed_at` and regenerated chunk embeddings (verified via a fake embedding provider producing distinguishable output) and `error_message: null`; using T018's fake-provider `.error` attribute with the same deterministic unsafe content (`"Traceback"`, a fake internal URL, a fake API key), a failed re-index on an already-`ready` document leaves `status` and existing chunk embeddings completely unchanged but sets `error_message` to the fixed generic string from T025 — explicitly asserting none of the injected forbidden substrings appear anywhere in the HTTP response — while remaining non-null and operationally useful; a failed re-index on an already-`failed` document leaves it `failed` with an updated, equally sanitized `error_message`; the endpoint accepts no body or query parameter that could influence embedding provider, model, chunk size, overlap, or similarity settings; re-indexing a nonexistent, foreign-tenant, or deleted document returns `404`

### Implementation for User Story 5

- [X] T025 [US5] Create `src/shiruno/application/reindex_document.py`: tenant-scoped lookup, fetch the document's existing chunks, call `embedding_provider.embed_passages(...)` on their stored `content`; on success, update each chunk's `embedding` and set `status = ready` / `indexed_at = now` / `safe_error_message = None`; on failure, leave `status` and every chunk's `embedding` completely unchanged, only update `safe_error_message` — using the same small, fixed set of generic strings as T007, never the raw exception's text (research.md §4; depends on T004, T007)
- [X] T026 [US5] Add `POST /documents/{document_id}/reindex` to `src/shiruno/api/routers/documents.py` with `document_reindex` audit logging (depends on T025, T006)

**Checkpoint**: `uv run pytest tests/contract/test_documents_reindex.py -q` passes independently.

---

## Phase 7: User Story 6 - No administrator can ever reach another organization's knowledge (Priority: P1)

**Goal**: Explicit, dedicated proof that every one of the four new
operations (detail, health, replace, reindex) is cross-tenant isolated,
on top of the already-isolated list/upload/delete from Feature 009.

**Independent Test**: quickstart.md §9 — with two tenants, confirm every
new operation performed by one tenant's administrator against the other
tenant's data is blocked, and that no client-supplied tenant identifier
has any effect.

- [X] T027 [US6] Extend `tests/contract/test_documents_auth.py`: Tenant A cannot view Tenant B's document detail, replace it, or re-index it — all `404`, identical to a nonexistent document; Tenant A's health summary never reflects Tenant B's data; a client-supplied tenant identifier (body/query/header) has no effect on detail, health, replace, or re-index (depends on T016, T023, T026)

**Checkpoint**: `uv run pytest tests/contract/test_documents_auth.py -q` passes independently, extending Feature 009's cross-tenant proof to every new operation.

---

## Phase 8: User Story 4 - Administrator removes knowledge they no longer want (Priority: P2)

**Goal**: Re-verify the existing, already-tenant-scoped delete continues
to work correctly now that the schema and retrieval filter have changed.

**Independent Test**: quickstart.md §8 — delete a document and confirm it
no longer appears anywhere or contributes to answers.

- [X] T028 [US4] Extend `tests/contract/test_documents_lifecycle.py`: a deleted document is excluded from the list, returns `404` from detail, is excluded from health counts, and no longer contributes to chat answers (depends on T008, T004, T016, T015)

**Checkpoint**: `uv run pytest tests/contract/test_documents_lifecycle.py -q` passes independently — no new implementation was needed; delete's existing behavior composes correctly with the new columns and filter.

---

## Phase 9: User Story 7 - Everything that already worked keeps working (Priority: P1)

**Goal**: Confirm the entire pre-existing behavior surface (public chat,
small talk, rate limiting, budget, Feature 009 tenant isolation) is
unaffected.

**Independent Test**: quickstart.md §10 — run the pre-existing contract
suites unmodified in intent.

- [X] T029 [US7] Run `uv run pytest tests/contract tests/unit tests/integration -q` and confirm 100% pass with original assertion intent preserved (FR-037–FR-039; depends on T010–T028)

**Checkpoint**: Full pre-existing behavior surface verified unchanged.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T030 [P] Add `tests/integration/test_knowledge_document_migration.py`: run both new Alembic migrations' `upgrade`/`downgrade` against a dedicated throwaway database (mirroring `specs/009-admin-platform-foundation`'s `test_tenant_migration.py` pattern), asserting `updated_at`/`indexed_at` backfill correctness for pre-existing rows and full reversibility (depends on T002, T003)
- [X] T033 [P] Extend `tests/contract/test_admin_authorization_fail_closed.py`'s existing parametrized route list (Feature 009) to include `GET /api/v1/documents/health`, `GET /api/v1/documents/{document_id}`, `POST /api/v1/documents/{document_id}/replace`, and `POST /api/v1/documents/{document_id}/reindex`; prove missing, malformed, and expired authentication all fail closed with the exact same generic `401` status and body already used by every other tenant-scoped admin route, and — reusing whatever existing Feature 009 deactivated-tenant fixture/test pattern that file or `test_documents_auth.py` already establishes — that an administrator belonging to a deactivated tenant is denied on all four new routes too (FR-033, FR-034; mandatory security-boundary coverage; depends on T015, T016, T023, T026)
- [X] T034 [P] Extend `tests/contract/test_audit_logging.py`: a successful replace produces a `document_replace` audit log entry, and a successful re-index produces a `document_reindex` entry; both include the correct action name and the authenticated `tenant_id` and administrator identity metadata (matching the existing `document_upload`/`document_delete` assertion pattern from Feature 009); neither log line contains the uploaded/replacement document's content, an authentication token, or a password (FR-035, FR-036; depends on T023, T026)
- [X] T031 Walk through `quickstart.md` end to end manually against the local `docker compose` stack (`shiruno` project) and confirm every documented expected outcome
- [X] T032 Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src tests`, and confirm all clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies (Setup is a no-op) — BLOCKS every later phase.
- **US1 (Phase 3)**: depends only on Foundational.
- **US2 (Phase 4)**: depends only on Foundational (re-verifies T007/T008).
- **US3 (Phase 5)**: depends only on Foundational (`_ingest_content` from T007).
- **US5 (Phase 6)**: depends only on Foundational.
- **US6 (Phase 7)**: depends on US1 (T016, detail+health), US3 (T023, replace), and US5 (T026, reindex) — phased after them despite being P1, since it tests operations they create, exactly mirroring Feature 009's US4 (fail-closed) precedent.
- **US4 (Phase 8)**: depends on Foundational and, for its assertions, on US1's detail/health routes (T015, T016) already existing.
- **US7 (Phase 9)**: depends on every prior phase (runs the whole suite).
- **Polish (Phase 10)**: depends on all prior phases. T033 additionally depends on T015/T016 (US1) and T023/T026 (US3/US5) existing, since it extends coverage to those routes; T034 additionally depends on T023/T026.

### Parallel Opportunities

- T001 has no dependencies and must go first; T004, T005, T006 can then start together once T001 lands. T002/T003/T007/T008 are sequential where noted.
- Within US1's implementation, T013 and T014 are independent files — run together, then T015/T016 integrate them in order (routing-order constraint).
- T019 and T020 (US3's contract test vs. concurrency integration test) are independent files — run together.
- T030, T033, and T034 in Polish are independent files — run together once their respective dependencies land; T031/T032 run last.

---

## Parallel Example: Foundational Phase

```bash
# After T001 lands, launch the independent Foundational tasks together:
Task: "Add status == ready filter to search_similar_chunks (T004)"
Task: "Add new DocumentSummary fields (T005)"
Task: "Add document_replace/document_reindex to AuditAction (T006)"
```

---

## Implementation Strategy

### MVP First (Foundational + US1 + US2 + US3 + US6 + T033)

This feature's core, non-negotiable promise is "an administrator can see
and safely evolve their knowledge base without ever risking it" — that
requires visibility (US1), confirmation that ordinary ingestion still
works (US2), *safe* replacement including its now-corrected concurrency
guarantee (US3), proof that none of this ever crosses a tenant boundary
(US6), and proof that none of it is reachable without valid authentication
either (T033). Treat these phases as the MVP:

1. Complete Phase 2: Foundational.
2. Complete Phase 3: User Story 1 — validate independently.
3. Complete Phase 4: User Story 2 — validate independently.
4. Complete Phase 5: User Story 3 — validate independently, including the concurrency test.
5. Complete Phase 7: User Story 6 — validate independently.
6. Complete T033 (Polish) — extending the fail-closed auth proof to all four new routes is mandatory security-boundary coverage, not optional polish, even though it's filed in Phase 10 for file-organization reasons.
7. **STOP and VALIDATE**: run `test_documents_lifecycle.py`, `test_documents_detail.py`, `test_documents_health.py`, `test_documents_upload.py`, `test_documents_replace.py`, `test_replace_concurrency.py`, `test_documents_auth.py`, and `test_admin_authorization_fail_closed.py` together — this is the point at which the feature's core safety and isolation guarantees are proven end-to-end.
8. Add US5 (re-index) and US4 (delete re-verification) — both strengthen the MVP but are not required for its core guarantee to hold.
9. Complete T034 (audit verification), Phase 9 (US7), and the rest of Phase 10 (Polish) last.

### Incremental Delivery

Foundational → US1 → US2 → US3 → US6 → T033 (checkpoint: core guarantee
proven) → US5 → US4 → T034 → US7 → rest of Polish.
