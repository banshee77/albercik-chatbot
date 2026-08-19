# Phase 1 Data Model: Admin Platform Foundation & Tenant Boundary

All types/conventions below match `src/shiruno/persistence/models.py`'s
existing style exactly (see research.md §1). This document describes the
target shape after this feature; it does not restate unrelated existing
tables (`DocumentChunk`, `UsageRecord`, `RateLimitWindow`) except where
their relationships change.

## Tenant (new)

Represents one customer of the Shiruno platform. First-class security
boundary per constitution Principle II.

| Column | Type | Constraints |
|---|---|---|
| `id` | `Uuid` | PK, `default=uuid.uuid4` |
| `name` | `String` | `NOT NULL` |
| `slug` | `String` | `NOT NULL`, `UNIQUE` |
| `status` | `Enum(TenantStatus)` | `NOT NULL`, default `active` |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now()` |
| `updated_at` | `DateTime(timezone=True)` | `server_default=func.now()`, `onupdate=func.now()` |

```python
class TenantStatus(enum.StrEnum):
    active = "active"
    inactive = "inactive"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=TenantStatus.active,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**Lifecycle**: created only via the Albertos migration bootstrap or the
`create-tenant` CLI command (research.md §6). No supported operation in
this feature transitions `status` from `active` to `inactive`
(Clarifications, 2026-08-19) — `inactive` exists as a schema value so
FR-017 is testable via direct test setup, but has no production entry
point yet. A future feature may add one.

## Administrator (changed)

Adds a required tenant association. No other existing column changes.

| Column | Type | Constraints | Change |
|---|---|---|---|
| `id` | `Uuid` | PK | unchanged |
| `username` | `String` | `NOT NULL`, `UNIQUE` (platform-wide — Clarifications, 2026-08-19) | unchanged |
| `password_hash` | `Text` | `NOT NULL` | unchanged |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now()` | unchanged |
| `is_active` | `Boolean` | `NOT NULL`, default `True` | unchanged |
| `tenant_id` | `Uuid` | `NOT NULL`, FK → `tenants.id` | **new** |

```python
tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
```

**Migration/backfill rule**: every pre-existing `Administrator` row is
assigned `tenant_id` = the Albertos tenant's id, deterministically, before
the column is made `NOT NULL` (research.md §9). No administrator can exist
without a tenant after this migration (FR-028).

## KnowledgeDocument (changed)

Adds a required tenant association, making existing admin document
management tenant-scoped (research.md §3). No other existing column
changes; `DocumentChunk` is unchanged (ownership enforced transitively
through its parent document).

| Column | Type | Constraints | Change |
|---|---|---|---|
| `id` | `Uuid` | PK | unchanged |
| `original_filename` | `Text` | `NOT NULL` | unchanged |
| `uploaded_by_admin_id` | `Uuid` | FK → `administrators.id` | unchanged |
| `uploaded_at` | `DateTime(timezone=True)` | `server_default=func.now()` | unchanged |
| `status` | `Enum(DocumentStatus)` | `NOT NULL` | unchanged |
| `deleted_at` | `DateTime(timezone=True)` | nullable | unchanged |
| `tenant_id` | `Uuid` | `NOT NULL`, FK → `tenants.id` | **new** |

```python
tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
```

**Migration/backfill rule**: every pre-existing `KnowledgeDocument` row
(all of them Albertos's, since Albertos is the only customer with real
data) is assigned `tenant_id` = the Albertos tenant's id before the column
is made `NOT NULL` (research.md §9, mirrors the `Administrator` backfill).

**Application behavior change**: `upload_document(...)` gains a required
`tenant_id` parameter and stamps it on the new row.
`list_documents(session, tenant_id)` filters
`WHERE tenant_id = :tenant_id`. `delete_document(document_id, session,
tenant_id)` treats a document that exists but belongs to a different
tenant identically to a nonexistent document — raises the existing
`NotFoundAppError`, no new branch, no distinguishable response (FR-018,
FR-024).

## Relationships (target state)

```text
Tenant (1) ──< Administrator (many)
Tenant (1) ──< KnowledgeDocument (many)
KnowledgeDocument (1) ──< DocumentChunk (many)   [unchanged]
```

No other table changes. `UsageRecord` and `RateLimitWindow` remain
tenant-unaware (constitution Principle II Rule 10 — not retroactively
tenant-owned by this amendment; neither has an admin-facing per-tenant
view today).

## Tenant Context (not persisted)

`Tenant Context` from the spec's Key Entities is not a table — it is the
`Tenant` object returned by the `get_current_tenant` FastAPI dependency
(research.md §5), always derived from `get_current_administrator`'s
resolved `Administrator.tenant_id`, never from request input. No schema
entry corresponds to it.

## Cross-cutting rules

- Every `tenant_id` foreign key is `NOT NULL` after migration — no
  nullable tenant ownership remains on `Administrator` or
  `KnowledgeDocument` (spec's Database Migration requirement, item 11).
- `Tenant.slug` uniqueness is enforced at the database level
  (`UNIQUE`), not merely application-checked (research.md §2).
- No cascade delete is configured from `Tenant` to `Administrator` or
  `KnowledgeDocument` — this feature introduces no tenant-deletion path,
  so the question of cascade behavior does not yet arise; the FK uses the
  database's default (`NO ACTION`), matching how `KnowledgeDocument`'s
  existing FK to `Administrator` already behaves.

## Migration plan (Alembic)

Two migrations, in order (research.md §9 has the full rationale):

1. **`add_tenants_table_and_administrator_tenant_id`**
   - `CREATE TYPE tenant_status AS ENUM ('active', 'inactive')`
   - `CREATE TABLE tenants (...)`
   - `INSERT INTO tenants (id, name, slug, status) VALUES (gen_random(), 'Albertos', 'albertos', 'active') RETURNING id` — captured for the next step
   - `ALTER TABLE administrators ADD COLUMN tenant_id UUID` (nullable)
   - `UPDATE administrators SET tenant_id = :albertos_id WHERE tenant_id IS NULL`
   - Assert zero remaining `NULL` rows (abort loudly otherwise, matching `48197330146f`'s pattern)
   - `ALTER TABLE administrators ALTER COLUMN tenant_id SET NOT NULL`
   - `ALTER TABLE administrators ADD CONSTRAINT ... FOREIGN KEY (tenant_id) REFERENCES tenants(id)`
   - **Downgrade**: drop the FK/column from `administrators`, drop `tenants`, drop the `tenant_status` enum type.

2. **`add_knowledge_document_tenant_id`** (depends on migration 1)
   - `ALTER TABLE knowledge_documents ADD COLUMN tenant_id UUID` (nullable)
   - `UPDATE knowledge_documents SET tenant_id = (SELECT id FROM tenants WHERE slug = 'albertos') WHERE tenant_id IS NULL`
   - Assert zero remaining `NULL` rows
   - `ALTER TABLE knowledge_documents ALTER COLUMN tenant_id SET NOT NULL`
   - `ALTER TABLE knowledge_documents ADD CONSTRAINT ... FOREIGN KEY (tenant_id) REFERENCES tenants(id)`
   - **Downgrade**: drop the FK/column from `knowledge_documents`.

Both migrations are additive/safe (no data deleted or rewritten beyond the
deterministic backfill), reversible (`downgrade()` fully undoes the
`upgrade()`), and deterministic (the backfill target is looked up by the
fixed `albertos` slug, never guessed).
