# Research: Public Website for ALBERTOS Traditional Karate-Do Club

Phase 0 output for `/speckit-plan`. Each section resolves one open technical
question raised by the Technical Context / Constitution Check.

## 1. Rendering strategy: server-side Jinja2, not client-side-only

- **Decision**: Pages are rendered server-side with Jinja2 templates
  (`fastapi.templating.Jinja2Templates`), reading from static, in-memory
  Python data. A small vanilla-JS file progressively enhances the two
  filterable views (schedule, news) to re-fetch and swap results in place
  instead of a full page reload, but the plain `<form method="get">` +
  full-page-reload path is the real, always-working mechanism — JS is an
  enhancement, never a requirement.
- **Rationale**: Spec SC-008 and the "JavaScript unavailable" edge case
  require every page's core content — explicitly including the *unfiltered*
  schedule and news list — to remain readable without JavaScript. A
  client-rendered (fetch-JSON-into-empty-DOM) approach cannot satisfy that:
  with JS off, the page would be empty. Server-side rendering makes "works
  without JS" the default behavior, not a separate code path to maintain.
- **Alternatives considered**:
  - *Client-side rendering only* (static HTML shell + JS fetches JSON):
    rejected — fails SC-008 outright.
  - *Static-site generator (build-time HTML baking)*: rejected — adds a
    new build/CI step the project doesn't have, and still requires a
    templating mechanism (would still add Jinja2 or equivalent) for no
    benefit at this traffic/content scale (a handful of pages, updated by
    editing Python source, not by end users).
  - *SPA framework (React/Vue)*: rejected — fails SC-008, adds a build
    pipeline and a materially larger dependency footprint than a
    templating library, violates Constitution Principle XIII (no framework
    without a concrete current requirement).

## 2. Filtering mechanism: server-side, query-param GET, allowlist-validated

- **Decision**: The schedule (`/grafik?location=...&day=...&level=...`) and
  news (`/aktualnosci?category=...`) pages accept optional query
  parameters. The route handler validates each supplied value against the
  small enumerated set actually present in the static data (e.g., the
  known location names); an unrecognized value is treated as "no match"
  (empty-state UI), never echoed back unescaped. The pure filtering logic
  lives in `public_site/filters.py` as plain functions over the static data
  — no framework, no query builder.
- **Rationale**: This is the one design choice that resolves three
  requirements at once: (a) works with zero JavaScript (a plain HTML
  `<form method="get">` triggers a normal navigation Jinja2 can render),
  (b) is trivially unit-testable in Python via pytest — exactly the
  project's existing, approved test tooling — instead of needing a browser-
  automation or Node-based JS test runner, and (c) keeps filtering logic in
  one place (Python) rather than duplicating the same predicate logic in
  both a Python data layer and separate client-side JS that could drift
  out of sync.
- **Alternatives considered**:
  - *Client-side-only filtering* (JS mutates DOM visibility): rejected —
    fails SC-008; also not independently unit-testable without adding a
    JS/browser test tool, which Constitution Principle XIV doesn't approve
    and this feature doesn't otherwise need.
  - *A JSON "API" endpoint the page always fetches from on load, even for
    the unfiltered view*: rejected — reintroduces the "empty without JS"
    failure mode for the *initial* view; the chosen design only uses JS as
    an optional, swappable enhancement on top of a working server-rendered
    baseline.

## 3. Static data representation: Python dataclasses, not JSON/YAML files

- **Decision**: Trainers, locations, sessions, news posts, and glossary
  terms are plain frozen `@dataclass` instances defined directly in
  `public_site/data/*.py`, imported at process start — not JSON/YAML files
  parsed at runtime or at import time.
- **Rationale**: This content is maintained by editing project source
  (spec Assumptions: "static structured content maintained as part of the
  project, not editable by any... UI"), not by a non-technical content
  editor or an external tool — so there's no audience for a
  human-editable-but-not-Python data format. Dataclasses get free type
  checking (mypy, matching Constitution Principle XII's "type hints
  throughout"), no parsing/validation step, no risk of a malformed file at
  runtime, and are trivially importable in tests (`from
  albercik_chatbot.public_site.data.news import NEWS_POSTS`).
- **Alternatives considered**:
  - *JSON files loaded at startup*: rejected — adds a parsing/validation
    step and a new failure mode (malformed JSON at deploy time) for zero
    benefit, since nothing outside this codebase ever edits this data.
  - *A tiny SQLite file*: rejected outright by spec FR-035/036 (no
    database).

## 4. URL / slug scheme

- **Decision**: Root-level, Polish, human-readable paths:
  `/` (home), `/karate-do`, `/o-klubie` (history), `/trenerzy`, `/sekcje`,
  `/grafik` (schedule), `/aktualnosci` (news list) + `/aktualnosci/{slug}`
  (news detail), `/kontakt`. Trainers, locations, and news posts each carry
  a stable `slug: str` field in their static data (kebab-case, unique)
  used for the news detail path and as in-page anchor ids elsewhere.
- **Rationale**: Satisfies the Edge Case requirement that a bookmarked/
  shared link to a specific news post loads that post directly. Confirmed
  no collision with any existing route: all existing API routes are under
  `/api/v1/*` (`auth.py`, `documents.py`, `chat.py` routers all declare
  `APIRouter(prefix="/api/v1", ...)`), and `health.py` only defines
  `/health` — the entire root path space is free.
- **Alternatives considered**: UUID-based slugs — rejected as needlessly
  opaque/unfriendly for a handful of hand-authored demo posts; a
  human-readable slug is simpler to author and read in a URL bar.

## 5. Testing approach: pytest + FastAPI `TestClient` only

- **Decision**: All automated coverage for this feature uses the project's
  existing pytest + `httpx`/`TestClient` stack — no Playwright, no
  Selenium, no Node.js test runner. Three test files: unit tests for the
  pure filter functions and static-data shape/completeness
  (`test_public_site_filters.py`, `test_public_site_data.py`), and contract
  tests hitting the real routes for page availability, navigation-link
  presence, filter behavior (including empty states), and a negative test
  proving the contact page's form has no backend route to submit to
  (`test_public_site_pages.py`).
- **Rationale**: Because filtering is server-side (§2), there is no
  meaningful client-side logic left that *needs* a browser to test — the
  vanilla-JS enhancement only swaps already-correct, already-tested HTML
  fragments the server produced; its absence doesn't change correctness
  (SC-008). This keeps the entire test suite on the same tooling the rest
  of the project already uses and trusts, with zero new dependencies,
  fully satisfying spec Testing item 14 (page availability, navigation,
  schedule/news filtering, non-regression) without stretching Constitution
  Principle XIV further than the one already-justified Jinja2 addition.
- **Alternatives considered**: Playwright/browser automation for true
  DOM-interaction testing of the JS enhancement — rejected as
  disproportionate: it would test a pure progressive-enhancement layer
  whose correctness is already guaranteed by the server-rendered baseline
  it fetches from, at the cost of a genuinely new, heavy dependency
  (browser binaries, a different test runtime) the constitution doesn't
  approve and this feature doesn't need to meet its acceptance criteria.

## 6. Visual design tokens (FR-007's Japanese design language, made concrete)

- **Decision**: A small set of CSS custom properties define the palette and
  type scale, applied via one shared `site.css`:
  - Palette: `--ink: #1a1a1a` (near-black), `--paper: #f5f2ec` (warm
    off-white), `--indigo: #22314f` (deep indigo, primary), `--accent:
    #b3382c` (single restrained red accent, used sparingly — e.g. active
    nav state, primary CTA), plus one neutral mid-gray for secondary text.
  - Type: a serif or high-contrast humanist sans for headings (evoking
    calligraphic weight-contrast without literal brush-script fonts), a
    plain, highly legible sans for body copy — both from a small,
    self-hostable font stack (system-font fallback first, so the site
    never blocks render on a webfont, keeping FR-002a's <2s budget easy).
  - Motifs used sparingly, never as page-filling decoration: a thin
    horizontal rule motif evoking a dojo floor line under section
    headings; one static `enso`-inspired circle mark used once in the
    hero and as a small brand mark in the footer/nav — never as a
    repeating background pattern.
- **Rationale**: Operationalizes the amended FR-007 ("authentic, elevated
  Japanese design language... avoid tacky/kitsch execution") into concrete,
  buildable decisions — a restrained, disciplined palette and minimal use
  of a single motif reads as considered rather than novelty-symbol-driven,
  matching the "credible, premium dojo feeling, not a tourist-shop
  pastiche" language in the spec.
- **Alternatives considered**: A literal red-circle-on-white "flag" motif
  or repeating kanji/kana background pattern — rejected, exactly the
  "decorative symbols"/"fake calligraphy" excess FR-007 explicitly warns
  against.

## 7. Placeholder imagery: CSS/SVG only, no photo assets

- **Decision**: Trainer photos, news images, and any other "photography" in
  this feature are CSS-based placeholders (a flat or subtly textured block
  in the palette above, with a simple inline SVG monogram/silhouette) —
  no external image files are sourced, licensed, or bundled.
- **Rationale**: Spec Assumptions explicitly put photography out of scope
  to source/license for this feature; a placeholder that's part of the
  page's own CSS/SVG has zero licensing risk, zero missing-asset 404s, and
  trivially satisfies the "consistent placeholder, not a broken image"
  requirement (FR-021, Edge Cases) for every entity, always, by
  construction.
- **Alternatives considered**: Bundling stock/AI-generated placeholder
  photos — rejected as unnecessary scope/risk (licensing, file size vs.
  the 2s budget) for a requirement a few lines of CSS/SVG already satisfy.

## 8. Accessibility & motion

- **Decision**: Semantic landmarks (`<header>`, `<nav>`, `<main>`,
  `<footer>`), a skip-to-content link, visible focus states, `alt=""` on
  decorative placeholder graphics and real `alt` text on anything
  meaningful, and all reveal/hover animation wrapped in `@media
  (prefers-reduced-motion: reduce)` to disable non-essential motion.
- **Rationale**: Directly satisfies FR-004 (semantic HTML,
  screen-reader/keyboard navigation) and FR-008 (restrained interactivity
  that never blocks access to content).
- **Alternatives considered**: None — this is baseline, non-optional web
  accessibility practice already implied by FR-004; no tradeoff to weigh.

## 9. Performance: no caching layer needed at this scale

- **Decision**: No response caching, no CDN, no pre-computed static export
  is added for the MVP. Jinja2's default template auto-reload is disabled
  in a way consistent with how the rest of the app already runs in
  production (no per-request filesystem template recompilation cost
  beyond Jinja2's own built-in bytecode caching).
- **Rationale**: With in-memory Python data (no DB round-trip) and no
  external calls, rendering a page of this size is on the order of single-
  digit milliseconds of server work — the <2s budget (FR-002a/SC-010) is
  dominated entirely by normal network/TLS/browser-render time, not by
  anything this feature's server-side code does. Adding a caching layer
  now would be optimizing a cost that doesn't exist yet (Constitution
  Principle XIII: no infrastructure for scenarios the project doesn't have).
- **Alternatives considered**: In-memory response caching (e.g.,
  `functools.lru_cache` around rendered HTML) — rejected as premature; can
  be added later if real traffic ever shows otherwise, with zero
  architectural change required to add it.
