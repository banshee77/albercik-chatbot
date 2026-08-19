# Phase 0 Research: Admin Platform Foundation & Tenant Boundary

All decisions below resolve the "planning phase determines..." items the
spec (`spec.md`) deliberately deferred. No `NEEDS CLARIFICATION` markers
remain in `plan.md`'s Technical Context — every unknown is resolved here
against the existing codebase's own conventions (`src/shiruno/`), so this
feature reads as a natural extension of Feature 001-008, not a new style.

## 1. Tenant primary key type and table shape

**Decision**: `Tenant.id` is a `Uuid` primary key with `default=uuid.uuid4`,
matching every existing entity (`Administrator`, `KnowledgeDocument`,
`DocumentChunk`, `UsageRecord`). `status` is a `StrEnum` (`TenantStatus`:
`active`, `inactive`) stored via SQLAlchemy `Enum(..., values_callable=...)`,
matching the exact pattern already used for `DocumentStatus`,
`ProviderKind`, and `ProviderName` in `persistence/models.py`. `slug` is a
`String`, `unique=True`, `nullable=False`. `name` is `String`,
`nullable=False`. `created_at`/`updated_at` are `DateTime(timezone=True)`;
`created_at` uses `server_default=func.now()` (matching every other
`created_at` in the schema); `updated_at` additionally sets
`onupdate=func.now()` since it is the first mutable-timestamp column in
this schema (no existing column to copy that convention from, but it is
the standard SQLAlchemy idiom and the simplest correct choice).

**Rationale**: Zero new conventions introduced — a reviewer who knows the
existing models already knows this one.

**Alternatives considered**: Integer/serial PK — rejected, inconsistent
with every existing table and gives no benefit here. `slug` as the primary
key (natural key) — rejected, the codebase's convention is always a
surrogate UUID PK with a separately unique-constrained natural identifier
(mirrors `Administrator.username`).

## 2. Tenant slug validation

**Decision**: Slug format (lowercase, digits, hyphens) is validated at the
CLI/application boundary (a small check in `cli.py`'s `create-tenant`
argument handling), not as a database `CHECK` constraint.

**Rationale**: The existing schema has no `CHECK` constraints anywhere
(only `UNIQUE`, `Enum`, and `NOT NULL`) — matching that precedent is
simpler than introducing a new constraint category for one column
(Principle XIII, Simplicity). Uniqueness — the property this feature's
tests actually need to prove (FR-002) — is still a real database
constraint (`UNIQUE`), not merely application-checked.

**Alternatives considered**: A `CHECK (slug ~ '^[a-z0-9-]+$')` constraint —
rejected as unnecessary defense-in-depth for an operator-only, CLI-driven
field with no public write path.

## 3. Tenant-owned resource used to prove cross-tenant isolation

**Decision**: `KnowledgeDocument` gains a required `tenant_id` FK now,
rather than introducing a separate throwaway "test-only" resource/table.
Existing admin document upload/list/delete (`api/routers/documents.py`,
`application/upload_document.py`, `application/list_documents.py`,
`application/delete_document.py`) become tenant-scoped: upload stamps the
authenticated administrator's tenant, list filters to it, and delete/get
treat a document belonging to another tenant exactly like a nonexistent
one (`NotFoundAppError`, reusing the existing 404 branch — no new
information-disclosure surface). Cross-tenant isolation (User Story 3) is
proven against these real, already-shipped endpoints using a second
test-only tenant/administrator, not a synthetic resource.

**Rationale**: The spec's Assumptions section explicitly left this as a
planning decision ("Whether the existing document records themselves gain
an explicit organization-ownership column now... is a technical decision
made during planning") and separately requires (FR-024) that this
feature's data model must not leave a state where a future second tenant's
documents could be reached by today's administrator. Scoping
`KnowledgeDocument` now is strictly simpler than doing both — building a
one-off synthetic "prove-it" resource *and* separately guaranteeing
`KnowledgeDocument` isolation later — and it gives the isolation tests
real production value instead of testing a resource nobody ships.
`DocumentChunk` needs no `tenant_id` of its own: it has no independent
admin-facing endpoint and is only ever reached through its parent
`KnowledgeDocument`, so ownership is enforced transitively.

**What this does NOT change**: The public `/api/v1/chat` retrieval path
(`domain/retrieval.py`, `application/ask_question.py`) is untouched — it
has no administrator identity to scope by, Albertos is still the only
tenant with real chunks, and FR-021/FR-022 require the public contract to
stay unchanged. Retrieval continues to query `DocumentChunk`/
`KnowledgeDocument` exactly as before; only the *admin-authenticated
management* endpoints gain a tenant filter.

**Alternatives considered**: A new `TenantScopedTestResource` table/router
used only by tests — rejected as speculative infrastructure with no
production purpose, the opposite of what Principle XIII (Simplicity) and
this constitution's amended Principle II Rule 10 ("tenant ownership...
when that entity becomes part of the reusable platform/customer
boundary") ask for; `KnowledgeDocument` already *is* that boundary.
Leaving `KnowledgeDocument` untouched and proving isolation only at the
dependency layer (no HTTP round-trip) — rejected, weaker proof that would
miss a route wired without the new dependency, and the spec's own framing
("test-only path necessary to prove tenant isolation... at the new
foundation boundary") anticipates exercising a real request path.

## 4. Admin API namespace and the new identity endpoint

**Decision**: A new router, `api/routers/admin.py`, registered with
`prefix="/api/v1/admin"`, exposing exactly one route:
`GET /api/v1/admin/me`. Existing `POST /api/v1/auth/login` and the
`/api/v1/documents` routes are **not** moved under `/admin` in this
feature — they keep their current paths, which already satisfy FR-023
("existing... capabilities MUST continue to function") without a
relocation the spec never asks for.

**Rationale**: This establishes the `/api/v1/admin/...` namespace the
spec calls "the preferred conceptual direction" for future admin features
(Feature 010+) to build under, while keeping this feature's surface area
to exactly the one endpoint the spec asks for (FR-019/FR-020). Moving
`/documents` under `/admin` now would be an unrequested breaking rename
with no security benefit — the routes are already administrator-gated.

**Alternatives considered**: Renaming `/api/v1/documents` to
`/api/v1/admin/documents` now — rejected, out of scope (spec explicitly
scopes Knowledge Base Administration to Feature 010) and would be a
gratuitous breaking change for existing integrations/tests.

## 5. `CurrentTenant` / `CurrentAdmin` dependency boundary

**Decision**: `api/deps.py` gains one new dependency,
`get_current_tenant`, layered directly on the existing
`get_current_administrator`:

```python
def get_current_tenant(
    current_admin: Administrator = Depends(get_current_administrator),
    session: Session = Depends(get_session),
) -> Tenant:
    tenant = session.get(Tenant, current_admin.tenant_id)
    if tenant is None or tenant.status != TenantStatus.active:
        raise UnauthorizedError(_GENERIC_AUTH_FAILURE)
    return tenant
```

Any tenant-scoped route declares both
`current_admin: Administrator = Depends(get_current_administrator)` and
`current_tenant: Tenant = Depends(get_current_tenant)`; it never looks up
tenant membership itself.

**Rationale**: `get_current_administrator` already resolves before any
route body runs and already fails closed on missing/invalid/inactive
accounts (existing docstring, `api/deps.py`); composing `get_current_tenant`
on top reuses that guarantee instead of duplicating it, and reuses the
exact same generic `UnauthorizedError` message so a deactivated tenant is
indistinguishable from an invalid token from the outside (constitution
Principle II Rule 7 / FR-018). This is the reusable "authenticated admin →
tenant context → tenant-scoped operation" boundary FR-014 requires,
expressed as two ordinary FastAPI `Depends()` — no new framework.

**Alternatives considered**: A single combined dependency returning
`(Administrator, Tenant)` — rejected; two small composable dependencies
match the existing style (`get_llm_provider`, `get_embedding_provider`,
etc. are each single-purpose) and let a route depend on just
`current_admin` when it genuinely doesn't need tenant scoping (there is no
such route in this feature, but the shape stays honest either way).

## 6. Provisioning mechanism: tenants and tenant-owned administrators

**Decision**: Two complementary mechanisms, matching the spec's explicit
menu of options:

- **Bootstrap**: The Alembic migration that introduces the `tenants` table
  also inserts exactly one row — Albertos (`name="Albertos"`,
  `slug="albertos"`, `status="active"`) — and uses its generated id to
  backfill every pre-existing `Administrator` and `KnowledgeDocument` row.
  This is the same "add nullable → backfill → verify → enforce NOT NULL"
  four-step shape already used by
  `alembic/versions/48197330146f_add_usage_records_provider_name.py`; the
  only difference is that the backfill target value here is a freshly
  inserted row rather than a derived enum value. Re-running this migration
  is not a real-world case Alembic allows (its own `alembic_version`
  tracking prevents a migration from applying twice), so "idempotent
  re-provisioning" for Albertos specifically is structurally guaranteed by
  Alembic itself, not by application code.
- **Ongoing operator tool**: `cli.py` gains a `create-tenant` subcommand
  (`--name`, `--slug`) for any *future* tenant, and `create-admin` gains a
  required `--tenant <slug>` argument. Both reuse the existing
  `IntegrityError` → clear stderr message → `SystemExit(1)` pattern
  `create_admin` already has for duplicate usernames — `create-tenant` on
  an existing slug (including re-running it for `albertos`) fails clearly
  rather than duplicating, satisfying FR-004's "idempotent or fail
  clearly" for the general mechanism. `create-admin` without a matching
  `--tenant` slug fails clearly and creates nothing (FR-009).

**Rationale**: Baking the one-time Albertos bootstrap into the migration
avoids inventing a second "first-run seed script" concept the codebase has
never needed before (Principle XIII), while the CLI stays the actual
"provisioning mechanism" surface named throughout the spec for every
tenant after the first. This mirrors how `Administrator` itself is
provisioned today: CLI-only, no HTTP endpoint, no auto-seeding on startup
(FR-006).

**Alternatives considered**: A standalone Python seed script run manually
after `alembic upgrade head` — rejected, adds an extra manual step with no
enforcement that it was actually run, whereas the migration's backfill is
inseparable from `alembic upgrade head` succeeding at all. Auto-creating
Albertos in `create_app()` on startup — explicitly forbidden by FR-006.

## 7. Auditability

**Decision**: `infra/audit.py`'s `log_audit_event` gains an optional
`tenant_id: uuid.UUID | None = None` parameter. `login_success`,
`document_upload`, and `document_delete` call sites pass
`current_tenant.id` (or `current_admin.tenant_id`, equivalent). `login_failure`
leaves it `None` — no administrator (and therefore no tenant) is resolved
on a failed login, so there is nothing truthful to log there.

**Rationale**: Directly satisfies FR-025 using the existing dedicated
audit logger (no new persistence table, no new logging service — Principle
XIII, and the module's own docstring already states its parameter list is
deliberately incapable of carrying sensitive values).

## 8. Response shape for `GET /api/v1/admin/me`

**Decision**:

```json
{
  "administrator": { "id": "...", "username": "..." },
  "tenant": { "id": "...", "name": "Albertos", "slug": "albertos" }
}
```

No `email` field (the spec's example response is explicitly noted as
illustrative in its Assumptions — `Administrator` has no email attribute
today and this feature does not add one). Built via a small manual mapping
function in `api/routers/admin.py`, matching the existing
`documents.py::_to_summary` convention rather than adding
`from_attributes=True` ORM-mode config the rest of `api/schemas.py`
doesn't use.

**Rationale**: Consistency with existing schema/response-building style;
zero new sensitive fields (FR-020).

## 9. Migration sequencing

**Decision**: Two Alembic migrations, chained in order:

1. `add_tenants_table_and_administrator_tenant_id` — creates `tenants`,
   inserts the Albertos row, adds `administrators.tenant_id` (nullable →
   backfilled to Albertos → `NOT NULL` + FK), all in the four-step
   explicit style of the existing `provider_name` migration.
2. `add_knowledge_document_tenant_id` — adds `knowledge_documents.tenant_id`
   (nullable → backfilled to Albertos, since every existing document today
   is Albertos's → `NOT NULL` + FK), same shape.

**Rationale**: Two focused, independently reviewable migrations rather
than one large one, matching how `provider_metrics` and `provider_name`
were introduced as separate migrations even though closely related.
Splitting also keeps the "tenant now exists" step decoupled from the
"documents are now tenant-owned" step, so a future revert of just the
document-scoping decision (unlikely, but cheap to keep possible) doesn't
require reverting tenant existence itself.

## 10. What is explicitly NOT built (confirms spec's Out of Scope)

- No tenant deactivation/activation CLI or API surface (Clarifications
  session 2026-08-19) — `status` is set once, to `active`, at creation;
  `inactive` is exercised only via direct test setup.
- No platform super-admin role, endpoint, or UI.
- No changes to `UsageRecord` or `RateLimitWindow` — neither has an
  admin-facing per-tenant listing today, so neither needs `tenant_id` yet
  (constitution Principle II Rule 10).
- No change to username uniqueness scope (Clarifications session
  2026-08-19) — stays platform-wide.
- No React, no observability platform, no billing — unchanged from spec's
  Out of Scope section.
