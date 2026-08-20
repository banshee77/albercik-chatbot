# Quickstart: Conversations UI

**Feature**: `015-conversations-ui` | **Spec**: [spec.md](./spec.md)

Manual/live validation against the real local stack. Automated coverage
(component tests, backend regression suite) lives in the test suite per
research.md R12 and does not require any of the steps below — this guide
proves the feature end-to-end for a human, not the automated gate.

No manual SQL is used anywhere below — every verification conversation is
generated through the existing public `/api/v1/chat` endpoint, exactly as
`specs/011-conversations-analytics/quickstart.md` already does.

## Prerequisites

- Backend running with CORS enabled for the admin frontend's origin
  (`CORS_ALLOWED_ORIGINS=http://localhost:5173`), identical prerequisite to
  Feature 013's and Feature 014's own quickstarts.
- `PUBLIC_CHAT_TENANT_SLUG` (default `albertos`) names the tenant that will
  receive every conversation generated below — log in to Admin as an
  administrator of **that same tenant**, or every conversation you generate
  will belong to a tenant you can't see from the account you log in with
  (this is expected tenant isolation, not a bug — spec.md Edge Cases).
- A tenant administrator account for that tenant exists (Feature 013's
  quickstart covers creating one if none does):
  ```sh
  uv run python -m shiruno.cli create-admin --tenant albertos --username admin --password <a-real-password>
  ```

## 1. Generate verification conversations

Generate at least one of each outcome so every detail-presentation branch
(US2, §14–17) is checkable. `small_talk` and `out_of_scope` occur
naturally from question content; `grounded` requires the tenant's
knowledge base to have at least one ready document (Feature 014); a real
`unavailable` case is optional (see step 9 note).

```sh
# Answered (grounded) — needs a matching, already-ready knowledge document
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Jakie są godziny otwarcia?"}'

# Knowledge gap (insufficient_information) — ask something the knowledge base can't answer
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is the airspeed velocity of an unladen swallow?"}'

# Small talk
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Hello!"}'

# Out of scope
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Write me a Python quicksort implementation."}'
```

**Expected**: each call returns a normal `ChatResponse` — this feature
changes nothing about `/api/v1/chat` (FR-050).

## 2. Start the Admin frontend

```sh
cd apps/admin
npm install   # first time only
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`).

## 3. Log in and open Conversations

Log in with the administrator credentials from Prerequisites, then select
"Conversations" from primary navigation.

**Expected**: `/app/conversations` no longer shows the Feature 013
placeholder text ("Conversation history is coming soon.") — an intentional
loading state appears briefly, then the four conversations from step 1
appear, newest first, each with its question and a human-readable outcome
label — never a raw enum string like `insufficient_information` (spec US1,
FR-001, FR-007).

## 4. Search

Type a distinctive word from one question (e.g. `swallow`) into the search
field and submit.

**Expected**: the list re-queries the backend and shows only the matching
conversation. Clear the search field and resubmit; the full list of four
returns (spec US3, FR-010–FR-012).

## 5. Outcome filter

Select "Knowledge gap" from the outcome filter.

**Expected**: only the `insufficient_information` conversation from step 1
is shown (spec US3, FR-013).

## 6. Date range

Set "From" to today's date and "To" to today's date.

**Expected**: all four conversations remain visible (they were all created
today). Set "From" to a date in the future; the list shows the
filtered-no-results state ("No conversations match the selected filters"),
distinct from a "no conversations yet" state, with a visible way to clear
filters (spec US3, FR-015, FR-021).

## 7. Pagination

If a tenant already has more than one page of conversations (repeat step 1
enough times, or use a tenant with pre-existing history), select "Next".

**Expected**: the next page loads, "Previous" becomes enabled, and
"Previous" returns to the first page. On the first page, "Previous" is
disabled; on the last page, "Next" is disabled (spec US4, FR-018–FR-020).
With only four conversations and the default page size, this step may show
both controls disabled on a single page — that is the correct outcome, not
a bug.

## 8. Grounded detail

Select the "Answered" conversation from step 1.

**Expected**: a detail panel opens below the list (the list stays visible)
showing the question and answer clearly separated, the outcome, and a
"Sources" section listing the knowledge document label(s) that grounded
it — never reconstructed from the current Knowledge page state (spec US2,
FR-024, FR-028). The compact metadata area shows latency, provider, model,
and token counts where present, without dominating the question/answer
(FR-035). Expand "Technical details" and confirm the request ID is
present and copyable (FR-038).

## 9. Knowledge-gap, small-talk, and out-of-scope detail

Select each of the other three conversations from step 1 in turn.

**Expected**:
- **Knowledge gap**: a "Knowledge gap" state, not phrased as a wrong
  answer, with no fabricated sources (spec US2, FR-031).
- **Small talk**: displays normally with no fabricated provider/model/token
  values — their absence is shown naturally (FR-034, FR-036).
- **Out of scope**: a neutral "Out of scope" label, not phrased as a
  failure (FR-032).

A real `unavailable` conversation is optional and harder to force safely
(it requires the kill switch, budget limit, or a provider error) — if one
already exists in this tenant's history from prior testing, select it and
confirm a safe "Assistant unavailable" state with no raw provider
exception text (FR-033); otherwise this sub-step may be skipped, since it
is already covered by the automated test suite (spec Testing Requirements
#28).

## 10. Confirm no tenant-selection control exists

Inspect the Conversations page and its detail panel.

**Expected**: no dropdown, tenant ID field, or similar control anywhere
that would let this administrator choose a different tenant's
conversations (spec FR-041).

## 11. Close detail and confirm list state survives

With a search term, an outcome filter, and a page other than the first (if
reachable) all active, open a conversation's detail, then close it.

**Expected**: the search term, outcome filter, date range, and current
page are exactly as they were before detail was opened (spec §23, FR-027).

## 12. Detail failure is isolated from the list

With the browser's network tools, block the
`GET /api/v1/admin/conversations/{id}` request for one selection (or
select a conversation and immediately trigger a backend restart to force a
transient failure).

**Expected**: a safe, detail-level error appears in the panel; the
underlying list remains fully visible and usable (spec US2, FR-026).

## 13. Log out and re-check protection

Log out, then navigate directly to `/app/conversations` again.

**Expected**: redirected to `/login` — no conversation content shown after
logout (reusing Feature 013's existing session behavior, spec US5,
FR-042–FR-043).

## 14. Narrower viewport check

Using browser dev-tools device emulation, resize to a common tablet width
(~768px) and repeat steps 3, 4, and 8.

**Expected**: the list and detail panel remain usable (via stacking,
responsive layout, or horizontal scroll) with every control reachable — no
layout overlap or clipped content (spec FR-048).

## Cleanup

```sh
# apps/admin/: Ctrl-C the `npm run dev` process
```

No real LLM call is strictly required beyond what `/api/v1/chat` already
uses per the deployment's configured `LLM_PROVIDER` (default `ollama`,
local) — Conversations itself performs no LLM/embedding call of its own
and never invokes Phoenix or any observability path (FR-050).
