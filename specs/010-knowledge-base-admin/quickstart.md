# Quickstart: Knowledge Base Administration

Validation scenarios proving this feature works end-to-end. Assumes the
local Docker Compose stack (`shiruno` project, per the Feature 009
infra-rename) is already up and migrated. No real Ollama, GPU, or
Anthropic credentials are required for anything below except the
grounded-chat sample at the end, which uses whatever `LLM_PROVIDER` is
already configured (default `ollama`, local).

## Prerequisites

```bash
docker compose up -d
uv run alembic upgrade head
```

## 1. Migration

```bash
uv run alembic upgrade head
```

**Expected**: succeeds; every existing `knowledge_documents` row now has
a non-null `updated_at`, `indexed_at` set for rows that were already
`ready`, `safe_error_message` and `replaces_document_id` both `NULL`.

## 2. Provision an administrator (if not already done)

```bash
uv run python -m shiruno.cli create-admin --tenant albertos --username admin
```

## 3. Empty-state health and list

```bash
TOKEN=<login token>
curl -s http://localhost:8000/api/v1/documents/health -H "Authorization: Bearer $TOKEN"
```

**Expected** (on a tenant with no documents yet): `200`,
`{"documents": {"total": 0, "ready": 0, "processing": 0, "failed": 0},
"chunks": 0, "ready_for_chat": false, "last_indexed_at": null}` — no
error (FR-030).

## 4. Upload, list, detail, health

```bash
curl -s -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" -F "file=@godziny.txt"
# note the returned "id" as $DOC_ID

curl -s http://localhost:8000/api/v1/documents -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/v1/documents/$DOC_ID" -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/documents/health -H "Authorization: Bearer $TOKEN"
```

**Expected**: upload returns `201` with `status: "ready"`; list and
detail both show the document with `content_type: "text/plain"`,
non-null `updated_at`/`indexed_at`, `error_message: null`; health now
shows `documents.ready: 1`, `ready_for_chat: true`.

## 5. Safe replace — old knowledge keeps working until new knowledge is ready

```bash
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/replace" \
  -H "Authorization: Bearer $TOKEN" -F "file=@godziny-nowe.txt"
# note the returned "id" as $NEW_DOC_ID — different from $DOC_ID
```

**Expected**: `201`, `status: "ready"`. Then:

*Concurrent-replace safety* (exactly one of two simultaneous replace
requests for the same document may win, per research.md §3's row-level
lock) is proven by the automated integration test
(`tests/integration/test_replace_concurrency.py`), not by this manual
guide — reliably driving two requests into the same lock window from a
shell script isn't a meaningful reproduction of the guarantee. Run it
directly: `uv run pytest tests/integration/test_replace_concurrency.py -q`.

```bash
curl -s http://localhost:8000/api/v1/documents -H "Authorization: Bearer $TOKEN"
```

**Expected**: the list now shows `$NEW_DOC_ID` (not `$DOC_ID`) —
`$DOC_ID` has been retired. A `POST /api/v1/chat` question the old
content would have answered now answers from the new content instead.

## 6. Failed replace leaves the original untouched

Using a fake-provider test (see `tests/contract/test_documents_replace.py`
for the automated version) or an intentionally invalid replacement file
against the live stack:

**Expected**: the replacement attempt returns `201` with `status:
"failed"` and a safe `error_message`; `GET /documents` still shows the
**original** `$DOC_ID` as `ready`, unaffected; a relevant chat question
still answers from the original content.

## 7. Re-index

```bash
curl -s -X POST "http://localhost:8000/api/v1/documents/$NEW_DOC_ID/reindex" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: `200`, same `id` as `$NEW_DOC_ID`, `status: "ready"`,
`indexed_at` updated to a later timestamp, `error_message: null`.

## 8. Delete

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
  "http://localhost:8000/api/v1/documents/$NEW_DOC_ID" \
  -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/documents -H "Authorization: Bearer $TOKEN"
```

**Expected**: `204`; the document no longer appears in the list or
contributes to chat answers.

## 9. Cross-tenant isolation

```bash
uv run python -m shiruno.cli create-tenant --name "Acme Test Co" --slug acme-test
uv run python -m shiruno.cli create-admin --tenant acme-test --username acme-admin
ACME_TOKEN=<login as acme-admin>

curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000/api/v1/documents/$DOC_ID" \
  -H "Authorization: Bearer $ACME_TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  "http://localhost:8000/api/v1/documents/$DOC_ID/replace" \
  -H "Authorization: Bearer $ACME_TOKEN" -F "file=@x.txt"
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  "http://localhost:8000/api/v1/documents/$DOC_ID/reindex" \
  -H "Authorization: Bearer $ACME_TOKEN"
curl -s http://localhost:8000/api/v1/documents/health -H "Authorization: Bearer $ACME_TOKEN"
```

**Expected**: all four `404` except health, which returns `200` showing
only Acme's own (empty) counts — never Albertos's data.

## 10. Existing behavior unaffected

```bash
uv run pytest tests/contract/test_chat.py tests/contract/test_chat_small_talk.py \
  tests/contract/test_documents_auth.py tests/contract/test_documents_upload.py \
  tests/contract/test_admin_me.py -q
```

**Expected**: all pass, unmodified in intent.

## 11. Full suite

```bash
uv run pytest -q
```

**Expected**: 100% pass, no real Ollama/GPU/Anthropic/network access
used (`tests/fakes/`, real Postgres+`pgvector` via `db-test`).
