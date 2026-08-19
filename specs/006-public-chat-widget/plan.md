# Implementation Plan: Public Website Chat Widget

**Branch**: `006-public-chat-widget` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-public-chat-widget/spec.md`

## Summary

Add a persistent "Zapytaj Albertos" chat launcher and panel to the existing
public website, entirely within the existing `public_site` package,
reusing the existing `POST /api/v1/chat` endpoint exactly as-is with no
backend changes of any kind. The panel chassis (title, scope notice,
message log, input, send/close controls) is static Jinja2 markup added
once to the shared `base.html` layout (present identically on all 8 public
pages by construction), hidden without JavaScript via the same `.js`-class
CSS-gating mechanism feature 005 already established for the mobile nav
toggle. A new vanilla-JS module, `chat.js`, handles all behavior: open/
close with focus management and an `Escape` handler, submitting each
question independently to `/api/v1/chat`, mapping its four outcomes (plus
429/503/network/malformed-response) to friendly Polish messages, rendering
answer text and deduplicated source labels via `textContent` only (never
`innerHTML`), and persisting the conversation transcript — but not the
panel's open/closed state — in `sessionStorage` so it survives navigation
between pages within the same tab. This feature adds **zero new
dependencies and zero new backend endpoints or Python modules** — the
entire change surface is two edited existing files (`base.html`,
`site.css`) plus one new static JS file and its tests.

## Technical Context

**Language/Version**: Python 3.14 (server-rendered chassis, unchanged);
vanilla ES2017+ JavaScript, no transpilation (client behavior) — both
already the project's established stack, no new language/runtime.

**Primary Dependencies**: None new. Reuses FastAPI, Jinja2, and Starlette
`StaticFiles` exactly as already wired by feature 005's `main.py` changes
— this feature adds no line to `pyproject.toml`/`uv.lock`.

**Storage**: N/A server-side (no new table, no migration). Client-side
only: `window.sessionStorage`, holding the conversation transcript as a
single JSON-encoded array (data-model.md).

**Testing**: pytest + FastAPI `TestClient` (existing, for markup/
accessibility-attribute contract tests) plus plain-text static-source
assertions against the shipped `chat.js` file (existing `pytest`, no new
test framework, no Node.js runner, no browser-automation tool) — see
research.md §8.

**Target Platform**: Linux server, same Docker container/image as the
existing app (no new service, no new container).

**Project Type**: Single project (web service) — this feature is a
client-only addition inside the already-existing `public_site` in-process
module; it does not touch `api/`, `application/`, `domain/`, `providers/`,
or `persistence/`.

**Performance Goals**: Panel open/close is a pure client-side DOM/CSS
toggle with no network call — perceptibly instant (well under 100ms).
Actual question-answer latency is entirely governed by the existing,
untouched `/api/v1/chat` pipeline and is out of this feature's control or
scope to re-measure.

**Constraints**: MUST NOT modify `api/routers/chat.py`, `api/schemas.py`,
`application/ask_question.py`, or any RAG/retrieval/provider/rate-limit/
budget/prompt-injection/admin-auth code (spec FR-023, explicit user
instruction). MUST NOT introduce a second chat endpoint, WebSocket, or SSE
stream (spec FR-006; Out of Scope). MUST NOT add a new frontend framework,
build tool, or dependency (spec Implementation constraints; Constitution
Principle XIII/XIV). MUST leave every existing automated test passing
unmodified (spec SC-008, mirroring feature 005's FR-037/038 precedent).

**Scale/Scope**: 1 new static JS file (`chat.js`, on the order of a few
hundred lines given research.md's decisions: fetch/outcome mapping, focus
trap, sessionStorage read/write, dedup logic); 2 existing files edited
(`base.html` — one launcher button + one panel skeleton block; `site.css`
— one new design section for launcher/panel/message-bubble/status styles
plus one small-viewport media-query addition); 2 new test files. Zero new
Python modules, zero new routes, zero new dependencies.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicability | Assessment |
|---|---|---|
| I. Security by Default | Applies | LLM-derived `answer`/source `label` text is treated as untrusted and inserted via `textContent` only, never `innerHTML` — enforced structurally (research.md §2) and proven by a static-source test (research.md §8), not by convention alone. No secrets involved. **Pass.** |
| II. Tenancy Posture | N/A | No tenant concept touched. |
| III. Secure RAG | N/A | This feature never calls retrieval/the LLM directly — it only proxies a question to the existing, untouched endpoint that already owns that boundary. |
| IV. Secure Document Ingestion | N/A | No uploads in this feature. |
| V. LLM Provider Neutrality | N/A | No new LLM call path is introduced; the existing endpoint (already behind the Principle V interface) is reused unmodified. |
| VI. Embedding Provider Neutrality | N/A | Same reasoning as V. |
| VII. Cloud/Provider Neutrality | Applies | No cloud-specific service introduced; static HTML/CSS/JS served from the existing container. **Pass.** |
| VIII. API Security | Applies | No new endpoint is added (FR-006) — the one existing input-validation/authz boundary (`/api/v1/chat`) is unchanged. The widget's own request construction is additionally, redundantly disciplined to send only `question` (belt-and-suspenders on top of, not instead of, the server's `extra="forbid"`). **Pass.** |
| IX. Privacy and Logging | Applies | No new server-side logging. No PII is collected by this feature (the same public, unauthenticated question flow as before); `sessionStorage` content never leaves the browser except as the same `question` string the existing endpoint already receives. **Pass.** |
| X. Cost Safety (NON-NEGOTIABLE) | Applies | This feature cannot create new cost exposure: no new endpoint, no new call path to a paid provider, and the client-side request-construction discipline (research.md §1, contracts doc) cannot add fields the server doesn't already reject via `extra="forbid"`. Existing rate limiting/budget/kill-switch controls apply identically to widget-originated requests as to any other caller of the same endpoint, unchanged. **Pass — no new mechanism needed, none added.** |
| XI. Testing Discipline (NON-NEGOTIABLE) | Applies (proportionately) | New markup-contract tests (launcher/panel present and accessible on every page) and new client-script static-source tests (only `/api/v1/chat` referenced, only `question` sent, no `innerHTML`) per research.md §8 — all via the existing pytest/`TestClient` stack, no live provider/GPU/browser-automation dependency (spec SC-008). The full existing `test_chat*.py` suite is re-run unmodified as the non-regression proof, since no file it exercises is touched. **Pass.** |
| XII. Engineering Quality | Applies | `chat.js` follows the same IIFE, no-global-leak, explicit-function style already established by `site.js`; no new abstraction layer for a single-file client script. **Pass.** |
| XIII. Simplicity for MVP | Applies | No SPA framework, no build pipeline, no new dependency of any kind — this plan is *simpler* than feature 005's (which needed one justified new dependency, Jinja2; this one needs none). Chat panel chassis reuses the existing Jinja2 layout rather than introducing client-side templating. **Pass.** |
| XIV. Approved MVP Technology Stack | Applies | Zero new technology introduced — reuses exactly Jinja2 (already established by feature 005) and vanilla CSS/JS (already the site's pattern). **Pass — no Complexity Tracking entry needed.** |

**Gate result (pre-Phase-0)**: PASS, with **no deviation to justify** —
unlike feature 005, this feature introduces no new dependency, so
Complexity Tracking is intentionally empty below.

**Post-Phase-1 re-check**: `research.md`, `data-model.md`,
`contracts/chat-widget-client-contract.md`, and `quickstart.md` were
produced without introducing anything beyond what the pre-Phase-0 table
above already assessed — no new dependency, no new database table, no new
provider/SDK, no new route, no change to any existing security/cost/rate-
limit control, and no route collision (this feature adds zero routes).
**Gate result: still PASS. No new deviation introduced during design.**

## Project Structure

### Documentation (this feature)

```text
specs/006-public-chat-widget/
├── plan.md              # This file (/speckit-plan command output)
├── research.md           # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── chat-widget-client-contract.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Single project (existing pattern — extended, not split; same as feature 005)
src/albercik_chatbot/
├── api/                       # existing: /api/v1/* routers, schemas, errors — UNCHANGED
├── application/                # existing: RAG use-case orchestration — UNCHANGED
├── domain/                     # existing: RAG/prompting/retrieval logic — UNCHANGED
├── providers/                   # existing: LLM/embedding providers — UNCHANGED
├── persistence/                 # existing: SQLAlchemy models/repositories — UNCHANGED
├── infra/                       # existing: logging, concurrency, rate limiting — UNCHANGED
├── main.py                      # existing: create_app() — UNCHANGED (public_site router/static mount already wired by feature 005)
└── public_site/                 # feature 005's package — extended in place, no new modules
    ├── router.py                 # UNCHANGED — this feature adds no route
    ├── models.py, filters.py, data/   # UNCHANGED
    ├── templates/
    │   └── base.html              # MODIFIED — adds the chat launcher button and panel
    │                                #   skeleton (shared by every page that extends this layout)
    └── static/
        ├── css/site.css            # MODIFIED — adds launcher/panel/message-bubble/status
        │                            #   styles and the small-viewport panel-sizing rules
        └── js/
            ├── site.js               # UNCHANGED — existing nav/filter-form enhancements
            └── chat.js                # NEW — all chat widget behavior (open/close, focus
                                        #   trap, fetch + outcome mapping, sessionStorage,
                                        #   dedup, duplicate-submission guard)

tests/
├── contract/
│   ├── test_public_site_pages.py           # UNCHANGED
│   └── test_public_site_chat_widget.py      # NEW: launcher + panel markup and ARIA
│                                              #   attributes present on all 8 pages
├── unit/
│   ├── test_public_site_filters.py, test_public_site_data.py   # UNCHANGED
│   └── test_chat_widget_client_script.py     # NEW: static-source assertions on chat.js
│                                              #   (endpoint literal, field discipline,
│                                              #   no innerHTML, textContent usage)
└── ... (all existing tests, including tests/contract/test_chat*.py, unchanged)
```

**Structure Decision**: Single project, extended in place — this feature
does not add a package, a route, or a dependency; it extends two existing
files inside `public_site/` and adds one new static asset plus its tests,
mirroring exactly how feature 005 extended `main.py` additively. No new
deployment unit, `docker-compose.yml` service, or CI step is needed.
`public_site/` (and by extension this feature) still imports nothing from
`domain/`, `application/`, or `providers/`, and the reverse remains true
too — this feature communicates with the rest of the backend exclusively
through the same public, unauthenticated HTTP boundary any other client of
`/api/v1/chat` would use.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

*No violations — this feature introduces no new dependency, endpoint, or
architectural layer. Table intentionally omitted.*
