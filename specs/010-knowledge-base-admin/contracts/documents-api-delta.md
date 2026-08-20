# Contract Delta: `/api/v1/documents`

Describes what changes and what does not, relative to the API surface
that exists immediately before this feature. Follows the same
delta-document convention as
`specs/009-admin-platform-foundation/contracts/admin-api-delta.md`.

## Unchanged: `POST /api/v1/documents`, `GET /api/v1/documents`, `DELETE /api/v1/documents/{document_id}`

Paths, methods, authentication requirement, request shape, and response
shape are all unchanged. `GET /api/v1/documents`'s response items gain
three additional fields (see `DocumentSummary` below) — a purely additive
JSON change, not a breaking one.

## New: `GET /api/v1/documents/health`

**MUST be registered before `GET /documents/{document_id}` in the
router** (research.md §2) — a literal `/health` path would otherwise be
captured by the `{document_id}` pattern and fail UUID coercion (`422`)
before ever reaching this route.

Requires authentication (`get_current_administrator` + `get_current_tenant`).

**Response `200`**:

```json
{
  "documents": {
    "total": 12,
    "ready": 11,
    "processing": 0,
    "failed": 1
  },
  "chunks": 184,
  "ready_for_chat": true,
  "last_indexed_at": "2026-08-19T20:49:32.483546Z"
}
```

- `documents.total` = count of the tenant's non-deleted documents
  (`ready` + `processing` + `failed`).
- `chunks` = count of `DocumentChunk` rows belonging to the tenant's
  currently `ready`, non-deleted documents — i.e., chunks that actually
  participate in retrieval right now.
- `ready_for_chat` = `documents.ready > 0`.
- `last_indexed_at` = `MAX(indexed_at)` across the tenant's `ready`
  documents, or `null` if none.

A tenant with zero documents returns `{"documents": {"total": 0, "ready":
0, "processing": 0, "failed": 0}, "chunks": 0, "ready_for_chat": false,
"last_indexed_at": null}` — `200`, never an error (FR-030).

## New: `GET /api/v1/documents/{document_id}`

Requires authentication. Returns the same `DocumentSummary` shape as a
list item (research.md §5). `404` (`NotFoundAppError`) if the id does not
exist, belongs to another tenant, or refers to a soft-deleted/retired
document — all three cases return the identical response body, per
FR-032.

## New: `POST /api/v1/documents/{document_id}/replace`

Multipart file upload, same shape as `POST /documents`. Requires
authentication. The `{document_id}` path parameter identifies the
**predecessor** the caller wants to replace.

**Response `201`**: a `DocumentSummary` for the **new successor**
document — mirrors `POST /documents`'s existing "always 201, `status`
field reflects the outcome" contract (research.md §3). `status: "ready"`
means the replacement is now active and the predecessor has been
retired; `status: "failed"` means the predecessor is **unchanged and
still active** — the response's `error_message` field carries the safe
failure summary.

Two concurrent replace requests for the same predecessor MUST NOT both
report `status: "ready"`. Exactly one may win (its successor activates,
the predecessor is retired); the other's successor is created but
persists as `status: "failed"` with `error_message: "This document was
already replaced by another request."` — a distinct, specific failure
reason from ordinary validation/embedding failure, produced by the
row-locked eligibility re-check (research.md §3, data-model.md's
concurrency invariant). The losing successor's chunks are never
retrievable, since retrieval requires `status == ready`.

**Response `404`**: predecessor does not exist, belongs to another
tenant, is already deleted/retired, or is not currently eligible (e.g.,
already superseded) — identical body across all cases.

**Response `400`/`413`**: replacement content fails the same
validation/size checks as a new upload — identical to `POST /documents`'s
existing behavior.

## New: `POST /api/v1/documents/{document_id}/reindex`

No request body. Requires authentication.

**Response `200`**: a `DocumentSummary` for the **same** document
(`id` unchanged). If regeneration succeeds: `status: "ready"`,
`indexed_at` updated, `error_message: null`. If regeneration fails and
the document was already `ready`: `status` stays `"ready"` — **the
document keeps serving retrieval** — but `error_message` is set to
describe the failed re-index attempt (research.md §4). If regeneration
fails and the document was already `failed`: `status` stays `"failed"`,
`error_message` updated to the latest attempt.

**Response `404`**: document does not exist, belongs to another tenant,
or is soft-deleted — identical body across all cases.

**Response `409`** (or equivalent existing conflict convention): the
document is currently mid-processing (defensive check; unreachable in
practice given synchronous ingestion — research.md notes this).

The requester cannot supply or influence embedding provider, embedding
model, chunk size, chunk overlap, or similarity settings — the endpoint
accepts no body and no query parameters that map to any of these.

## `DocumentSummary` (changed — additive only)

```json
{
  "id": "...",
  "filename": "godziny.txt",
  "content_type": "text/plain",
  "status": "ready",
  "uploaded_at": "2026-08-19T20:49:32.483546Z",
  "updated_at": "2026-08-19T20:49:32.483546Z",
  "indexed_at": "2026-08-19T20:49:33.100000Z",
  "error_message": null
}
```

- `content_type` — new, always `"text/plain"` today (research.md §6; the
  system only accepts `.txt` uploads).
- `updated_at` — new.
- `indexed_at` — new, nullable.
- `error_message` — new, nullable; `safe_error_message` from the model —
  always one of a small, fixed set of generic strings, never raw
  exception detail (FR-004, FR-013, research.md §10a).
- `uploaded_at` is unchanged in name and meaning (research.md §7) —
  existing tests asserting on it are unaffected.

No field exposes filesystem paths, internal storage locations, raw
embedding vectors, credentials, or unsanitized technical detail (FR-004).

## Unchanged: `POST /api/v1/chat` and all public routes

No change of any kind (FR-037, FR-038, FR-039).
