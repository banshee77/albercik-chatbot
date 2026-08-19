---

description: "Task list for Feature 009 — Admin Platform Foundation & Tenant Boundary"
---

# Tasks: Admin Platform Foundation & Tenant Boundary

**Input**: Design documents from `/specs/009-admin-platform-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included — the spec's "Testing requirements" section explicitly mandates automated tests for every isolation/security property, and constitution Principle II Rule 8 makes cross-tenant isolation test coverage NON-NEGOTIABLE.

**Organization**: Tasks are grouped by user story from spec.md, in priority order (P1 stories first: US1, US3, US5; then P2: US2, US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5, per spec.md
- File paths are exact and relative to the repository root.

## Path Conventions

Single existing backend project — `src/shiruno/`, `tests/`, `alembic/versions/` at repository root (plan.md's Structure Decision; no new project is created).

---

## Phase 1: Setup

No setup tasks are required. This feature extends the existing `shiruno`
backend project in place — no new dependency, tool, or project scaffolding
is introduced (plan.md Technical Context: zero new dependencies).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema, dependency, and test-infrastructure changes every
later phase (including the pre-existing test suite) requires to even run,
once `Administrator.tenant_id` becomes `NOT NULL`.

**⚠️ CRITICAL**: No user story task may start until this phase is complete.
In particular, `Administrator.tenant_id NOT NULL` (T002) breaks every
existing test that constructs `Administrator(...)` directly — T010–T014
are not optional cleanup, they are required for the pre-existing suite to
collect and run at all after T002/T004 land.

- [X] T001 [P] Add `TenantStatus` enum and `Tenant` model to `src/shiruno/persistence/models.py` (data-model.md "Tenant": `id` UUID PK, `name`, `slug` unique, `status` enum default `active`, `created_at`, `updated_at`)
- [X] T002 Add required `tenant_id` FK column (`Uuid`, `ForeignKey("tenants.id")`, `nullable=False`) to `Administrator` in `src/shiruno/persistence/models.py` (depends on T001)
- [X] T003 Add required `tenant_id` FK column (`Uuid`, `ForeignKey("tenants.id")`, `nullable=False`) to `KnowledgeDocument` in `src/shiruno/persistence/models.py` (depends on T001)
- [X] T004 Create Alembic migration `add_tenants_table_and_administrator_tenant_id` in `alembic/versions/` — create `tenants` table, insert the Albertos row (`name="Albertos"`, `slug="albertos"`, `status="active"`), add `administrators.tenant_id` nullable → backfill every existing row to Albertos → assert none remain NULL → set `NOT NULL` + FK; full reversible `downgrade()` (data-model.md "Migration plan" §1; depends on T001, T002)
- [X] T005 Create Alembic migration `add_knowledge_document_tenant_id` in `alembic/versions/` (revises T004's migration) — add `knowledge_documents.tenant_id` nullable → backfill every existing row to the Albertos tenant (looked up by slug) → assert none remain NULL → set `NOT NULL` + FK; full reversible `downgrade()` (data-model.md "Migration plan" §2; depends on T003, T004)
- [X] T006 [P] Add `get_current_tenant` FastAPI dependency to `src/shiruno/api/deps.py` — resolves `Tenant` from `current_admin.tenant_id` via `Depends(get_current_administrator)`, raises the existing generic `UnauthorizedError` if the tenant is missing or `status != active` (research.md §5; depends on T001, T002)
- [X] T007 [P] Add optional `tenant_id: uuid.UUID | None = None` parameter to `log_audit_event` in `src/shiruno/infra/audit.py`, included in the log line (research.md §7; depends on T001)
- [X] T008 Add a `default_tenant` pytest fixture (creates and flushes one `Tenant` row via `db_session`) to `tests/conftest.py` (depends on T001)
- [X] T009 Extend `seed_admin_and_token` in `tests/fixtures/admin.py` to accept a required `tenant_id` parameter (no default), and add a `seed_tenant(db_session, **overrides)` helper alongside it (depends on T008)
- [X] T010 [P] Update every `Administrator(...)` seed call to supply `tenant_id` (via T008's `default_tenant` fixture) in `tests/contract/test_chat.py`, `tests/contract/test_chat_small_talk.py`, `tests/contract/test_chat_kill_switch.py`, `tests/contract/test_chat_rate_limit.py`, `tests/contract/test_chat_budget.py` (depends on T008)
- [X] T011 [P] Update every `Administrator(...)` seed call to supply `tenant_id` in `tests/contract/test_chat_usage_accounting.py`, `tests/contract/test_chat_provider_failure.py`, `tests/contract/test_chat_provider_switch.py`, `tests/contract/test_chat_provider_parity.py`, `tests/contract/test_chat_ollama_default.py`, `tests/contract/test_chat_answerability.py`, `tests/contract/test_chat_no_client_override.py` (depends on T008)
- [X] T012 [P] Update every `Administrator(...)` seed call to supply `tenant_id` in `tests/contract/test_prompt_injection_visitor.py`, `tests/contract/test_audit_logging.py`, `tests/contract/test_auth_login.py` (depends on T008)
- [X] T013 [P] Update every `Administrator(...)` seed call to supply `tenant_id` in `tests/integration/test_database_session_commit.py`, `tests/integration/test_retrieval_pgvector.py` (depends on T008)
- [X] T014 [P] Update the two existing `Administrator(...)` seed calls to supply `tenant_id` in `tests/contract/test_documents_auth.py` (depends on T008)

**Checkpoint**: Schema, dependency boundary, and existing test infrastructure are tenant-aware. `uv run pytest tests/contract tests/unit tests/integration -q` should collect and run (still green on everything not yet touched by a later phase). User story work can now begin.

**Execution note**: T009's signature change also required updating 7 files
that call `seed_admin_and_token(...)` directly (not just the raw
`Administrator(...)` construction sites T010–T014 anticipated) —
`test_audit_logging.py`, `test_upload_usage_accounting.py`,
`test_documents_lifecycle.py`, `test_documents_upload.py`,
`test_prompt_injection_no_bypass.py`, `test_document_lifecycle.py`, and
`test_prompt_injection_document.py`. Also, since `KnowledgeDocument.tenant_id`
is `NOT NULL`, T020–T023 (US3's application/router changes, below) turned
out to be a real prerequisite for the pre-existing document-upload test
files to pass, not purely additive — they were implemented alongside
Foundational for that reason. All of this is captured in the actual diff;
noted here for traceability.

---

## Phase 3: User Story 1 - Administrator signs in and is automatically confined to their own organization (Priority: P1) 🎯 MVP

**Goal**: An authenticated administrator can retrieve their own identity
and tenant via a safe endpoint, and cannot influence which tenant is
resolved through any client-supplied value.

**Independent Test**: quickstart.md §3–§4 — log in, call `GET
/api/v1/admin/me`, confirm only the caller's own administrator/tenant is
returned, and that a header/query/body tenant override has no effect.

### Tests for User Story 1

- [X] T015 [US1] Contract tests for `GET /api/v1/admin/me` in `tests/contract/test_admin_me.py`: valid token → 200 with own administrator (`id`, `username` only) and own tenant (`id`, `name`, `slug`); missing token → 401; invalid/expired token → 401; response never includes `password_hash` or a second seeded tenant's data; a supplied `X-Tenant-Id` header / `tenant_id` query param / body field has no effect on the returned tenant (contracts/admin-api-delta.md; depends on T009)

### Implementation for User Story 1

- [X] T016 [US1] Add `AdministratorOut`, `TenantOut`, `AdminMeResponse` Pydantic models to `src/shiruno/api/schemas.py` (contracts/admin-api-delta.md response shape)
- [X] T017 [US1] Create `src/shiruno/api/routers/admin.py` with `prefix="/api/v1/admin"` and `GET /me`, depending on `get_current_administrator` + `get_current_tenant`, mapping to `AdminMeResponse` via a manual `_to_response` helper (matches `documents.py::_to_summary` convention; depends on T006, T016)
- [X] T018 [US1] Register `admin.router` in `create_app()` in `src/shiruno/main.py`, alongside `auth.router`/`documents.router` (depends on T017)

**Checkpoint**: `uv run pytest tests/contract/test_admin_me.py -q` passes independently. User Story 1 is fully functional on its own.

---

## Phase 4: User Story 3 - Cross-customer data access is provably impossible (Priority: P1)

**Goal**: The existing admin document endpoints become tenant-scoped, and
automated tests prove one tenant's administrator can never read, modify,
or delete another tenant's documents — including when a tenant is
deactivated.

**Independent Test**: quickstart.md §5, §7 — with two tenants and one
administrator each, confirm Tenant B's admin cannot see or delete Tenant
A's uploaded document, and that a deactivated tenant's admin is denied.

### Tests for User Story 3

- [X] T019 [US3] Extend `tests/contract/test_documents_auth.py`: (a) an administrator only sees their own tenant's documents in `GET /api/v1/documents`; (b) `DELETE /api/v1/documents/{id}` on another tenant's document returns 404, identical to a nonexistent id; (c) a supplied `X-Tenant-Id` header / `tenant_id` query/body field on any documents route has no effect; (d) an administrator whose tenant's `status` is set to `inactive` directly via `db_session` is denied (401) on every documents route despite an otherwise-valid token (spec Testing Requirements #10, #13; depends on T014)

### Implementation for User Story 3

- [X] T020 [P] [US3] Add a required `tenant_id` parameter to `upload_document(...)` in `src/shiruno/application/upload_document.py`, stamped onto the created `KnowledgeDocument`
- [X] T021 [P] [US3] Add a required `tenant_id` filter parameter to `list_documents(...)` in `src/shiruno/application/list_documents.py` (`WHERE tenant_id = :tenant_id`)
- [X] T022 [P] [US3] Add a required `tenant_id` parameter to `delete_document(...)` in `src/shiruno/application/delete_document.py` — a document that exists but belongs to a different tenant raises the existing `NotFoundAppError`, same branch as a nonexistent id
- [X] T023 [US3] Wire `current_tenant: Tenant = Depends(get_current_tenant)` into all three routes in `src/shiruno/api/routers/documents.py`, passing `tenant_id=current_tenant.id` through to T020/T021/T022 (depends on T006, T020, T021, T022)
- [X] T024 [US3] Pass `tenant_id=current_tenant.id` into the existing `log_audit_event(...)` calls in `src/shiruno/api/routers/documents.py`; pass `tenant_id=administrator.tenant_id` into the `login_success` `log_audit_event(...)` call in `src/shiruno/api/routers/auth.py` (the login handler has no `current_tenant` dependency — it resolves `administrator` directly, before any token exists) (depends on T007, T023)

**Checkpoint**: `uv run pytest tests/contract/test_documents_auth.py -q` passes independently, proving cross-tenant isolation on real, already-shipped endpoints.

---

## Phase 5: User Story 5 - Everything that already works keeps working (Priority: P1)

**Goal**: Confirm the entire pre-existing behavior surface (public chat,
small talk, rate limiting, budget, existing document auth) is unaffected,
and add the one regression check this feature specifically motivates
(public chat requires no tenant/assistant identifier).

**Independent Test**: quickstart.md §8 — run the pre-existing contract
suites unmodified in intent.

- [X] T025 [US5] Add `tests/contract/test_chat_tenant_unaffected.py`: `POST /api/v1/chat` with a body that includes an unexpected `tenant_id`/`assistant_id` field is rejected the same way any other unknown field already is (`extra="forbid"`, `api/schemas.py::ChatRequest`), and a normal request produces the same `grounded`/`small_talk`/`insufficient_information`/`out_of_scope`/`unavailable` outcomes as before this feature, with no tenant/assistant identifier required (FR-021, FR-022, SC-009)
- [X] T026 [US5] Run `uv run pytest tests/contract tests/unit tests/integration -q` and confirm 100% pass with original assertion intent preserved (quickstart.md §8; depends on T010–T014, T019, T025)

**Checkpoint**: Full pre-existing behavior surface verified unchanged.

---

## Phase 6: User Story 2 - Operator provisions a new customer organization and its administrator safely (Priority: P2)

**Goal**: `create-tenant` and `create-admin --tenant` give an operator a
safe, repeatable, idempotent-or-clearly-failing way to provision tenants
and tenant-owned administrators without touching the database directly.

**Independent Test**: quickstart.md §2 — provision Albertos again (fails
clearly, no duplicate), provision a new tenant and administrators for it,
attempt an administrator for a nonexistent tenant slug (fails clearly).

### Tests for User Story 2

- [X] T027 [US2] Extend `tests/unit/test_cli.py`: `create-tenant` creates a `Tenant` with `status="active"`; a duplicate slug fails with a clear stderr message and `SystemExit(1)`, no duplicate row created; `create-admin` without `--tenant` is a CLI usage error; `create-admin --tenant <missing-slug>` fails clearly with no `Administrator` row created; `create-admin --tenant <existing-slug>` succeeds and the created row's `tenant_id` matches; no password/hash/secret appears in any captured stdout/stderr (contracts/cli-provisioning-contract.md; depends on T009)

### Implementation for User Story 2

- [X] T028 [US2] Add a `create_tenant(name, slug)` function and `create-tenant` subparser (`--name`, `--slug`) to `src/shiruno/cli.py`, mirroring `create_admin`'s existing `IntegrityError` → clear stderr message → `SystemExit(1)` pattern; success prints exactly `Tenant '<name>' (slug: '<slug>') created.`
- [X] T029 [US2] Add a required `--tenant` argument to the `create-admin` subparser in `src/shiruno/cli.py`; look up the `Tenant` by slug before creating the `Administrator`, printing `Error: no tenant with slug '<slug>' exists.` and exiting `1` with no row created if not found; otherwise set `tenant_id` on the created `Administrator` (depends on T028)

**Checkpoint**: `uv run pytest tests/unit/test_cli.py -q` passes independently.

---

## Phase 7: User Story 4 - Unauthenticated or invalid access attempts are consistently rejected (Priority: P2)

**Goal**: Explicit, dedicated proof that every tenant-scoped admin route
introduced or touched by this feature fails closed identically for
missing, invalid, and expired authentication, with no distinguishing
information in the response.

**Independent Test**: quickstart.md §6 — call `GET /api/v1/admin/me` with
no token and with a garbage token; both return the identical generic 401.

- [X] T030 [US4] Add `tests/contract/test_admin_authorization_fail_closed.py`: for `GET /api/v1/admin/me`, `POST /api/v1/documents`, `GET /api/v1/documents`, and `DELETE /api/v1/documents/{id}`, assert missing token, malformed token, and expired token all return the exact same `401` status and `{"detail": "Authentication required."}` body — no route returns a different message or status for any of the three cases (FR-016, FR-018; depends on T017, T023)

**Checkpoint**: `uv run pytest tests/contract/test_admin_authorization_fail_closed.py -q` passes independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T031 [P] Add `tests/integration/test_tenant_migration.py`: run `alembic upgrade head` and `alembic downgrade` against `db-test` via Alembic's `Config`/`command` API, asserting the Albertos tenant exists after upgrade, pre-existing administrators/documents are backfilled to it, and each downgrade step succeeds and is reversible (quickstart.md §1; spec Testing Requirements #18–#20)
- [X] T032 [P] Update `docs/architecture.md`'s "Future: Shiruno Platform / Customer Admin" section — move `Tenant`, tenant-owned `Administrator`, and `GET /api/v1/admin/me` from "future" to the current-architecture description; keep Knowledge Base Administration UI, Conversations & Analytics, and the React admin frontend explicitly marked as still future (spec's Documentation requirement)
- [X] T033 [P] Update `README.md`'s "single-tenant... no `organization_id`/tenant table" line to reflect the new tenant-aware architecture, referencing `docs/architecture.md`
- [X] T034 Walk through `quickstart.md` end to end manually against a local `docker compose` stack and confirm every documented expected outcome
- [X] T035 Run `uv run pytest -q` and confirm 100% pass with no real Ollama, GPU, Anthropic credentials, or external network access used (spec Testing requirements, "must not require" list)
- [X] T036 [P] Add `tests/unit/test_no_startup_tenant_creation.py`: build the app via `create_app(...)` (with fakes) against a fresh test database and assert zero `Tenant` rows exist afterward — proving no tenant is auto-provisioned as a side effect of application startup (FR-006)
- [X] T037 [P] Extend `tests/contract/test_audit_logging.py` to assert `tenant_id` is present and correct in the logged output for `login_success`, `document_upload`, and `document_delete` audit events (FR-025; depends on T007, T024)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies (Setup is a no-op) — BLOCKS every later phase, including the pre-existing suite continuing to run.
- **User Stories (Phase 3–7)**: All depend on Foundational completion. Among themselves:
  - US1 (Phase 3): depends only on Foundational.
  - US3 (Phase 4): depends only on Foundational (touches `test_documents_auth.py` after T014, same file, so run after T014 — already guaranteed by Foundational ordering).
  - US5 (Phase 5): its verification task (T026) depends on Foundational's cleanup (T010–T014) and US3's new tests (T019) having landed, since it runs the whole suite.
  - US2 (Phase 6): depends only on Foundational (T009's `seed_tenant`/`seed_admin_and_token` signature).
  - US4 (Phase 7): depends on US1 (T017) and US3 (T023) existing, since it tests routes they introduce/change.
- **Polish (Phase 8)**: Depends on all prior phases (T035 runs the full suite; T031 depends on T004/T005's migrations existing; T036 depends only on Foundational; T037 depends on T007 and T024).

### Parallel Opportunities

- T001, T006, T007 can start together once nothing blocks them (T006/T007 need T001's `Tenant` import available, but are otherwise independent of each other and of T003–T005).
- T010–T014 are five independent file clusters — all `[P]`, run together once T008 lands.
- Within US3's implementation, T020/T021/T022 are three independent application-layer files — run together, then T023 integrates them.
- T031/T032/T033 in Polish touch unrelated files — run together.

---

## Parallel Example: Foundational Phase

```bash
# After T001, T008 land, launch the four independent seed-fixup clusters together:
Task: "Update Administrator(...) seeding in tests/contract/test_chat*.py cluster 1 (T010)"
Task: "Update Administrator(...) seeding in tests/contract/test_chat*.py cluster 2 (T011)"
Task: "Update Administrator(...) seeding in tests/contract/test_prompt_injection_visitor.py, test_audit_logging.py, test_auth_login.py (T012)"
Task: "Update Administrator(...) seeding in tests/integration/test_database_session_commit.py, test_retrieval_pgvector.py (T013)"
```

---

## Implementation Strategy

### MVP First (Foundational + User Story 1 + User Story 3)

This feature has three P1 stories (US1, US3, US5) because tenant
*resolution* (US1) and tenant *isolation* (US3) are two halves of one
security guarantee — shipping only US1 would prove the server derives
tenant context correctly but not that it's actually enforced against
cross-tenant access, which is the feature's whole point (constitution
Principle II). Treat **Foundational + US1 + US3** as the true MVP:

1. Complete Phase 2: Foundational.
2. Complete Phase 3: User Story 1 — validate independently.
3. Complete Phase 4: User Story 3 — validate independently.
4. **STOP and VALIDATE**: run `test_admin_me.py` and `test_documents_auth.py` together; this is the point at which the constitution's Principle II is actually satisfied end-to-end.
5. Complete Phase 5 (US5) to confirm nothing else broke.
6. Add US2 (CLI) and US4 (explicit fail-closed proof) — both strengthen the MVP but are not required for the core security guarantee to hold.
7. Complete Phase 8 (Polish) last.

### Incremental Delivery

Foundational → US1 → US3 → US5 (checkpoint: feature's core guarantee
proven and nothing regressed) → US2 → US4 → Polish.
