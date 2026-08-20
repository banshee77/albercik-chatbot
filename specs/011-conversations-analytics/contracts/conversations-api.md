# Contract: `/api/v1/admin/conversations`

New resource — no existing endpoint changes. Follows the same delta-document
convention as `specs/010-knowledge-base-admin/contracts/documents-api-delta.md`.
Both routes require authentication (`get_current_administrator` +
`get_current_tenant`), exactly like every other tenant-scoped admin route.

## New: `GET /api/v1/admin/conversations`

**Query parameters** (all optional):

| Param | Type | Default | Notes |
|---|---|---|---|
| `outcome` | one of `grounded`, `insufficient_information`, `out_of_scope`, `unavailable`, `small_talk` | none (no filter) | Invalid value → `400`. |
| `start_date` | ISO 8601 date/datetime | none | Inclusive lower bound on `created_at`. |
| `end_date` | ISO 8601 date/datetime | none | Inclusive upper bound on `created_at`. |
| `q` | string | none | Case-insensitive substring match over `question` (research.md §8). |
| `limit` | integer | `20` | Clamped to `[1, 100]` — never rejected, never exceeded (FR-019, research.md §7). |
| `offset` | integer | `0` | Clamped to `>= 0`. |

**Response `200`**:

```json
{
  "items": [
    {
      "id": "...",
      "request_id": "...",
      "question": "Kiedy są zajęcia dla początkujących?",
      "outcome": "grounded",
      "created_at": "2026-08-20T10:15:00Z",
      "latency_ms": 1180
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

- Ordered by `created_at` descending, ties broken by `id` descending, for a
  fully deterministic order (FR-017).
- `total` reflects the count matching all applied filters, independent of
  `limit`/`offset` — a client can compute whether more pages exist.
- Zero matches (including a tenant with no conversations at all) returns
  `200` with `"items": [], "total": 0` — never an error (FR-020).
- No field here exposes another tenant's data, a raw provider error, or
  admin-only detail beyond what's already listed — the list stays
  intentionally lightweight (spec.md "Keep list responses lightweight").

## New: `GET /api/v1/admin/conversations/{conversation_id}`

**Response `200`**:

```json
{
  "id": "...",
  "request_id": "...",
  "question": "Kiedy są zajęcia dla początkujących?",
  "answer": "Zajęcia dla początkujących odbywają się...",
  "outcome": "grounded",
  "created_at": "2026-08-20T10:15:00Z",
  "latency_ms": 1180,
  "sources": [
    {"document_id": "...", "label": "treningi.txt"},
    {"document_id": "...", "label": "sekcje.txt"}
  ],
  "provider_name": "ollama",
  "provider_model": "qwen3:8b",
  "input_tokens": 512,
  "output_tokens": 96,
  "provider_metrics": null,
  "safe_failure_category": null
}
```

- `sources` is `null` for every outcome except `grounded` (FR-005, FR-006) —
  never a fabricated or empty-list placeholder standing in for "no
  sources," to keep "grounded with sources" and "not grounded" visibly
  distinct.
- `provider_name`/`provider_model`/`input_tokens`/`output_tokens`/
  `provider_metrics` are all `null` together whenever no real provider call
  was attempted (small_talk, out_of_scope, the zero-chunk
  insufficient_information case, and the non-`provider_error` flavors of
  `unavailable` — data-model.md "Lifecycle rules").
- `safe_failure_category` is non-`null` only when `outcome = "unavailable"`.
- No field exposes raw embedding vectors, internal storage locations,
  secrets, or another tenant's documents (FR-015).
- **Every field on this response is an immutable snapshot taken when the
  conversation was originally recorded** (research.md §2a, data-model.md
  "Lifecycle rules") — this endpoint never reconstructs, refreshes, or
  re-derives a value from current state. Concretely: if the document(s)
  named in `sources` are later replaced or deleted (feature
  010-knowledge-base-admin), this response keeps showing the original
  label/id exactly as recorded, even though that document id may now
  `404` from `GET /documents/{id}`. If the deployment's configured LLM
  provider or model changes after this conversation was recorded,
  `provider_name`/`provider_model` keep showing whichever provider/model
  actually answered it at the time — never the currently configured one.

**Response `404`**: the conversation does not exist, or belongs to another
tenant — both cases return the identical body, so a cross-tenant lookup is
indistinguishable from a lookup of a nonexistent record (FR-022, FR-035).
