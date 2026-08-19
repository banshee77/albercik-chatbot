# Quickstart: Admin Platform Foundation & Tenant Boundary

Validation scenarios proving this feature works end-to-end. Assumes the
existing local dev setup (`docker-compose.yml`, `db`/`db-test`/`app`
services) already works per the root `README.md`. No real Ollama, GPU, or
Anthropic credentials are required for anything below.

## Prerequisites

```bash
docker compose up -d db db-test
uv run alembic upgrade head
```

## 1. Migration + bootstrap

```bash
uv run alembic upgrade head
```

**Expected**: succeeds; a `tenants` table exists with exactly one row
(`slug="albertos"`, `status="active"`); every pre-existing `administrators`
row now has a non-null `tenant_id` pointing at that row; every pre-existing
`knowledge_documents` row likewise. See data-model.md's Migration plan.

```bash
uv run alembic downgrade -1   # reverts knowledge_documents.tenant_id
uv run alembic downgrade -1   # reverts tenants + administrators.tenant_id
uv run alembic upgrade head   # back to head, for the rest of this guide
```

**Expected**: each downgrade succeeds without error; re-running `upgrade
head` succeeds and reaches the same end state.

## 2. Provision a tenant and an administrator

```bash
uv run python -m shiruno.cli create-tenant --name "Albertos" --slug albertos
```

**Expected**: since the migration already bootstrapped Albertos, this
fails clearly (`Error: a tenant with slug 'albertos' already exists.`) —
proving the mechanism does not silently duplicate (FR-004).

```bash
uv run python -m shiruno.cli create-tenant --name "Acme Test Co" --slug acme-test
uv run python -m shiruno.cli create-admin --tenant albertos --username admin
uv run python -m shiruno.cli create-admin --tenant acme-test --username acme-admin
```

**Expected**: both administrators are created, associated with the
correct tenant. See contracts/cli-provisioning-contract.md.

```bash
uv run python -m shiruno.cli create-admin --tenant no-such-tenant --username x
```

**Expected**: fails clearly (`Error: no tenant with slug 'no-such-tenant'
exists.`), no administrator row created (FR-009).

## 3. Authenticate and resolve tenant context

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "<the password set above>"}'
```

**Expected**: `200`, unchanged response shape (`access_token`,
`token_type`, `expires_in`) — see contracts/admin-api-delta.md.

```bash
TOKEN=<access_token from above>
curl -s http://localhost:8000/api/v1/admin/me -H "Authorization: Bearer $TOKEN"
```

**Expected**: `200`, body exactly:

```json
{"administrator": {"id": "...", "username": "admin"},
 "tenant": {"id": "...", "name": "Albertos", "slug": "albertos"}}
```

Repeat with the `acme-admin` token — expect `tenant.slug == "acme-test"`,
never `"albertos"`.

## 4. Client cannot override tenant context

```bash
curl -s http://localhost:8000/api/v1/admin/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-Id: <acme tenant id>"
curl -s "http://localhost:8000/api/v1/admin/me?tenant_id=<acme tenant id>" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: both return the Albertos admin's own tenant, identical to
step 3 — the header/query value has no effect (FR-013).

## 5. Cross-tenant document isolation

```bash
# As the Albertos admin, upload a document.
curl -s -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" -F "file=@README.md"
# note the returned "id" as $DOC_ID

# As the Acme admin, try to see/delete it.
ACME_TOKEN=<login as acme-admin>
curl -s http://localhost:8000/api/v1/documents -H "Authorization: Bearer $ACME_TOKEN"
curl -s -X DELETE "http://localhost:8000/api/v1/documents/$DOC_ID" \
  -H "Authorization: Bearer $ACME_TOKEN" -o /dev/null -w '%{http_code}\n'
```

**Expected**: the list from the Acme admin does not include `$DOC_ID`; the
delete attempt returns `404`, identical to deleting a random nonexistent
id (FR-018, FR-024).

## 6. Missing / invalid authentication

```bash
curl -s http://localhost:8000/api/v1/admin/me -o /dev/null -w '%{http_code}\n'
curl -s http://localhost:8000/api/v1/admin/me -H 'Authorization: Bearer not-a-real-token' \
  -o /dev/null -w '%{http_code}\n'
```

**Expected**: both `401`, identical generic body (FR-016).

## 7. Deactivated tenant fails closed (test-only — no CLI/API path exists)

Exercised in the automated suite only (Clarifications, 2026-08-19): a test
sets a tenant's `status` directly to `inactive` via the test database
session, then confirms a previously-valid token for that tenant's
administrator now receives `401` from `/api/v1/admin/me` and from the
document endpoints (FR-017).

## 8. Existing behavior unaffected

```bash
uv run pytest tests/contract/test_chat.py tests/contract/test_chat_small_talk.py \
  tests/contract/test_chat_rate_limit.py tests/contract/test_chat_budget.py \
  tests/contract/test_documents_auth.py tests/contract/test_documents_lifecycle.py -q
```

**Expected**: all pass, unmodified in intent, exactly as before this
feature (User Story 5, FR-021–FR-023, SC-002, SC-009).

## 9. Full suite

```bash
uv run pytest -q
```

**Expected**: 100% pass, no real Ollama/GPU/Anthropic/network access used
(`tests/fakes/`, `tests/conftest.py`'s `db-test` Postgres+pgvector
service).
