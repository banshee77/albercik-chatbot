# Phase 1 Data Model: Shiruno Admin Platform Shell

**Feature**: `013-admin-platform-shell` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## No new backend entities

This feature adds no new database table, column, or migration. It reuses
two existing backend endpoints exactly as they exist today:

- `POST /api/v1/auth/login` (`api/routers/auth.py`) — unchanged.
- `GET /api/v1/admin/me` (`api/routers/admin.py`) — unchanged.

`Administrator`, `Tenant`, and every other persisted entity
(`persistence/models.py`) are untouched (spec FR-031). The only backend
change is additive server configuration: `CORS_ALLOWED_ORIGINS`
(research.md R8).

The "entities" this feature actually introduces are frontend-only state
shapes, held in memory for the lifetime of a browser tab. They are
documented here in place of a conventional data model, matching this
project's own precedent (Feature 012's `data-model.md` did the same for
span schemas when a feature introduced no database change).

## Frontend state shapes

### `AuthState` (research.md R6)

The single source of truth for whether the current tab considers itself
authenticated. Held by one `AuthProvider`; read, never independently
re-derived, by every protected route and by the header.

| Field | Type | Notes |
|---|---|---|
| `status` | `"initializing" \| "unauthenticated" \| "authenticated" \| "error"` | Exactly spec.md's Key Entities enumeration. `"initializing"` is the state on first mount, before any bootstrap attempt has resolved. |
| `administrator` | `AdministratorIdentity \| null` | Non-null only when `status === "authenticated"`. |
| `tenant` | `OrganizationIdentity \| null` | Non-null only when `status === "authenticated"`. |
| `errorMessage` | `string \| null` | Set only on `"error"` — always one of this feature's own safe, generic strings (FR-002, FR-018, FR-019), never raw backend text. |

State transitions (all one-way except explicit `login`/`logout`):

```text
initializing
  ├─(no in-memory token / bootstrap has nothing to check)→ unauthenticated
  ├─(login() succeeds, /admin/me succeeds)→ authenticated
  └─(login() fails, OR /admin/me fails after a fresh login)→ error

unauthenticated
  └─(login() succeeds, /admin/me succeeds)→ authenticated

authenticated
  ├─(logout())→ unauthenticated
  └─(any authenticated API call returns 401/403)→ unauthenticated
      (with a session-expired flag surfaced to the login page — US6)

error
  └─(login() retried and succeeds)→ authenticated
```

There is deliberately no `authenticated → initializing` transition and no
persisted-session rehydration path: per research.md R1, a full page
reload always restarts at `initializing → unauthenticated` (no stored
token to recover), never silently re-enters `authenticated`.

### `AdministratorIdentity`

Mirrors `AdministratorOut` (`api/schemas.py`) exactly — the frontend adds
no field the backend doesn't already return.

| Field | Type | Source |
|---|---|---|
| `id` | `string` (UUID) | `AdminMeResponse.administrator.id` |
| `username` | `string` | `AdminMeResponse.administrator.username` |

### `OrganizationIdentity`

Mirrors `TenantOut` (`api/schemas.py`) exactly.

| Field | Type | Source |
|---|---|---|
| `id` | `string` (UUID) | `AdminMeResponse.tenant.id` — never rendered as primary UI text (FR-008); available only for internal use (e.g., React key props), not display. |
| `name` | `string` | `AdminMeResponse.tenant.name` — the primary display value everywhere "organization" is shown. |
| `slug` | `string` | `AdminMeResponse.tenant.slug` |

`TenantOut` does not currently expose `status`; nothing in this feature
adds it, per spec.md's Assumptions ("tenant slug/name/status where
exposed by the existing contract").

### `ApplicationRoute`

Not a runtime data object — the fixed set of routes this feature
registers, listed here for traceability back to FR-009:

| Path | Protected? | Content in this feature |
|---|---|---|
| `/login` | No | Functional login form |
| `/app` | Yes | Minimal home: organization identity, welcome state, navigation shortcuts (spec.md US1 Scenario 2, Key Entities) |
| `/app/knowledge` | Yes | Placeholder only (FR-011) |
| `/app/conversations` | Yes | Placeholder only (FR-011) |
| `/app/analytics` | Yes | Placeholder only (FR-011) |

## Configuration additions

- **Backend** (`src/shiruno/config.py`): one new setting,
  `CORS_ALLOWED_ORIGINS: str = ""` (research.md R8).
- **Frontend** (`apps/admin/.env`, git-ignored, with a committed
  `.env.example`): `VITE_SHIRUNO_API_URL` (research.md R9) — the only
  frontend environment variable this feature introduces; it is public by
  definition (FR-023) and carries no secret.
