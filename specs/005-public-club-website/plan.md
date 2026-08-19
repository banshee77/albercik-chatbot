# Implementation Plan: Public Website for ALBERTOS Traditional Karate-Do Club

**Branch**: `005-public-club-website` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-public-club-website/spec.md`

## Summary

Add a public, unauthenticated, 8-page informational website (Strona główna,
O Karate-Do, O klubie/Historia, Trenerzy, Sekcje, Grafik, Aktualności,
Kontakt) for the fictional ALBERTOS Traditional Karate-Do club, served by
the existing FastAPI application as new, purely additive routes. All content
(trainers, locations, training sessions, news posts, glossary terms) is
static, in-memory Python data — no database, no CMS, no accounts. Pages are
server-rendered with Jinja2 so every page's core content (including the
unfiltered training schedule and news list) is present and readable without
JavaScript; the training-schedule and news filters work via a plain
query-param GET request (full-page-reload fallback) with an optional
vanilla-JS progressive enhancement that re-fetches and swaps the result
list in place without a full reload. Zero changes to the existing RAG/LLM/
Ollama code paths, database schema, or `/api/v1/*`/`/health` contracts.

## Technical Context

**Language/Version**: Python 3.14 (matches the existing project; no new
language/runtime)

**Primary Dependencies**: FastAPI (existing), Starlette `StaticFiles`
(existing, ships with FastAPI/Starlette — no new install), **Jinja2 (NEW —
see Complexity Tracking)**. No new JS framework, no build tool, no CSS
framework — hand-written HTML/CSS and a small vanilla-JS file.

**Storage**: N/A — static, in-memory Python data structures (dataclasses in
a new `public_site/data/` module); no database table, no migration, no
`pgvector`/SQLAlchemy involvement.

**Testing**: pytest + FastAPI `TestClient` (both already the project's
approved/existing tooling) — no new test framework, no browser-automation
tool, no Node.js test runner. See research.md §5 for why this is sufficient
given the chosen server-side-filtering architecture.

**Target Platform**: Linux server, same Docker container/image as the
existing app (no new service, no new container in `docker-compose.yml`).

**Project Type**: Single project (web service) — the public site is a new
in-process module inside the existing FastAPI app, not a separate
frontend/backend split.

**Performance Goals**: A primary page becomes usable in under 2 seconds
under typical broadband/mobile conditions (spec FR-002a/SC-010). Trivially
achievable: server-side rendering of small, in-memory Python data with zero
DB queries, zero external/LLM calls, zero network round-trips beyond the
one HTTP request itself.

**Constraints**: No authentication; no new database tables/migrations; no
writes of any kind (the contact "form" is static/non-functional); MUST NOT
modify existing `/api/v1/*`/`/health` routes, RAG/domain/application/
provider code, or Ollama configuration; MUST leave the entire existing
automated test suite passing unchanged (spec FR-037/038, SC-007).

**Scale/Scope**: 8 primary pages + 1 detail-page pattern (individual news
posts); on the order of 3-5 trainers, 2-4 locations, ~10-15 training
sessions, ≥5 news posts, ≥8 glossary terms — small, fixed, hand-authored
content. No pagination, caching layer, or CDN concerns at this scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicability | Assessment |
|---|---|---|
| I. Security by Default | Applies | New routes are read-only GET (plus a static, non-wired contact form). Query-param filter values are matched against small enumerated allowlists derived from the static data (location/day/level/category) — never interpolated as raw HTML (Jinja2 auto-escapes by default; no `\|safe` on user input). No secrets, no auth decisions made here. **Pass.** |
| II. Tenancy Posture | N/A | No tenant concept touched; single ALBERTOS site as before. |
| III. Secure RAG | N/A | This feature does not call retrieval, the LLM, or embeddings at all (spec FR-037). |
| IV. Secure Document Ingestion | N/A | No uploads in this feature. |
| V. LLM Provider Neutrality | N/A | No LLM call on this feature's request path. |
| VI. Embedding Provider Neutrality | N/A | No embedding call on this feature's request path. |
| VII. Cloud/Provider Neutrality | Applies | No cloud-specific service introduced; static Python data + Jinja2 rendering is portable to any host running the existing container. **Pass.** |
| VIII. API Security | Applies | Public by design (spec FR-001) — this is the intended posture for these routes, not a lapse. Input validation: filter query params are checked against known enumerated values; unrecognized values degrade to the existing empty-state UI, never to an error leaking internals. **Pass.** |
| IX. Privacy and Logging | Applies | No PII collected (static form performs no submission). No new sensitive logging. **Pass.** |
| X. Cost Safety | Applies, but not triggered | This feature's entire request path never invokes a paid LLM or embedding provider, so the specific mandatory controls this principle enumerates (rate limiting *for paid-call protection*, budget, kill switch) address a risk this feature's routes do not create. Existing global controls (if any apply at the ASGI/middleware level to all routes) are untouched either way. **No new cost-control mechanism is added, and none is required**, because there is no paid-provider call to protect. |
| XI. Testing Discipline | Applies (proportionately) | Not "security-sensitive" in the RBAC/provider sense, but the spec's own Testing requirement (item 14) is honored: contract tests for page availability/navigation/filtering/empty-states, unit tests for the pure filter functions and static-data integrity, and a negative test proving the contact form has no backend route to submit to. All via the existing pytest/TestClient stack. **Pass.** |
| XII. Engineering Quality | Applies | Plain dataclasses for static data, plain route handlers, pure filter functions, no repository/factory/DI-framework abstraction. **Pass.** |
| XIII. Simplicity for MVP | Applies | No SPA framework, no build pipeline, no new deployable service, no database. Server-side rendering + a small optional JS enhancement is the minimal design that still satisfies the "works without JavaScript" requirement (SC-008). **Pass.** |
| XIV. Approved MVP Technology Stack | **Deviation — justified below** | Jinja2 is not on the literal approved list. See Complexity Tracking. |

**Gate result (pre-Phase-0)**: PASS, with one documented, justified deviation (Jinja2) — see Complexity Tracking.

**Post-Phase-1 re-check**: `research.md`, `data-model.md`, `contracts/pages.md`,
and `quickstart.md` were produced without introducing anything beyond what
the pre-Phase-0 table above already assessed — no database table, no new
provider/SDK dependency, no auth surface, no new cost-bearing call path,
and no route collision with `/api/v1/*` or `/health` (verified directly
against the existing routers' `prefix=` declarations — see research.md
§4). The single negative-contract test (`contracts/pages.md` — contact
form has no backend route) is the one place this design deliberately adds
*proof of absence* rather than just relying on the markup, matching
Constitution Principle XI's spirit even though this feature falls outside
that principle's literal RBAC/provider trigger list. **Gate result: still
PASS. No new deviation introduced during design.** No violation is silently introduced.

## Project Structure

### Documentation (this feature)

```text
specs/005-public-club-website/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── pages.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Option 1: Single project (existing pattern — extended, not split)
src/albercik_chatbot/
├── api/                      # existing: /api/v1/* routers, schemas, errors — UNCHANGED
├── application/              # existing: RAG use-case orchestration — UNCHANGED
├── domain/                   # existing: RAG/prompting/retrieval logic — UNCHANGED
├── providers/                 # existing: LLM/embedding providers — UNCHANGED
├── persistence/               # existing: SQLAlchemy models/repositories — UNCHANGED
├── infra/                     # existing: logging, concurrency, rate limiting — UNCHANGED
├── main.py                    # existing: create_app() — gains one new include_router()
│                               #   + one new StaticFiles mount; nothing else changes
├── config.py                  # existing — UNCHANGED (no new settings needed)
└── public_site/                # NEW — this feature, fully self-contained
    ├── __init__.py
    ├── router.py               # APIRouter: page routes (/, /karate-do, /o-klubie,
    │                            #   /trenerzy, /sekcje, /grafik, /aktualnosci,
    │                            #   /aktualnosci/{slug}, /kontakt) — no prefix, root-level
    ├── models.py                # frozen dataclasses: Location, Trainer, TrainingSession,
    │                            #   NewsPost, GlossaryTerm
    ├── filters.py                # pure functions: filter_sessions(...), filter_news(...)
    ├── data/
    │   ├── __init__.py
    │   ├── locations.py          # LOCATIONS: tuple[Location, ...]
    │   ├── trainers.py           # TRAINERS: tuple[Trainer, ...]
    │   ├── sessions.py           # SESSIONS: tuple[TrainingSession, ...]
    │   ├── news.py               # NEWS_POSTS: tuple[NewsPost, ...]
    │   └── glossary.py           # GLOSSARY_TERMS: tuple[GlossaryTerm, ...]
    ├── templates/                 # Jinja2 .html (base layout + one per page + news detail)
    └── static/                    # hand-written CSS/JS, mounted at /static/site/*
        ├── css/site.css
        └── js/site.js

tests/
├── contract/
│   └── test_public_site_pages.py    # NEW: every page 200s, nav present, filters work,
│                                      #   empty-states, contact form has no POST route
├── unit/
│   ├── test_public_site_filters.py   # NEW: pure filter-function behavior
│   └── test_public_site_data.py      # NEW: static-data shape/completeness checks
└── ... (all existing tests unchanged)
```

**Structure Decision**: Single project, extended in place. The public
website is one new, fully self-contained package (`public_site/`) inside
the existing `src/albercik_chatbot/` tree, wired into the existing
`main.py::create_app()` via one additional `include_router()` call and one
`app.mount(...)` for static assets — mirroring exactly how the existing
`api/routers/*` are already wired, so no new deployment unit,
`docker-compose.yml` service, or CI step is needed. `public_site/` imports
nothing from `domain/`, `application/`, or `providers/`, and nothing in
those existing packages imports from `public_site/` — satisfying spec
FR-034's separation requirement structurally, not just by convention.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Jinja2 added as a new dependency (Principle XIV names an approved stack that doesn't list a templating engine) | The spec requires (SC-008, and the "JavaScript unavailable" edge case) that every page's core content — including the *unfiltered* training schedule and news list — be present and readable without JavaScript. That rules out a client-side-JS-only rendering approach (fetch JSON, render into an empty page shell), because with JS disabled the page would show nothing. Some form of server-side HTML rendering of the static data is therefore required, not optional. Jinja2 is FastAPI's own first-party, standard mechanism for this (`fastapi.templating.Jinja2Templates`), auto-escapes by default (XSS-safe for the query-param-driven filter views), and adds a single, well-known, actively-maintained dependency — not a framework, not a build pipeline, not a new runtime. | **Hand-rolled Python string templating** (f-strings building HTML): rejected — reinvents auto-escaping (a real XSS-safety regression risk for filter-echo views) for no benefit over a well-audited library, and would be *more* code to review and maintain, not less. **A build-time static-site generator** (bake HTML files at build/deploy time from the same Python data): rejected — adds a new build step/CI stage the project doesn't currently have, and still needs *something* to do the templating (would still add Jinja2 or an equivalent), for no corresponding benefit at this traffic scale. **A client-side SPA framework** (React/Vue + a JSON API): rejected outright — violates SC-008 (breaks without JS), is a materially heavier dependency footprint (build tooling, node_modules, bundler) than a templating library, and is exactly the kind of "generic framework not justified by a concrete current requirement" Principle XIII already tells us to avoid. |

