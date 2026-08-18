# Phase 1 Data Model: Albertos RAG Support Chatbot (MVP)

Derived from the spec's Key Entities section and resolved against the Phase 0
research decisions (embedding dimensionality, rate limiting, budget
accounting). Single-tenant per constitution Principle II: no `organization_id`
or tenant column appears anywhere below.

## Entity overview

```text
Administrator ──────────────< (attributed to) uploads/deletes
KnowledgeDocument ──1───────< DocumentChunk (embedding stored inline on the chunk)
UsageRecord            (independent log, one row per LLM/embedding provider call)
RateLimitWindow         (independent counter, one row per source+window)
```

`Chat Interaction` from the spec's Key Entities is **not** a persisted table —
per the spec's own Assumptions ("not required to be retained as durable
conversation history"), it exists only for the duration of a single request/
response cycle.

## KnowledgeDocument

Represents one uploaded Albertos `.txt` file.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | System-generated; the uploaded filename is never used as a storage key (FR-013). |
| `original_filename` | text | Stored for display/audit only — never interpreted as a path (FR-012, FR-013). |
| `uploaded_by_admin_id` | UUID (FK → `Administrator.id`) | Attributes the upload for audit logging (FR-053). |
| `uploaded_at` | timestamptz | |
| `status` | enum: `processing`, `ready`, `failed` | `ready` once all chunks are embedded and stored; supports FR-016/FR-050 (a document isn't answerable mid-processing). |
| `deleted_at` | timestamptz, nullable | Soft-delete marker. A non-null value excludes the document (and its chunks) from every retrieval query — see Validation rules. |

**Validation rules**:
- Rejected before a row is created (FR-010/FR-011): not `.txt`, not valid UTF-8, empty/whitespace-only content, or over the configured max size.
- `original_filename` is sanitized for display but never used to derive a filesystem or storage path.

**Lifecycle**: `processing` → `ready` (normal path) or `processing` → `failed`
(chunking/embedding error; no chunks are stored, document is not retrievable,
error is surfaced per FR-050 without internal detail). `ready` → soft-deleted
(FR-015/FR-016): chunks tied to it are immediately excluded from retrieval
queries; hard deletion of the underlying rows may happen later via a cleanup
job, but is not required for MVP correctness since the query layer must
already filter on `deleted_at IS NULL`.

## DocumentChunk

A segment of a `KnowledgeDocument`, carrying its own embedding inline (no
separate `ChunkEmbedding` table — pgvector stores the vector as a column on
the same row that owns the text, which is both simpler and avoids a join on
every retrieval query).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `document_id` | UUID (FK → `KnowledgeDocument.id`) | |
| `position` | integer | 0-based order within the source document (FR-020). |
| `content` | text | Never empty (FR-021 — empty chunks are dropped before insert, not stored and later filtered). |
| `embedding` | `vector(384)` (pgvector) | Dimension fixed by the local `intfloat/multilingual-e5-small` `sentence-transformers` model (research.md §4); MUST match whatever `EmbeddingProvider` implementation is active (FR-024). |
| `created_at` | timestamptz | |

**Indexes**: `HNSW` index on `embedding` using cosine distance ops
(`vector_cosine_ops`); a plain index on `document_id` for deletion/listing.

**Validation rules**: `position` is unique per `document_id`; chunk ordering
is preserved by construction (chunker emits chunks in document order and
`position` is assigned sequentially — FR-020).

## Administrator

An authenticated operator. Multiple accounts may exist (per the clarification
session), all in a single privilege tier.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `username` | text, unique | |
| `password_hash` | text | `bcrypt` hash; the plaintext password is never stored or logged (FR-051/FR-052). |
| `created_at` | timestamptz | |
| `is_active` | boolean, default `true` | Allows disabling an account (e.g., offboarding) without deleting audit-log attribution on past actions. |

**Validation rules**: provisioned only via an out-of-band CLI seed command
(FR-004a) — no HTTP endpoint creates a row here. Login checks `is_active`
in addition to the password hash.

## UsageRecord

One row per LLM or embedding provider call, for cost/usage visibility.
Deliberately excludes prompt/document content (FR-048).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `request_id` | UUID | Correlates to the originating HTTP request (for tracing without storing content). |
| `provider_kind` | enum: `llm`, `embedding` | |
| `provider_model` | text | e.g., `claude-...`, `intfloat/multilingual-e5-small`. Embedding rows record latency/success for observability even though local embedding calls carry no per-call provider cost. |
| `input_tokens` | integer, nullable | Null when the provider doesn't report it (e.g., some embedding calls). |
| `output_tokens` | integer, nullable | |
| `success` | boolean | |
| `latency_ms` | integer | |
| `created_at` | timestamptz | Indexed — budget checks (research.md §3) query this column over a rolling/fixed window. |

**Validation rules**: never contains prompt text, document content, API keys,
or credentials (FR-048, Principle IX).

## RateLimitWindow

Backs the Postgres-based rate limiter (research.md §2). Not a business
entity — pure infrastructure state — but persisted for cross-process
correctness.

| Field | Type | Notes |
|---|---|---|
| `source_key` | text | Client IP as resolved via trusted-proxy config (FR-040); part of composite PK. |
| `window_start` | timestamptz | Start of the fixed window (e.g., truncated to the minute); part of composite PK. |
| `request_count` | integer | Incremented atomically per request via `INSERT ... ON CONFLICT (source_key, window_start) DO UPDATE SET request_count = request_count + 1`. |

**Lifecycle**: rows older than the current window (plus one) are eligible for
lazy pruning; no row is retained indefinitely.

## Cross-cutting rules enforced at the data layer

- **No tenant column anywhere** (constitution Principle II) — every query
  above is scoped only by the entity's own identifiers (document id, admin
  id), never by an `organization_id` that doesn't exist in this schema.
- **Soft-deleted documents/chunks are excluded from retrieval** by a
  `WHERE deleted_at IS NULL` (or an equivalent join filter) at the query
  layer — this is the mechanism behind FR-016/SC-007, verified independently
  by an automated test, not left to application-layer discipline alone.
- **Embedding dimensionality is a schema-level contract** (`vector(384)`,
  matching `intfloat/multilingual-e5-small`) between the `EmbeddingProvider`
  `Protocol` implementation and the `pgvector` column — changing the
  embedding model (via the `EMBEDDING_MODEL_NAME` setting, research.md §4a)
  requires a migration if the new model's dimensionality differs (documented
  consequence of FR-024).
