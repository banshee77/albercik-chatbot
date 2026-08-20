# Phase 1 Data Model: Knowledge Base UI

**Feature**: `014-knowledge-base-ui` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## No new backend entities

This feature adds no new database table, column, or migration, and no new
backend endpoint (research.md R1). It reuses the existing Feature 010
`/api/v1/documents*` surface exactly as it exists today.
`KnowledgeDocument`, `DocumentChunk`, and every other persisted entity
(`persistence/models.py`) are untouched (spec FR-041).

The "entities" this feature introduces are frontend-only state shapes, held
in memory for the lifetime of the Knowledge page. Documented here in place
of a conventional data model, matching this project's own precedent
(Feature 013's `data-model.md` did the same for its `AuthState`).

## Frontend state shapes

### `DocumentSummary` (research.md R1 — mirrors the backend schema exactly)

The frontend adds no field the backend doesn't already return.

| Field | Type | Notes |
|---|---|---|
| `id` | `string` (UUID) | Used to target replace/re-index/delete requests and as the list's React key; never rendered as primary UI text (mirrors Feature 013's `tenant.id` precedent). |
| `filename` | `string` | The safe, user-facing display name everywhere a document is named (list, detail, delete confirmation). |
| `content_type` | `string` | Displayed as-is in detail (currently always `"text/plain"` per the backend, FR-014). |
| `status` | `"processing" \| "ready" \| "failed"` | Mapped to a human-readable label via `statusLabel()` (research.md R6); an unrecognized value falls back to a generic label rather than being assumed Ready/Failed (FR-008). |
| `uploaded_at` | `string` (ISO datetime) | Shown in the document list/detail. |
| `updated_at` | `string` (ISO datetime) | Shown in detail. |
| `indexed_at` | `string \| null` | Shown in detail when present; `null` while never successfully indexed. |
| `error_message` | `string \| null` | The sanitized failure/last-action-issue message (FR-013/FR-020); may be non-null even when `status === "ready"` after a failed re-index attempt on an already-working document (research.md R11) — the frontend always trusts `status`, never infers "broken" from a non-null `error_message` alone. |

### `KnowledgeHealthSummary` (mirrors `KnowledgeHealthResponse` exactly)

| Field | Type | Notes |
|---|---|---|
| `documents.total` / `.ready` / `.processing` / `.failed` | `number` | Rendered as the health summary's counts (FR-001). |
| `chunks` | `number` | "Active chunk count" (FR-001) — never a per-document chunk breakdown or chunk content (FR-002/FR-015). |
| `ready_for_chat` | `boolean` | Rendered as "Ready for chat: Yes/No" (spec's conceptual layout). |
| `last_indexed_at` | `string \| null` | Shown when present. |

### `KnowledgePageState` (page-local, held by `KnowledgePage.tsx` — research.md R8, R9)

Not a network response shape — the page's own orchestration state.

| Field | Type | Notes |
|---|---|---|
| `status` | `"loading" \| "loaded" \| "error"` | Drives FR-034/FR-035: `"loading"` before the first successful `reloadKnowledge()` (research.md R8), `"error"` if that first load fails (distinct from an empty-but-successful load), `"loaded"` once data has arrived at least once. |
| `documents` | `DocumentSummary[]` | Populated by `listDocuments()`; empty array + `status: "loaded"` is the intentional empty state (FR-003), distinct from `status: "error"`. |
| `health` | `KnowledgeHealthSummary \| null` | Populated by `getKnowledgeHealth()`; `null` only before the first successful load. |
| `selectedDocumentId` | `string \| null` | Drives the inline detail panel (research.md R4); looked up against `documents`, never fetched separately in the MVP flow. |
| `pendingAction` | `{ kind: "upload" \| "replace" \| "reindex" \| "delete"; documentId?: string } \| null` | Drives per-action disabled/pending states (FR-011/FR-018/FR-023/FR-027) without a full-page loading flag — only the specific control tied to `pendingAction` is disabled; everything else stays interactive (FR-036). |

### `Document Action` (conceptual, spec Key Entities — not a stored value)

The four mutations this feature exposes, each calling exactly one
`api/knowledge.ts` function (research.md R3) and, on success, invoking
`reloadKnowledge()` (research.md R8):

| Action | Eligible documents | API function |
|---|---|---|
| Upload | N/A (creates a new document) | `uploadDocument(file)` |
| Re-index | Any document except one currently `"processing"` (backend-enforced `409`, research.md R1/R11) | `reindexDocument(id)` |
| Replace | Any document regardless of status — including `"processing"` (spec Clarifications, 2026-08-20; research.md R1) | `replaceDocument(id, file)` |
| Delete | Any document owned by the tenant | `deleteDocument(id)` |

## Configuration additions

None. No new frontend environment variable, no new backend setting — this
feature reuses `VITE_SHIRUNO_API_URL` and the existing `CORS_ALLOWED_ORIGINS`
allow-list Feature 013 already introduced (research.md R1).
