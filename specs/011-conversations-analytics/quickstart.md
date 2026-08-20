# Quickstart: Conversations & Analytics

Validation scenarios proving this feature works end-to-end. Assumes the
local Docker Compose stack (`shiruno` project) is already up and migrated.
No real Ollama, GPU, or Anthropic credentials are required for anything
below except the grounded-chat sample, which uses whatever `LLM_PROVIDER`
is already configured (default `ollama`, local).

## Prerequisites

```bash
docker compose up -d
uv run alembic upgrade head
```

## 1. Migration

```bash
uv run alembic upgrade head
```

**Expected**: succeeds; `conversation_records` exists, empty (no
historical rows — data-model.md).

## 2. Provision an administrator (if not already done)

```bash
uv run python -m shiruno.cli create-admin --tenant albertos --username admin
```

## 3. Generate a conversation, then browse it

```bash
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Jakie są godziny otwarcia?"}'

TOKEN=<login token>

curl -s http://localhost:8000/api/v1/admin/conversations -H "Authorization: Bearer $TOKEN"
```

**Expected**: the chat call returns a normal `ChatResponse` exactly as
before this feature — no new required field, same shape. The list call
returns `200` with one item (assuming the tenant slug matches
`PUBLIC_CHAT_TENANT_SLUG`, default `"albertos"`) showing the question,
outcome, timestamp, and latency.

## 4. Conversation detail

```bash
CONVERSATION_ID=<id from step 3's list response>

curl -s "http://localhost:8000/api/v1/admin/conversations/$CONVERSATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: `200` with the full question/answer/outcome, latency, and —
if the outcome was `grounded` — the source documents that supported it.

## 5. Cross-tenant isolation

```bash
uv run python -m shiruno.cli create-tenant --name "Acme Test Co" --slug acme-test
uv run python -m shiruno.cli create-admin --tenant acme-test --username acme-admin
ACME_TOKEN=<login as acme-admin>

curl -s http://localhost:8000/api/v1/admin/conversations -H "Authorization: Bearer $ACME_TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' \
  "http://localhost:8000/api/v1/admin/conversations/$CONVERSATION_ID" \
  -H "Authorization: Bearer $ACME_TOKEN"
curl -s http://localhost:8000/api/v1/admin/analytics/summary -H "Authorization: Bearer $ACME_TOKEN"
```

**Expected**: Acme's conversation list is empty; the cross-tenant detail
lookup returns `404` (identical to a nonexistent id); Acme's analytics
summary shows all-zero counts — never Albertos's data.

## 6. Analytics summary, knowledge gaps, common questions

```bash
curl -s http://localhost:8000/api/v1/admin/analytics/summary -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/admin/analytics/knowledge-gaps -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/admin/analytics/questions -H "Authorization: Bearer $TOKEN"
```

**Expected**: summary reflects the conversation(s) generated above; both
grouping endpoints return `200` with either an empty `items` list (if no
insufficient-information questions were asked yet) or ranked groups.

## 7. Recording never breaks the public chat response

Covered by an automated test
(`tests/contract/test_chat_conversation_recording.py`), not this manual
guide — reliably forcing a mid-request database failure from a shell
script isn't a meaningful reproduction of the guarantee. Run it directly:

```bash
uv run pytest tests/contract/test_chat_conversation_recording.py -q
```

**Expected**: a scenario where the `ConversationRecord` insert is forced to
fail still returns a normal, successful `ChatResponse` to the caller — only
that write's `SAVEPOINT` rolls back, the outer request transaction (and any
`UsageRecord` rows already flushed in it) continues and commits normally,
and the failure is only visible in the server-side log (no question/answer
content in it), never in the HTTP response.

## 8. Public reference tenant resolution is fail-closed, and never affects `/chat`

Also covered by automated tests
(`tests/unit/test_resolve_public_tenant.py` for the resolution function in
isolation; `tests/contract/test_chat_conversation_recording.py` for the
end-to-end guarantee), not manual steps — the point being verified is
specifically that misconfiguration is invisible to the visitor:

```bash
uv run pytest tests/unit/test_resolve_public_tenant.py \
  tests/contract/test_chat_conversation_recording.py -q
```

**Expected**: with `PUBLIC_CHAT_TENANT_SLUG` pointed at a slug that does
not exist, or at a tenant whose `status` is `inactive`, `POST /api/v1/chat`
still returns its normal outcome and answer, identical to a correctly
configured deployment — only no `ConversationRecord` is written for that
request, and the reason is visible solely in the server-side log. No
fallback tenant is ever selected, and no `Tenant` row is ever created as a
side effect.

## 9. Existing behavior unaffected

```bash
uv run pytest tests/contract/test_chat.py tests/contract/test_chat_small_talk.py \
  tests/contract/test_documents_auth.py tests/contract/test_admin_me.py -q
```

**Expected**: all pass, unmodified in intent.

## 10. Full suite

```bash
uv run pytest -q
```

**Expected**: 100% pass, no real Ollama/GPU/Anthropic/network access used
(`tests/fakes/`, real Postgres via `db-test`).
