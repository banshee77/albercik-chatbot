# Phase 1 Data Model: Knowledge Base Administration

Extends `src/shiruno/persistence/models.py`'s existing `KnowledgeDocument`
in place (research.md §8) — no new table. Types/conventions match the
existing model exactly.

## KnowledgeDocument (changed)

| Column | Type | Constraints | Change |
|---|---|---|---|
| `id` | `Uuid` | PK | unchanged |
| `original_filename` | `Text` | `NOT NULL` | unchanged |
| `uploaded_by_admin_id` | `Uuid` | FK → `administrators.id` | unchanged |
| `tenant_id` | `Uuid` | `NOT NULL`, FK → `tenants.id` | unchanged (Feature 009) |
| `uploaded_at` | `DateTime(timezone=True)` | `server_default=func.now()` | unchanged — remains the API's `uploaded_at`/"created_at" field |
| `status` | `Enum(DocumentStatus)` | `NOT NULL` | unchanged values (`processing`/`ready`/`failed`) |
| `deleted_at` | `DateTime(timezone=True)` | nullable | unchanged — also used to retire a replaced document |
| `updated_at` | `DateTime(timezone=True)` | `NOT NULL`, `server_default=func.now()`, `onupdate=func.now()` | **new** |
| `indexed_at` | `DateTime(timezone=True)` | nullable | **new** — set when the document (re)reaches `ready` |
| `safe_error_message` | `Text` | nullable | **new** — sanitized failure summary (FR-013) |
| `replaces_document_id` | `Uuid` | nullable, FK → `knowledge_documents.id` | **new** — set only on a document created via replace |

```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
)
indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
replaces_document_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid, ForeignKey("knowledge_documents.id"), nullable=True
)
```

**Lifecycle rules**:

- `status` transitions: `processing → ready` (success) or `processing →
  failed` (failure), exactly as today. Re-index may additionally leave
  `status` **unchanged** on failure (research.md §4) — this is the one
  case where a terminal-looking state does not change as a result of a
  processing attempt.
- `indexed_at` is set (to the completion time) whenever `status` becomes
  `ready` via upload, replace, or successful re-index. It is left as-is
  (not cleared) on a failed re-index of an already-`ready` document,
  since that document's existing embeddings — and therefore its last
  genuine indexing — are unchanged.
- `safe_error_message` is set on any failed processing attempt (upload,
  replace, re-index) and is set to `NULL` when a document reaches `ready`
  with no failure to report for that attempt. Its value is always one of
  a small, fixed set of generic, developer-authored strings — never
  derived from or containing the raw exception's text (research.md
  §10a) — so sanitization is a structural guarantee, not a
  best-effort filter.
- `replaces_document_id` is set exactly once, at creation, only for
  documents created via the replace operation. It is never updated
  afterward.
- `deleted_at` is set either by an explicit delete (User Story 4,
  unchanged from Feature 009) or, as of this feature, by a successful
  replace retiring its predecessor. Both cases are indistinguishable by
  this column alone — the audit log and `replaces_document_id` (on the
  *successor*, pointing back) are what distinguish "deleted" from
  "replaced" for anyone reconstructing history.

## DocumentChunk (unchanged)

No schema change. Existing columns (`id`, `document_id`, `position`,
`content`, `embedding`, `created_at`) are sufficient: `content` is the
durable source re-index regenerates embeddings from (research.md §4).

## Retrieval query (changed, not a schema change)

`persistence/repositories.py::search_similar_chunks` gains an additional
`WHERE` condition:

```python
.where(
    KnowledgeDocument.deleted_at.is_(None),
    KnowledgeDocument.status == DocumentStatus.ready,
)
```

This is the structural enforcement point for FR-011/FR-012/FR-016/FR-017
(research.md §1) — every safety property about failed/in-flight
knowledge not participating in retrieval reduces to this one filter being
correct.

## Relationships (target state)

```text
Tenant (1) ──< KnowledgeDocument (many)          [unchanged, Feature 009]
KnowledgeDocument (1) ──< DocumentChunk (many)   [unchanged]
KnowledgeDocument (predecessor) ──0..1── KnowledgeDocument (successor)
    via successor.replaces_document_id            [new, this feature]
```

The predecessor↔successor relationship is one-directional (backward
pointer only, research.md §3) — there is no `superseded_by_document_id`
on the predecessor. A caller who wants "what replaced document X" queries
`WHERE replaces_document_id = X`.

**Concurrency invariant (data integrity, not merely a hardening step)**:
`predecessor.deleted_at IS NULL` is the single authoritative signal for
"this predecessor is still eligible to be replaced." The replace
operation MUST re-read this column under a `SELECT ... FOR UPDATE` row
lock on the predecessor immediately before deciding to retire it and
activate a successor (research.md §3) — never decide from a value read
earlier, before the lock was acquired. This guarantees that of any number
of concurrent replace requests targeting the same predecessor, at most
one observes `deleted_at IS NULL` under the lock and may retire it; every
other concurrent request observes `deleted_at IS NOT NULL` once
unblocked and MUST mark its own successor `failed` rather than activate
it. This is a correctness property of the schema's use, not an optional
safeguard — a caller that skips the lock (e.g., a future code path that
reads `deleted_at` without `with_for_update()`) reintroduces the race.

## Cross-cutting rules

- `replaces_document_id`, when set, MUST reference a document belonging
  to the **same tenant** as the successor — enforced at the application
  layer (the predecessor is always looked up tenant-scoped before a
  replace is allowed to proceed), not by a database constraint, matching
  how `tenant_id` ownership itself is enforced application-side elsewhere
  in this codebase.
- No `tenant_id` semantics from Feature 009 are altered; `replace` and
  `reindex` never change a document's `tenant_id`.

## Migration plan (Alembic)

Two migrations (research.md §12 has the full rationale), both additive
and reversible:

1. **`add_knowledge_document_lifecycle_metadata`**
   - `ALTER TABLE knowledge_documents ADD COLUMN updated_at TIMESTAMPTZ` (nullable)
   - `UPDATE knowledge_documents SET updated_at = uploaded_at WHERE updated_at IS NULL`
   - Assert zero remaining `NULL` rows (abort loudly otherwise, matching the project's established migration pattern)
   - `ALTER TABLE knowledge_documents ALTER COLUMN updated_at SET NOT NULL`, with `server_default = now()`
   - `ALTER TABLE knowledge_documents ADD COLUMN indexed_at TIMESTAMPTZ` (nullable, no backfill assertion needed — nullable is the permanent, correct state for non-ready rows)
   - `UPDATE knowledge_documents SET indexed_at = uploaded_at WHERE status = 'ready'`
   - `ALTER TABLE knowledge_documents ADD COLUMN safe_error_message TEXT` (nullable, no backfill — `NULL` is correct for every pre-existing row)
   - **Downgrade**: drop all three columns.

2. **`add_knowledge_document_replaces_document_id`** (depends on migration 1)
   - `ALTER TABLE knowledge_documents ADD COLUMN replaces_document_id UUID` (nullable, no backfill — `NULL` is correct for every pre-existing row)
   - `ALTER TABLE knowledge_documents ADD CONSTRAINT ... FOREIGN KEY (replaces_document_id) REFERENCES knowledge_documents(id)`
   - **Downgrade**: drop the FK/column.

Both migrations preserve every existing Albertos row's data untouched
beyond the deterministic backfill above; neither deletes or rewrites
existing `KnowledgeDocument` or `DocumentChunk` rows.
