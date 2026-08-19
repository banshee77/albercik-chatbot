# Quickstart: Validating Conversational UX for Public Chat

Validates this feature end-to-end against the running stack. See
`contracts/small-talk-classification-contract.md` for the exact
request/response mapping and `data-model.md` for the classification and
client-side shapes referenced below. Unlike feature 006, most of this
feature's backend behavior (the small-talk short-circuit itself) is fully
verifiable via `curl`/`TestClient` alone, since it lives entirely behind
the existing `POST /api/v1/chat` endpoint; only the avatar/identity/
no-sources widget presentation needs a real browser.

## Prerequisites

```bash
docker compose build app
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/health   # expect 200
```

No new `.env` variable, no new `docker-compose.yml` service, no database
migration, and no new dependency are required for this feature.

## Scenario 1 — Small talk short-circuits before RAG (SC-001, SC-002, FR-001–003)

```bash
curl -s -X POST localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Cześć"}' | python3 -m json.tool
```

Expected: HTTP 200, `"outcome": "small_talk"`, a short friendly greeting in
`answer`, `"sources": []`. Repeat with `"Dzięki!"`, `"Do zobaczenia"`,
`"Jak się masz?"`, `"W czym możesz mi pomóc?"`, and `"Czy jesteś
człowiekiem?"` — each returns `outcome: "small_talk"` with a distinct,
on-topic reply.

Automated equivalent: `tests/contract/test_chat_small_talk.py` asserts
this directly plus `fake_llm_provider.call_count == 0` and
`fake_embedding_provider.embed_calls == []` after each request (research.md
§8) — not observable via `curl` alone, since the fake providers only exist
inside the test process.

## Scenario 2 — A greeting does not swallow a real question (SC-003, FR-004, User Story 2)

```bash
curl -s -X POST localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Cześć, o której są treningi początkujących w Wierzbinie?"}' \
  | python3 -m json.tool
```

Expected: `outcome` is **not** `"small_talk"` — it is `"grounded"` (if the
seeded knowledge base supports this question) or
`"insufficient_information"`, exactly as it would be for the same question
asked without the "Cześć, " prefix. Compare against the same question with
the prefix stripped to confirm identical `outcome`/`answer`.

## Scenario 3 — Existing outcomes and safeguards are unchanged (SC-008, SC-009)

```bash
uv run pytest tests/contract/test_chat.py tests/contract/test_chat_answerability.py \
  tests/contract/test_chat_rate_limit.py tests/contract/test_chat_kill_switch.py \
  tests/contract/test_chat_budget.py tests/contract/test_chat_concurrency.py \
  tests/contract/test_chat_no_client_override.py -v
```

Expected: every pre-existing test in these files still passes, unmodified
— none of them is touched by this feature. `tests/contract/
test_chat_small_talk.py` additionally proves rate limiting and the kill
switch still trigger for a small-talk-shaped request (SC-009), by
pointing the existing rate-limit/kill-switch test patterns at a message
like `"Cześć"` instead of a real question.

## Scenario 4 — No client-side override of classification (testing requirement 17)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Cześć", "intent": "small_talk"}'
```

Expected: `400` (Pydantic `extra="forbid"` rejects the unknown `intent`
field before the request body is ever parsed into classification logic) —
identical to how any other unrecognized field is already rejected today
(see `tests/contract/test_chat_no_client_override.py`).

## Scenario 5 — Public widget hides source labels, shows identity + avatar (manual, requires a browser — SC-004, SC-005, SC-006, User Stories 4–5)

1. Open any public page in a browser with JavaScript enabled.
2. Activate the chat launcher — confirm a small decorative avatar mark is
   visible on the launcher, and the panel header reads "Asystent
   Albertos" (not "Albertos AI" or any "AI chatbot"/"LLM"/"RAG"/"Ollama"
   wording).
3. Ask a question known to be answerable from seeded content — confirm the
   answer appears with **no** "Źródła: ..." line or any filename/chunk
   identifier anywhere in the panel, and the same decorative avatar
   appears next to the assistant's reply bubble.
4. Open browser devtools → Network tab, inspect the raw `POST /api/v1/chat`
   response body for the same question — confirm `sources` is still
   present and populated there, proving the backend contract is untouched
   and only the widget's rendering changed.
5. Ask "Czy jesteś człowiekiem?" — confirm the reply clearly states it is
   a virtual Albertos assistant and does not claim to be human, with no
   visible loading delay (no network request needed for this reply —
   confirm via devtools Network tab that no new request fires beyond the
   one `POST /api/v1/chat` call itself).
6. In devtools, block the avatar SVG request (Network tab → right-click →
   "Block request URL", or rename/remove the file temporarily) and reload
   — confirm the launcher and panel still render and function correctly,
   with no broken-image icon, only a plain background where the avatar
   would have been.
7. Use a screen reader (or devtools' Accessibility Tree inspector) to
   confirm the avatar element is not separately announced (decorative,
   `aria-hidden="true"`), while the panel title "Asystent Albertos" is
   still announced normally.

## Scenario 6 — Transcript persistence unchanged, including small talk (SC-007, FR-015/016)

1. Open the panel, send a greeting ("Cześć") and a real question in the
   same session.
2. Navigate to a different public page, then reopen the panel — both the
   small-talk exchange and the real-question exchange are still present,
   in order.
3. Close the browser tab and reopen the site fresh — history is gone
   (session storage cleared), and the panel starts closed, exactly as in
   feature 006.

## Scenario 7 — Automated suite (no browser, no live LLM/GPU — SC-008)

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
docker compose config
```

Expected: the entire pre-existing suite still passes unmodified, alongside
this feature's new classifier unit tests, small-talk contract tests, and
extended widget/client-script tests — all using the project's existing
`TestClient`/fake-provider conventions, with zero dependency on a live
Ollama/Anthropic provider, a GPU, or browser automation.
