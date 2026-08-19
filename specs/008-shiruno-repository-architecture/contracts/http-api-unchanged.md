# Contract: Public & Admin HTTP API (frozen, unchanged)

This feature does not add, remove, or modify any HTTP endpoint, request
schema, response schema, status code, or outcome value. It is listed here
as an explicit contract precisely so the "unchanged" claim is checkable.

## Endpoints in scope (must behave identically before/after this feature)

| Endpoint | Contract source | Notes |
|---|---|---|
| `POST /api/v1/chat` | `specs/001-albertos-rag-chatbot/`, `specs/004-rag-answerability-and-ollama-performance/`, `specs/007-conversational-chat-ux/` | Request/response shape, outcome enum (`grounded`, `small_talk`, `insufficient_information`, `out_of_scope`, `unavailable`), source metadata, source hiding in the public widget |
| `POST /api/v1/auth/login` (or equivalent admin auth route) | `specs/001-albertos-rag-chatbot/` | JWT issuance, credential validation |
| Document management (`upload`/`list`/`delete`) | `specs/001-albertos-rag-chatbot/` | Admin-only, RBAC-enforced |
| `GET /health` | `specs/001-albertos-rag-chatbot/` | Liveness |
| Public website routes (`/`, `/karate-do`, `/o-klubie`, `/trenerzy`, `/sekcje`, `/grafik`, `/aktualnosci`, `/kontakt`, `/glosariusz` if present) | `specs/005-public-club-website/` | Rendered HTML, unauthenticated |
| Chat widget static assets (`/static/site/...`) | `specs/006-public-chat-widget/`, `specs/007-conversational-chat-ux/` | Served unchanged; only their on-disk source path may move within the package (see `runtime-paths.md`) |

## Verification

Covered by the existing automated test suite (contract + integration tests
under `tests/contract/`, `tests/integration/`) run unmodified in assertion
semantics against the refactored codebase — see `quickstart.md`.

## What is explicitly allowed to change

- The Python import path used internally to reach the code implementing
  these routes (`albercik_chatbot.*` → `shiruno.*`).
- The on-disk source location of static/template assets, as long as the
  URL paths they are served at (`/static/site/...`) do not change.

Nothing else.
