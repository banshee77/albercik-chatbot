# Quickstart: Validating the Public Chat Widget

Validates this feature end-to-end against the running stack. See
`contracts/chat-widget-client-contract.md` for the exact request/response
mapping and `data-model.md` for the client-side session shape referenced
below. Unlike feature 005's pages, most of this feature's actual behavior
requires JavaScript execution (a real browser), since the widget's whole
point is client-side interactivity — the automated test suite (Scenario 6)
covers what's verifiable via `curl`/`TestClient` alone.

## Prerequisites

```bash
docker compose build app
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/health   # expect 200
```

No new `.env` variables, no new `docker-compose.yml` service, no database
migration, and no new dependency are required for this feature.

## Scenario 1 — Launcher present on every public page (SC-002, FR-001, FR-002)

```bash
for path in / /karate-do /o-klubie /trenerzy /sekcje /grafik /aktualnosci /kontakt; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "localhost:8000${path}")
  has_launcher=$(curl -s "localhost:8000${path}" | grep -c 'id="chat-launcher"')
  echo "${path} -> ${code}, launcher present: ${has_launcher}"
done
```

Expected: every path returns `200` and contains exactly one
`id="chat-launcher"` element, with an `aria-label` naming "Zapytaj
Albertos" / "otwórz czat".

## Scenario 2 — Panel skeleton and scope notice (FR-004, FR-005)

```bash
curl -s localhost:8000/ | grep -o 'id="chat-panel"'
curl -s localhost:8000/ | grep -o 'role="dialog"'
curl -s localhost:8000/ | grep -o 'Zapytaj o treningi, grafik, trenerów, sekcje i informacje o klubie.'
```

Expected: the panel skeleton (title, scope notice, message log, form,
send/close controls) is present in every page's server-rendered HTML,
identically, since it lives in the shared `base.html` layout.

## Scenario 3 — `chat.js` is referenced and self-contained (FR-006, negative contract)

```bash
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/static/site/js/chat.js   # expect 200
curl -s localhost:8000/static/site/js/chat.js | grep -c '/api/v1/chat'            # expect >= 1
curl -s localhost:8000/static/site/js/chat.js | grep -c '/api/'                    # expect == the count above (no other API path)
curl -s localhost:8000/static/site/js/chat.js | grep -c 'innerHTML'                # expect 0
```

Automated equivalent:
`tests/unit/test_chat_widget_client_script.py` asserts this directly
against the source file rather than relying on manual inspection.

## Scenario 4 — Conversation flow (manual, requires a browser — User Stories 1–3)

1. Open any public page in a browser with JavaScript enabled.
2. Activate the "Zapytaj Albertos" launcher (mouse or keyboard) — the panel
   opens, focus moves into it.
3. Ask a question known to be answerable from seeded content (see
   `specs/001-albertos-rag-chatbot`/`tests/contract/test_chat.py` for
   examples of grounded questions against a seeded knowledge base) —
   expect the answer plus a compact `"Źródła: ..."` line.
4. Ask an off-topic question (e.g. "Napisz mi wiersz o wiośnie.") — expect
   the friendly out-of-scope reminder, no sources line.
5. Navigate to a different public page — the panel starts closed again,
   but reopening it shows the same conversation history from steps 3–4
   (Clarification, 2026-08-19).
6. Close the tab and reopen the site fresh — history is gone (session
   storage cleared).

## Scenario 5 — Error and loading states (manual or via a network-throttling
browser devtools profile — User Story 3, FR-016–020)

1. Submit a question and observe a visible loading state; click send again
   immediately — confirm only one network request fires (devtools Network
   tab).
2. With devtools "Offline" mode, submit a question — expect a friendly
   generic error, not a stuck spinner or a browser-native failure page.
3. Confirm the close button remains clickable throughout steps 1–2.

## Scenario 6 — Automated suite (no browser, no live LLM/GPU — SC-008)

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
docker compose config
```

Expected: the entire pre-existing suite still passes unmodified (this
feature touches no file any existing test exercises), alongside this
feature's new markup-contract and client-script static-source tests — all
using the project's existing `TestClient`/fake-provider conventions, with
zero dependency on a live Ollama/Anthropic provider, a GPU, or browser
automation.

## Scenario 7 — JavaScript-disabled non-regression (SC-005, User Story 5)

```bash
for path in / /karate-do /o-klubie /trenerzy /sekcje /grafik /aktualnosci /kontakt; do
  curl -s -o /dev/null -w "${path}: %{http_code}\n" "localhost:8000${path}"
done
```

Since `curl` never executes JavaScript, every one of the above requests
already *is* the no-JS scenario for these pages' own content and
navigation. For a visual confirmation, disable JavaScript in a browser and
confirm the launcher is entirely absent from the rendered page (not a
visibly present but non-functional button) — the `.js`-class CSS gating
means the server sends the same markup either way, but the browser only
reveals it once its own inline script has run.
