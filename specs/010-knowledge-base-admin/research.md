# Phase 0 Research: Knowledge Base Administration

Every decision below resolves an item the spec explicitly left to planning
(replacement data representation, re-index source-of-truth, exact API
paths) or a gap discovered while reading the current implementation
(`src/shiruno/`) that the spec's safety requirements depend on. No
`NEEDS CLARIFICATION` markers remain in `plan.md`'s Technical Context.

## 1. A structural gap in the current retrieval query

**Finding**: `persistence/repositories.py::search_similar_chunks` currently
filters only `KnowledgeDocument.deleted_at.is_(None)` — it does **not**
filter on `status`. In today's single-path (`upload_document.py`) code,
chunks are only ever added to the session inside the same try/except/
finally block that decides `status`, so in practice a chunk has never
existed for anything but a `ready` document. But that is a *convention*
enforced by ingestion-code discipline, not a guarantee enforced by the
query itself — exactly the kind of implicit invariant Feature 010's own
requirements (FR-011, FR-012, FR-016, FR-017; Testing Requirement #8) ask
to be made real and tested, not assumed.

**Decision**: Add an explicit `KnowledgeDocument.status ==
DocumentStatus.ready` filter to `search_similar_chunks`, alongside the
existing `deleted_at IS NULL` filter.

**Rationale**: Makes "only ready, active knowledge is ever retrieved" a
structural guarantee of the query — matching this codebase's existing
preference for structural guarantees over conventions (e.g.,
`infra/audit.py`'s parameter list, `ProviderName`'s explicit-not-inferred
values). It is required for Feature 010's replace/re-index safety
properties to be provably true rather than incidentally true, and it is
fully backward-compatible: every existing test that seeds chunks for
retrieval already sets `status=DocumentStatus.ready` explicitly (verified
across `tests/contract/test_chat*.py`), so this change alters no existing
test's expected outcome.

**Alternatives considered**: Leaving the query as-is and relying on
ingestion code to never commit a non-ready document's chunks — rejected;
this is precisely the kind of assumption a security-sensitive feature
(constitution Principle III/XI) should not rest on when a one-line,
zero-behavior-change-for-existing-data fix is available.

## 2. API surface: extend `/api/v1/documents`, not a new `/admin/knowledge` namespace

**Decision**: Add four new operations to the existing `documents` router
and resource:

```text
GET    /api/v1/documents/health              (NEW — registered before {document_id})
GET    /api/v1/documents/{document_id}       (NEW)
POST   /api/v1/documents/{document_id}/replace   (NEW)
POST   /api/v1/documents/{document_id}/reindex   (NEW)
```

`POST /api/v1/documents`, `GET /api/v1/documents`, and
`DELETE /api/v1/documents/{document_id}` are unchanged in path, method,
and contract.

**Rationale**: The spec's own item 11 states a "strong preference for
consistency with the already shipped document endpoints" and explicitly
says "prefer backward-compatible extension over duplicate parallel APIs
... do not create two competing document-management APIs." The existing
endpoints already live at `/api/v1/documents` (not under `/api/v1/admin`,
per Feature 009's own research §4 decision not to relocate them
speculatively). Introducing a second `/api/v1/admin/knowledge/documents`
tree pointing at the same underlying resource would be exactly the
"competing API" the spec warns against. The example paths in the spec's
scope section are explicitly marked as illustrative ("exact paths should
be decided during planning").

**Routing note**: `GET /documents/health` MUST be registered *before*
`GET /documents/{document_id}` in the router. FastAPI/Starlette matches
routes in registration order; `{document_id}` is typed `uuid.UUID`, so a
request for `/documents/health` would otherwise match that pattern first,
fail UUID coercion, and return `422` instead of falling through to the
health route.

**Alternatives considered**: The spec's own suggested
`/api/v1/admin/knowledge/documents/...` tree — rejected per the spec's own
explicit backward-compatibility preference, above.

## 3. Replace: new successor document, retire predecessor only on success — race-safe via row-level locking

**Decision**: `POST /documents/{document_id}/replace` creates a **new**
`KnowledgeDocument` row up front (`tenant_id` = predecessor's tenant,
`replaces_document_id` pointing back at the predecessor, `status =
processing`) and runs the same validation/chunking/embedding path as a
new upload — **without holding any lock on the predecessor** during that
potentially slow work. Only once embedding succeeds does the operation
acquire a row-level lock on the *predecessor* and, under that lock,
authoritatively decide whether this request is allowed to activate its
successor and retire the predecessor:

```python
# after embedding has already succeeded and the successor's chunks are
# staged (added to the session, not yet committed) — this is the ONLY
# part of replace that holds a lock, and it holds it only until this
# same request's transaction commits at the end of the request.
predecessor = session.execute(
    select(KnowledgeDocument)
    .where(KnowledgeDocument.id == predecessor_id)
    .with_for_update()
).scalar_one()

if predecessor.deleted_at is not None:
    # Lost the race: another request already retired this predecessor
    # (its own successor won). This request's successor must NOT become
    # active retrieval knowledge.
    new_document.status = DocumentStatus.failed
    new_document.safe_error_message = (
        "This document was already replaced by another request."
    )
else:
    predecessor.deleted_at = now
    new_document.status = DocumentStatus.ready
    new_document.indexed_at = now
```

`PostgreSQL`'s `SELECT ... FOR UPDATE` (exposed by SQLAlchemy as
`Select.with_for_update()`) blocks a second concurrent request's lock
acquisition until the first request's transaction commits or rolls back.
Since each HTTP request already runs inside exactly one transaction
(`persistence/database.py::get_session`, unchanged), no new transaction
boundary or session-management change is needed — the lock is simply
acquired partway through the request's existing transaction, held only
from that point until the request's own commit, and never spans an
embedding-provider call.

**Required outcome, and why this design delivers it**: of two concurrent
replace requests for the same predecessor, exactly one observes
`deleted_at IS NULL` under the lock and wins (retires the predecessor,
activates its successor as `ready`); the other, once unblocked, observes
`deleted_at IS NOT NULL` and loses — its successor is marked `failed`
with a safe, specific explanation, its chunks exist in storage but are
never retrievable (the `status == ready` filter from §1 excludes them),
and the predecessor is untouched by the loser. This holds regardless of
which request's *embedding* work happened to finish first — only the
lock-protected final check determines the winner, so there is no window
in which two successors are simultaneously active for one predecessor.

**Rationale**: This is the first of the two "new row + retire old" options
the spec itself lists as preferred, requires no schema beyond the one
nullable self-referential foreign key already planned, and uses only a
mechanism PostgreSQL/SQLAlchemy already provide — no new infrastructure,
queue, or distributed lock (constitution Principle XIII). Deferring the
lock acquisition until *after* embedding succeeds keeps the slow,
provider-bound work outside the locked section, so the row lock's
duration is bounded to fast, local database work — never blocked on an
external embedding call.

**Alternatives considered**: In-place mutation of the existing document
row — rejected; the predecessor must keep serving retrieval for the
entire duration of validating and embedding the replacement, which is
incompatible with mutating the same row that's still being read from. A
full document-versioning platform (version numbers, history table) —
rejected per the spec's explicit "do not build a generalized
document-versioning platform unless necessary." An advisory/application-level
lock (`pg_advisory_lock`) instead of a row lock — rejected as strictly
more complex than locking the row that is already the natural unit of
contention, with no additional benefit. A distributed lock (Redis,
`SELECT ... FOR UPDATE SKIP LOCKED` queue, etc.) — rejected; explicitly
out of scope and unnecessary when a single-database row lock already
gives correct, serialized semantics for this single-database application.
Optimistic concurrency (a version/`xmin` check without locking, retrying
on conflict) — rejected as more complex than pessimistic locking for no
benefit here: replace is a low-frequency administrator action, not a
high-throughput hot path, so blocking briefly under contention is
strictly simpler than implementing retry logic.

**Testing requirement this decision adds**: an automated test must prove
that two concurrent replace requests for the same predecessor cannot both
end up with an active successor (data-model.md's row-locking invariant).
Because `pytest-asyncio`'s default execution is single-threaded, this
test drives the race explicitly — two application-layer replace calls
against the same underlying database, interleaved around the lock point
(e.g., one call paused with its lock held in a background thread while
the second is issued from the main test thread and asserted to block
then lose) — rather than relying on incidental HTTP concurrency, so it
proves the *lock* itself, not merely that two sequential calls behave
correctly.

## 4. Re-index: regenerate embeddings for already-stored chunk text, honestly

**Finding**: `KnowledgeDocument` does not persist the original uploaded
bytes or the full extracted text — only `DocumentChunk.content` (the
already-chunked text) is durably stored. This means a *true* re-chunk
(recomputing chunk boundaries from scratch, e.g., after a
`CHUNK_SIZE_CHARS`/`CHUNK_OVERLAP_CHARS` configuration change) is not
possible without either persisting more source data or asking the
administrator to re-upload — exactly the fork in the road the spec's item
6 (options A/B/C) anticipated and explicitly deferred to planning.

**Decision**: Re-index regenerates **embeddings only**, for the document's
existing, already-persisted chunk boundaries, using the currently
configured embedding provider and model. It does **not** recompute chunk
boundaries. If an administrator needs a genuine re-chunk (e.g., after a
chunk-size setting change), the supported path is **replace** (re-upload),
which does have real full-text content to chunk from.

**Rationale**: This is option B/C from the spec's own menu, resolved in
the direction that requires zero new data retention (respecting item 16's
"do not silently add indefinite binary-file retention" and "remain
provider/cloud neutral") while still being **genuinely useful** —
recovering from a corrupted/incomplete embedding run, or refreshing
embeddings after an embedding *model* change, both regenerate real
retrieval data from real stored content, satisfying FR-027's "must not
fabricate success" requirement honestly. A pure "re-index requires
re-upload" design (option B taken further) would make the re-index
endpoint a no-op wrapper around replace, adding no real capability; this
design gives re-index genuine, distinct operational value.

**Failure behavior — re-index must never regress a working document**:
unlike replace, re-index failure does **not** transition a currently-ready
document to `failed`. If the document was already `ready`, a failed
re-index attempt leaves `status` and existing chunk embeddings completely
unchanged (the old embeddings keep serving retrieval) and only updates
`safe_error_message` to describe the latest failed attempt. If the
document was already `failed` (the recovery case) and re-index fails
again, it simply remains `failed` with an updated error message — no
regression either way, because a failed document was not retrievable
before the attempt and still is not after. This generalizes the spec's
"safe replace" principle to re-index even though the spec did not spell
it out explicitly for re-index, because SC-004/SC-005 and the
Architecture Principle section state the safety goal generally, and
"never make a document less retrievable than it already was" is the
simplest rule consistent with that goal.

**Alternatives considered**: Persisting full extracted text on
`KnowledgeDocument` now, to support true re-chunking — rejected; the spec
explicitly frames this as decision "A" and warns against silently adding
retention without documenting it; there is no current requirement forcing
it, and it can be added later behind the same `reindex_document` function
signature without an API change if a future feature needs it. Requiring
re-upload for *all* recovery (no distinct re-index capability at all) —
rejected as providing no value beyond replace.

## 5. Document detail endpoint

**Decision**: `GET /documents/{document_id}` returns the same
`DocumentSummary` shape as list items — no separate, richer "detail"
schema. A soft-deleted or retired-via-replace document returns `404`
(`NotFoundAppError`), identical to the existing delete/replace/reindex
not-found behavior.

**Rationale**: The spec's own preferred API list includes this path; its
Assumptions section explicitly leaves the exact shape to planning. Reusing
`DocumentSummary` avoids a second schema with no current field that
needs it (Simplicity).

## 6. `content_type` is derived, not persisted

**Finding**: The system currently only accepts `.txt` uploads
(`upload_document.py`'s `_ALLOWED_EXTENSION = ".txt"`); there is no MIME
type stored anywhere today.

**Decision**: `DocumentSummary.content_type` is a constant
(`"text/plain"`) computed at the API response layer, not a new database
column.

**Rationale**: A column with exactly one possible value today is
speculative (constitution Principle XVII's spirit / spec item 17's "avoid
speculative fields"). If a future feature adds support for additional
file types, a real column can be introduced then, at the point it carries
actual information.

## 7. `uploaded_at` already satisfies "created_at" — no breaking rename

**Decision**: Keep the existing `DocumentSummary.uploaded_at` field name
unchanged (it already is the creation timestamp the spec's item 1 calls
`created_at`); add a new `updated_at` field alongside it rather than
renaming.

**Rationale**: `uploaded_at` is part of the already-shipped, tested public
admin contract (`tests/contract/test_documents_lifecycle.py` and others
assert on it by name). Renaming it would be a gratuitous breaking change
for a field that already means exactly what the spec asks for; the spec's
"created_at" is business-language example text, not a literal field-name
mandate.

## 8. New `KnowledgeDocument` columns

**Decision**: Four new columns, all nullable except where noted:

- `updated_at: DateTime(timezone=True)` — `NOT NULL`, `server_default=now()`, `onupdate=now()`.
- `indexed_at: DateTime(timezone=True) | None` — set whenever a document
  (re)reaches `ready` via upload, replace, or successful re-index.
- `safe_error_message: Text | None` — set on any failed processing
  attempt (upload, replace, or re-index); cleared (`NULL`) once the
  document successfully reaches `ready` with no prior failure to report.
- `replaces_document_id: Uuid | None`, FK to `knowledge_documents.id` —
  set only on a document created via replace; `NULL` for ordinary
  uploads.

No new table, no new enum values (`DocumentStatus` already has
`processing`/`ready`/`failed`, matching the spec's minimum-three-states
requirement exactly — item 3 explicitly says preserve existing values
absent a strong reason to rename, and there is none here).

## 9. CLI: no new commands

**Decision**: No knowledge-management CLI commands are added.

**Rationale**: The spec's item 18 explicitly says not to build a
duplicate CLI when the authenticated HTTP API is sufficient, and it is —
every operation is fully exercisable and testable via `httpx` in the
automated suite and via `curl` against the live stack for quickstart
verification. The existing `create-tenant`/`create-admin` commands are
unrelated to knowledge management and are untouched.

## 10. Shared ingestion logic

**Decision**: Extract the chunk/embed/persist/status-transition logic
currently inline in `upload_document.py` into a shared helper,
`application/_ingest_content.py`, called by both `upload_document()` and
the new `replace_document()`. `reindex_document()` calls the embedding
step directly (it operates on already-chunked text, not raw bytes, so it
does not go through the full ingestion helper — see §4).

**Rationale**: Avoids duplicating the existing try/except/finally
status-transition logic (already carefully reasoned about — see
`upload_document.py`'s own comments on why chunk-adding happens inside
the try block) across two call sites, which would risk the two paths
silently drifting apart on exactly the safety-critical behavior Feature
010 is about. This is a refactor of existing logic into a shared function,
not a new abstraction layer (constitution Principle XII/XIII).

## 10a. `safe_error_message` is always a fixed, generic string — never derived from the raw exception

**Decision**: Every place that sets `safe_error_message` (`_ingest_content`
on upload/replace failure, `reindex_document` on re-index failure, and
replace's row-locked race-loss branch) uses one of a small, fixed set of
short, developer-authored strings — e.g., `"Embedding generation failed.
Retry indexing or replace the document."` or `"This document was already
replaced by another request."` — chosen by category, never by
interpolating `str(exc)`, the exception's `args`, or any other
exception-derived text into the stored/returned message.

**Rationale**: FR-013 requires the administrator-visible failure summary
to be "safe... while remaining operationally useful," and SC-008 requires
this to hold across sampled scenarios. Deriving a message from the raw
exception (even after attempting to strip "obviously bad" substrings) is
inherently a denylist — it can miss a provider's next error format
change. A fixed set of generic strings makes the guarantee structural,
matching this codebase's established preference (`infra/audit.py`'s
parameter list, `ProviderName`'s explicit values) for guarantees a test
can prove by construction rather than by sampling. The raw exception is
still logged server-side only, via the existing `logger.exception(...)`
call already present in the ingestion path — never client-visible.

**Testing implication**: a test can inject an exception carrying
deliberately unsafe, deterministic content (a fake stack-trace fragment,
a fake internal URL, a fake API key) and assert the returned
`error_message` is exactly the fixed string and contains none of the
injected content — a much stronger proof than merely asserting the
message is "non-empty."

## 11. Audit logging

**Decision**: `infra/audit.py`'s `AuditAction` literal gains two new
values: `"document_replace"`, `"document_reindex"`. Both log sites pass
`tenant_id` and `administrator_id` exactly like the existing
`document_upload`/`document_delete` sites; `document_replace` additionally
logs the predecessor's id (as `document_id`, since audit's existing
parameter list has no per-action extension point, and the predecessor is
the document being acted upon from the API caller's point of view).

**Rationale**: Directly satisfies FR-035 using the existing
structurally-safe logger (no parameter exists that could carry document
content or secrets — see `infra/audit.py`'s own docstring guarantee).

## 12. Migration sequencing

**Decision**: Two Alembic migrations:

1. `add_knowledge_document_lifecycle_metadata` — adds `updated_at`
   (backfilled to each row's existing `uploaded_at`, then `NOT NULL`),
   `indexed_at` (backfilled to `uploaded_at` for existing `ready` rows,
   left `NULL` for any non-ready row), `safe_error_message` (`NULL` for
   all existing rows — no known failure to report).
2. `add_knowledge_document_replaces_document_id` — adds the nullable
   self-referential FK (`NULL` for all existing rows — none were created
   via replace).

**Rationale**: Two focused migrations, matching this project's established
pattern (Feature 009's two-migration split; the original schema's
`provider_metrics`/`provider_name` split). `updated_at`'s backfill rule
(`= uploaded_at`) is the only defensible deterministic choice — true
"last modified" time for pre-existing rows was never tracked, and
`uploaded_at` is the best available proxy. `indexed_at`'s backfill rule
mirrors it for the same reason, scoped to rows that are actually `ready`
(a `processing`/`failed` row realistically should not exist in production
data today, but the backfill logic handles it correctly regardless).
