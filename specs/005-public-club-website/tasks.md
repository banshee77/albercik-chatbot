---

description: "Task list template for feature implementation"
---

# Tasks: Public Website for ALBERTOS Traditional Karate-Do Club

**Input**: Design documents from `/specs/005-public-club-website/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/pages.md, quickstart.md (all present)

**Tests**: Included — spec.md's Testing requirement (item 14) explicitly requests automated tests for page availability, navigation, schedule filtering logic, news filtering/data rendering, and non-regression of the existing suite. Tests are written before their corresponding implementation (TDD), matching this project's established convention.

**Organization**: Tasks are grouped by user story (spec.md's P1–P8) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US8)
- All file paths are relative to the repository root

## Path Conventions

Single project (existing pattern, extended — see plan.md "Project Structure"):
`src/albercik_chatbot/public_site/...`, `tests/contract/...`, `tests/unit/...`

---

## Phase 1: Setup

**Purpose**: Project initialization — no user story work can reference these until done

- [X] T001 Add `jinja2` as a project dependency (`uv add jinja2`), updating `pyproject.toml`/`uv.lock` — the one Constitution-flagged deviation, already justified in plan.md's Complexity Tracking
- [X] T002 Create the `public_site` package skeleton: `src/albercik_chatbot/public_site/__init__.py`, `src/albercik_chatbot/public_site/data/__init__.py`, and empty directories `src/albercik_chatbot/public_site/templates/`, `src/albercik_chatbot/public_site/static/css/`, `src/albercik_chatbot/public_site/static/js/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Static data model, static content, shared layout/styles/scripts, and app wiring that every user story's pages depend on

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete

- [X] T003 Define the 5 entity dataclasses (`Location`, `Trainer`, `TrainingSession`, `NewsPost`, `GlossaryTerm`) per data-model.md, as frozen `@dataclass`es with type hints, in `src/albercik_chatbot/public_site/models.py`
- [X] T004 Write the static-data integrity test in `tests/unit/test_public_site_data.py`, asserting (per data-model.md's validation rules and spec SC-005/SC-006/SC-009/FR-027): `LOCATIONS` has ≥2 entries with unique slugs; `TRAINERS` has ≥3 entries with unique slugs and every `location_slugs` entry resolving to a real `Location.slug`; every `TrainingSession.location_slug` resolves to a real `Location.slug`; `NEWS_POSTS` has ≥5 entries with unique slugs covering at least the 5 example categories named in FR-027 (new season, camp, exam, tournament/event, new beginners group); `GLOSSARY_TERMS` has ≥8 entries with unique terms — confirm this test fails (data modules don't exist yet)
- [X] T005 [P] Author `LOCATIONS` static data (≥2 entries, e.g. Grodzin and Wierzbin sections) in `src/albercik_chatbot/public_site/data/locations.py`
- [X] T006 [P] Author `TRAINERS` static data (≥3 fictional profiles: name, role, grade, specialization, bio, `location_slugs`, `has_photo=False`) in `src/albercik_chatbot/public_site/data/trainers.py`
- [X] T007 [P] Author `SESSIONS` static data (~10–15 entries spanning multiple locations/days/age-levels, each with a valid `location_slug`) in `src/albercik_chatbot/public_site/data/sessions.py`
- [X] T008 [P] Author `NEWS_POSTS` static data (≥5 fictional posts covering: new training season, karate camp, belt examination, tournament/event, new beginners group — per FR-027) in `src/albercik_chatbot/public_site/data/news.py`
- [X] T009 [P] Author `GLOSSARY_TERMS` static data (≥8 terms, e.g. Mokuso, Seiza, Rei, Kiai, Gyaku Tsuki, Kihon, Kata, Kumite, each with category + plain-language explanation) in `src/albercik_chatbot/public_site/data/glossary.py` — running `tests/unit/test_public_site_data.py` after T005–T009 must now pass
- [X] T010 Implement the pure filtering functions `filter_sessions(sessions, *, location=None, day=None, level=None)` and `filter_news(posts, *, category=None)` per data-model.md's "Behavior" notes, in `src/albercik_chatbot/public_site/filters.py`
- [X] T011 Create the (initially route-less) `APIRouter` in `src/albercik_chatbot/public_site/router.py`, a module-level `Jinja2Templates` instance pointed at `public_site/templates/`, and wire both into `src/albercik_chatbot/main.py::create_app()`: `app.include_router(public_site_router)` and `app.mount("/static/site", StaticFiles(directory=...), name="public_site_static")`, added strictly additively (no existing line in `main.py` changed) — confirm `uv run pytest` still passes (zero regressions) and `curl localhost:8000/health` still works after a rebuild
- [X] T012 Implement the shared layout `src/albercik_chatbot/public_site/templates/base.html`: HTML5 doctype, semantic landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`), a skip-to-content link, and a nav bar linking to all 8 primary pages by their fixed paths (`/`, `/karate-do`, `/o-klubie`, `/trenerzy`, `/sekcje`, `/grafik`, `/aktualnosci`, `/kontakt`) with a mobile-menu toggle button (behavior added in T014)
- [X] T013 Implement `src/albercik_chatbot/public_site/static/css/site.css`: design tokens per research.md §6 (palette custom properties, type scale, dojo-floor-line motif, sparing enso mark), a responsive base layout (mobile/tablet/desktop breakpoints), nav/footer/skip-link styles, and `@media (prefers-reduced-motion: reduce)` handling for any transition defined here
- [X] T014 Implement `src/albercik_chatbot/public_site/static/js/site.js`: mobile-menu open/close toggle (progressive enhancement over the nav markup from T012 — menu must be navigable via plain links even if this script fails to load, per FR-008) and a small reveal-on-scroll enhancement (`IntersectionObserver`, no-op gracefully if unsupported)

**Checkpoint**: Foundation ready — `LOCATIONS`, `TRAINERS`, `SESSIONS`, `NEWS_POSTS`, `GLOSSARY_TERMS`, `filter_sessions`, `filter_news`, the base layout, and app wiring all exist and are tested/working. Every user story phase below can now proceed in priority order.

---

## Phase 3: User Story 1 - First-time visitor gets oriented and knows how to join (Priority: P1) 🎯 MVP

**Goal**: A visitor loads `/` and finds the hero, a short Traditional Karate-Do intro, both CTAs, and previews of news/sections/trainer/benefits/contact, all readable on mobile.

**Independent Test**: `GET /` with no other page route implemented; response contains the hero, intro, primary CTA text ("Dołącz do nas"/"Przyjdź na pierwszy trening"), a link toward `/grafik`, at least one news-preview item, at least one location-preview item, a trainer preview, and a link toward `/kontakt`.

### Tests for User Story 1

- [X] T015 [P] [US1] Write contract test `test_home_page_has_hero_and_both_ctas_and_previews` (and a mobile-viewport-safe markup smoke check) in `tests/contract/test_public_site_pages.py`, asserting `GET /` returns 200 and the response body contains: the hero/club identification, a Traditional Karate-Do intro, both CTA link texts, a preview news item, a preview location, a trainer mention, and a link to `/kontakt` — confirm it fails (route doesn't exist yet)

### Implementation for User Story 1

- [X] T016 [US1] Implement `GET /` in `src/albercik_chatbot/public_site/router.py`, passing a small preview slice of `LOCATIONS`, `TRAINERS`, and `NEWS_POSTS` (newest-first) to the template context
- [X] T017 [US1] Implement `src/albercik_chatbot/public_site/templates/home.html` (hero, intro, primary/secondary CTA, news/sections/trainer previews, benefits list, contact CTA) extending `base.html`, plus hero/preview-card styles in `static/css/site.css` — confirm T015 now passes

**Checkpoint**: User Story 1 fully functional and independently testable/demoable.

---

## Phase 4: User Story 2 - Visitor finds a training session that fits their schedule (Priority: P2)

**Goal**: `/grafik` lists every session unfiltered by default and narrows correctly when filtered by location/day/age-level, individually and combined, with a clear empty state when nothing matches.

**Independent Test**: `GET /grafik` (all sessions visible); `GET /grafik?location=...` (narrowed); combined filters narrow further; an impossible combination shows the empty-state message, not a broken page.

### Tests for User Story 2

- [X] T018 [P] [US2] Write unit tests for `filter_sessions` in `tests/unit/test_public_site_filters.py` — no filters returns all; single-criterion filters narrow correctly; combined filters narrow further; an unrecognized value returns an empty result (never an error) — confirm they fail
- [X] T019 [P] [US2] Write contract tests in `tests/contract/test_public_site_pages.py` for `GET /grafik`: unfiltered lists every session; `?location=`, `?day=`, `?level=` each narrow correctly individually and combined; a non-matching combination renders the empty-state message — confirm they fail

### Implementation for User Story 2

- [X] T020 [US2] Implement `GET /grafik` in `router.py`: parse optional `location`/`day`/`level` query params, call `filter_sessions`, pass the result (and the distinct known location/day/level values, for the filter form's options) to the template context — confirm T018 now passes
- [X] T021 [US2] Implement `templates/grafik.html`: a `<form method="get">` filter control (works with zero JS — full-page reload on submit), the session list, and the empty-state message block, plus schedule-specific styles in `static/css/site.css` — confirm T019 now passes
- [X] T022 [US2] Extend `static/js/site.js` with a progressive-enhancement handler that intercepts the `/grafik` filter form's submit, `fetch()`s the same URL, and swaps the rendered session-list fragment in place instead of a full navigation — must degrade to the plain form behavior (T021) if this script doesn't run

**Checkpoint**: User Stories 1–2 both independently functional.

---

## Phase 5: User Story 3 - Visitor learns which location/section fits them (Priority: P3)

**Goal**: `/sekcje` lists every location with its full attribute set and links each to its assigned trainer.

**Independent Test**: `GET /sekcje` shows, per location, name/address/groups/age-level/days-hours/trainer; selecting a trainer name reaches that trainer's profile.

### Tests for User Story 3

- [X] T023 [P] [US3] Write contract test in `tests/contract/test_public_site_pages.py`: `GET /sekcje` returns 200 and every entry in `LOCATIONS` appears with its full attribute set and a link to `/trenerzy#{trainer_slug}` — confirm it fails

### Implementation for User Story 3

- [X] T024 [US3] Implement `GET /sekcje` in `router.py`, passing `LOCATIONS` (with resolved trainer names) to the template context
- [X] T025 [US3] Implement `templates/sekcje.html` (one card per location, all required fields, trainer link) plus location-card styles in `static/css/site.css` — confirm T023 now passes

**Checkpoint**: User Stories 1–3 all independently functional.

---

## Phase 6: User Story 4 - Visitor learns about the trainers (Priority: P4)

**Goal**: `/trenerzy` lists every trainer with their full attribute set and a consistent placeholder where a photo would go.

**Independent Test**: `GET /trenerzy` shows, per trainer, name/role/grade/specialization/bio/section(s), with a placeholder graphic (never a broken image).

### Tests for User Story 4

- [X] T026 [P] [US4] Write contract test in `tests/contract/test_public_site_pages.py`: `GET /trenerzy` returns 200, every entry in `TRAINERS` appears with its full attribute set, and every trainer card renders the placeholder graphic (since `has_photo` is `False` for all current data) — confirm it fails

### Implementation for User Story 4

- [X] T027 [US4] Implement `GET /trenerzy` in `router.py`, passing `TRAINERS` (with resolved location names) to the template context
- [X] T028 [US4] Implement `templates/trenerzy.html` (one card per trainer, id anchors matching `trainer_slug` for `/sekcje`'s links, CSS/SVG placeholder graphic per research.md §7) plus trainer-card styles in `static/css/site.css` — confirm T026 now passes

**Checkpoint**: User Stories 1–4 all independently functional.

---

## Phase 7: User Story 5 - Visitor understands what Traditional Karate-Do is (Priority: P5)

**Goal**: `/karate-do` explains the discipline (what it is, philosophy/values, kihon/kata/kumite, etiquette, belt progression, benefits by age) and includes a findable, categorized glossary of ≥8 dojo terms.

**Independent Test**: `GET /karate-do` covers every required topic and lists every `GlossaryTerm`, grouped so a specific term is findable without reading the whole page.

### Tests for User Story 5

- [X] T029 [P] [US5] Write contract test in `tests/contract/test_public_site_pages.py`: `GET /karate-do` returns 200, mentions kihon/kata/kumite, etiquette, belt progression, and benefits for children/teenagers/adults, and lists every `GlossaryTerm.term` from `GLOSSARY_TERMS` grouped under its `category` — confirm it fails

### Implementation for User Story 5

- [X] T030 [US5] Implement `GET /karate-do` in `router.py`, passing `GLOSSARY_TERMS` grouped by `category` to the template context
- [X] T031 [US5] Implement `templates/karate_do.html`: generic, non-club-specific educational copy (per FR-006/FR-018 — no unsupported real-organization/date claims) covering every required topic, plus the categorized glossary section, plus glossary styles in `static/css/site.css` — confirm T029 now passes

**Checkpoint**: User Stories 1–5 all independently functional.

---

## Phase 8: User Story 6 - Visitor reads the club's story (Priority: P6)

**Goal**: `/o-klubie` presents a fictional narrative (origins, first groups, growth of sections, camps/examinations, current community), clearly framed as demo content.

**Independent Test**: `GET /o-klubie` covers every required narrative beat and contains no wording implying it is verified real-world history.

### Tests for User Story 6

- [X] T032 [P] [US6] Write contract test in `tests/contract/test_public_site_pages.py`: `GET /o-klubie` returns 200 and mentions the club's origins, first training groups, growth of new sections, camps/examinations, and the current community — confirm it fails

### Implementation for User Story 6

- [X] T033 [US6] Implement `GET /o-klubie` in `router.py`
- [X] T034 [US6] Implement `templates/historia.html` (fictional narrative copy covering every required beat, per FR-019) plus any history-page-specific styles in `static/css/site.css` — confirm T032 now passes

**Checkpoint**: User Stories 1–6 all independently functional.

---

## Phase 9: User Story 7 - Visitor catches up on club news (Priority: P7)

**Goal**: `/aktualnosci` lists ≥5 news posts (title/date/category/summary/optional image), filterable by category with a clear empty state; selecting a post shows its full content at a stable, bookmarkable `/aktualnosci/{slug}` URL.

**Independent Test**: `GET /aktualnosci` (unfiltered, all posts); `?category=` narrows correctly; a non-matching category shows the empty state; `GET /aktualnosci/{slug}` shows full content for a known slug and 404s for an unknown one.

### Tests for User Story 7

- [X] T035 [P] [US7] Write unit tests for `filter_news` in `tests/unit/test_public_site_filters.py` — no filter returns all posts; a valid category narrows correctly; an unrecognized category returns an empty result — confirm they fail
- [X] T036 [P] [US7] Write contract tests in `tests/contract/test_public_site_pages.py`: `GET /aktualnosci` unfiltered lists every post (newest-first); `?category=` narrows correctly; a non-matching category renders the empty-state message; `GET /aktualnosci/{slug}` for a real slug returns 200 with the full article body; `GET /aktualnosci/does-not-exist` returns 404; the home page's news preview (T017) links into this page/post — confirm they fail

### Implementation for User Story 7

- [X] T037 [US7] Implement `GET /aktualnosci` (optional `category` query param, `filter_news`, newest-first ordering) and `GET /aktualnosci/{slug}` (404 via the existing app-wide error handling on an unknown slug) in `router.py` — confirm T035 and the list-page half of T036 now pass
- [X] T038 [US7] Implement `templates/aktualnosci.html` (list + `<form method="get">` category filter + empty-state block) and `templates/aktualnosci_detail.html` (full article content) plus news-card styles in `static/css/site.css` — confirm the remainder of T036 now passes
- [X] T039 [US7] Extend `static/js/site.js`'s progressive-enhancement handler (T022) to also cover `/aktualnosci`'s category filter form, reusing the same fetch-and-swap pattern

**Checkpoint**: User Stories 1–7 all independently functional.

---

## Phase 10: User Story 8 - Visitor gets in touch with the club (Priority: P8)

**Goal**: `/kontakt` shows phone/email/training locations/social-media placeholders, and any contact form present is verifiably non-functional (no backend route it can reach).

**Independent Test**: `GET /kontakt` shows all required contact info; `POST /kontakt` (or any path the form's markup might target) returns 404/405, proving no backend integration exists.

### Tests for User Story 8

- [X] T040 [P] [US8] Write contract tests in `tests/contract/test_public_site_pages.py`: `GET /kontakt` returns 200 with a phone number, an email address, every `Location`'s name/address, and social-media placeholders; `POST /kontakt` returns 404 or 405 — confirm they fail

### Implementation for User Story 8

- [X] T041 [US8] Implement `GET /kontakt` in `router.py`, passing `LOCATIONS` to the template context — deliberately register no `POST`/`PUT`/`PATCH` handler for this or any related path
- [X] T042 [US8] Implement `templates/kontakt.html` (phone/email/locations/social placeholders, and a visual-only contact form with no `action` wired to a real endpoint) plus contact-page styles in `static/css/site.css` — confirm T040 now passes

**Checkpoint**: All 8 user stories independently functional. Feature complete per spec.md.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Whole-feature verification that spans multiple stories

- [X] T043 Run the full existing automated suite (`uv run pytest`) and confirm 100% of pre-existing tests still pass unmodified, alongside all new tests from T004/T015/T018/T019/T023/T026/T029/T032/T035/T036/T040 (spec SC-007)
- [X] T044 Run the project's standard quality gate — `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `docker compose config` — and fix any findings
- [X] T045 [P] Execute quickstart.md Scenarios 1–8 end-to-end against a running `docker compose up -d` stack (page availability, schedule/news filtering + empty states, deep-linking, content-completeness counts, contact-form non-functionality, JS-disabled behavior via plain `curl`, and page-load timing) and record results
- [X] T046 [P] Manual accessibility/responsive pass per spec Edge Cases: keyboard-only navigation through the skip link and mobile menu, screen-reader landmark sanity check, and visual check at ≤360px and ≥1920px viewport widths on all 8 pages

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story phase.
- **User Stories (Phases 3–10)**: All depend on Foundational completion. Each phase's own route additions to the shared `router.py` and `static/css/site.css` are sequential *across* stories (same files); the phases are otherwise independent and are intended to be implemented in priority order (P1 → P8) per this project's established single-developer workflow, though each remains independently testable on its own.
- **Polish (Phase 11)**: Depends on all desired user story phases being complete.

### Within Each User Story

- Tests are written first and confirmed failing before the corresponding implementation task.
- Route (`router.py`) before template (needs the route's context variable names decided).
- Story complete and its own tests green before moving to the next priority.

### Parallel Opportunities

- T005–T009 (the 5 static-data files) can run in parallel once T003 (models) and T004 (the failing data test) exist.
- Within each user story phase, the test-writing task(s) marked `[P]` can run in parallel with each other (different files) but must both complete, and be confirmed failing, before that story's implementation tasks begin.
- T045 and T046 (Polish) can run in parallel with each other.

---

## Parallel Example: Foundational static data

```bash
# After T003 (models.py) and T004 (failing data-integrity test) are done:
Task: "Author LOCATIONS static data in src/albercik_chatbot/public_site/data/locations.py"
Task: "Author TRAINERS static data in src/albercik_chatbot/public_site/data/trainers.py"
Task: "Author SESSIONS static data in src/albercik_chatbot/public_site/data/sessions.py"
Task: "Author NEWS_POSTS static data in src/albercik_chatbot/public_site/data/news.py"
Task: "Author GLOSSARY_TERMS static data in src/albercik_chatbot/public_site/data/glossary.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1 (home page).
4. **STOP and VALIDATE**: `GET /` independently, per its Independent Test above.
5. Deploy/demo if ready — the home page alone is a credible, demonstrable front door (spec.md "Why this priority").

### Incremental Delivery

1. Setup + Foundational → foundation ready (all static content + shared layout/styles/wiring exist and are tested).
2. Add User Story 1 → validate independently → this is the MVP.
3. Add User Story 2 (schedule) → validate independently — the highest-value conversion feature after the home page.
4. Add User Stories 3–8 in priority order → validate each independently → full 8-page site.
5. Phase 11 Polish → full-suite + quickstart + accessibility verification.

### Notes

- No parallel-team story split is recommended despite the phase structure: every story after US1 edits the same shared `router.py` and `static/css/site.css`, so sequential P1→P8 delivery avoids merge conflicts, even though each story remains independently testable once its predecessor lands (matching this project's established single-developer workflow from prior features).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently before moving to the next.
- Avoid: vague tasks, same-file conflicts within a phase, cross-story dependencies that would break a story's independent testability.
