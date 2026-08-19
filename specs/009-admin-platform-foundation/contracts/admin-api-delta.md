# Contract Delta: Admin API

Describes what changes and what does not, relative to the API surface
that exists immediately before this feature (`src/shiruno/api/routers/`).
Follows the same delta-document convention as
`specs/004-rag-answerability-and-ollama-performance/contracts/chat-endpoint-delta.md`
and `specs/008-shiruno-repository-architecture/contracts/http-api-unchanged.md`.

## New: `GET /api/v1/admin/me`

New router, `api/routers/admin.py`, `prefix="/api/v1/admin"`. Requires
authentication (`get_current_administrator` + `get_current_tenant`,
research.md §5).

**Request**: no body, no query parameters. `Authorization: Bearer <token>`
required.

**Response `200`**:

```json
{
  "administrator": {
    "id": "3f1a2b4c-...",
    "username": "admin"
  },
  "tenant": {
    "id": "9c8d7e6f-...",
    "name": "Albertos",
    "slug": "albertos"
  }
}
```

Fields are exactly these — no `password_hash`, no token internals, no
other administrators in the tenant, no other tenant's data, ever
(FR-019, FR-020).

**Response `401`** (missing token, invalid/expired token, or the caller's
tenant is `inactive`): identical generic `{"detail": "Authentication
required or invalid."}` shape already used by every other authenticated
route (`api/errors.py::UnauthorizedError`) — deliberately indistinguishable
across all three causes (FR-016, FR-017, FR-018).

**Client-supplied tenant selection**: none accepted. There is no request
field, query parameter, or header this endpoint reads to determine which
tenant to return — the response is always the caller's own tenant,
resolved entirely server-side (FR-012, FR-013).

## Changed: `POST /api/v1/documents`, `GET /api/v1/documents`, `DELETE /api/v1/documents/{document_id}`

Paths, methods, authentication requirement, and response shapes are
**unchanged**. Behavior changes only in scope:

- `POST /api/v1/documents` now stamps the created document with the
  authenticated administrator's tenant. The response body
  (`DocumentSummary`) is unchanged.
- `GET /api/v1/documents` now returns only documents belonging to the
  authenticated administrator's tenant, instead of every document in the
  system. For the current single-real-tenant (Albertos) deployment, this
  is not observable — the returned set is identical, since Albertos is
  the only tenant with real documents.
- `DELETE /api/v1/documents/{document_id}` now returns `404` (unchanged
  status code and body shape, `NotFoundAppError`) for a document id that
  exists but belongs to a different tenant, in addition to the existing
  `404` for an id that does not exist at all — the two cases are and
  remain indistinguishable to the caller (FR-018, FR-024).

No new required request field, header, or query parameter is introduced
on any of these three routes. No client input can select which tenant's
documents are affected (FR-013).

## Unchanged: `POST /api/v1/auth/login`

Path, request shape, response shape, and failure behavior are all
unchanged (FR-011). The issued JWT still encodes only the administrator's
id (`sub` claim) — tenant membership is looked up server-side from
`Administrator.tenant_id` on every subsequent request via
`get_current_tenant`, never embedded in or trusted from the token itself
beyond identifying the administrator.

## Unchanged: `POST /api/v1/chat` and all public routes

No change of any kind. See FR-021/FR-022 and
`specs/008-shiruno-repository-architecture/contracts/http-api-unchanged.md`
for the pre-existing baseline this feature does not touch.
