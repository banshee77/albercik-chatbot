---

description: "Task list template for feature implementation"
---

# Tasks: Public Website Chat Widget

**Input**: Design documents from `/specs/006-public-chat-widget/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/chat-widget-client-contract.md, quickstart.md (all present)

**Tests**: Included — spec.md's Testing requirement (item 16) explicitly requests automated tests for widget markup/accessibility attributes, endpoint/field discipline in the client script, safe-rendering strategy, and non-regression of the existing suite, all without live providers, GPU, or browser automation. Tests are written before their corresponding implementation (TDD), matching this project's established convention (feature 005).

**Organization**: Tasks are grouped by user story (spec.md's P1–P5) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All file paths are relative to the repository root

## Path Conventions

Single project (existing pattern, extended — see plan.md "Project Structure"):
`src/albercik_chatbot/public_site/...`, `tests/contract/...`, `tests/unit/...`. This feature adds **no new Python module, route, or dependency** — only edits to `base.html`/`site.css` and one new static JS file.

---

## Phase 1: Setup

**Purpose**: Confirm a clean starting baseline — no dependency changes are needed for this feature

- [X] T001 Run `uv run pytest` and `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests` to confirm the pre-feature baseline is green (plan.md confirms zero new dependencies are needed, so no `pyproject.toml`/`uv.lock` change belongs in this feature)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared launcher/panel chassis (markup, styling, open/close mechanics, session storage) that every user story's behavior builds on

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete

- [X] T002 [P] Write contract test `tests/contract/test_public_site_chat_widget.py`: for each of the 8 public pages (`/`, `/karate-do`, `/o-klubie`, `/trenerzy`, `/sekcje`, `/grafik`, `/aktualnosci`, `/kontakt`), assert the response contains exactly one `id="chat-launcher"` element with an `aria-label` naming "Zapytaj Albertos" / "otwórz czat"; the panel skeleton `id="chat-panel"` with `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` pointing at `id="chat-panel-title"`; the scope-notice text "Zapytaj o treningi, grafik, trenerów, sekcje i informacje o klubie."; `id="chat-messages"` with `role="log"`; `id="chat-status"` with `role="status"`; `id="chat-form"`, `id="chat-input"`, `id="chat-send"`; and `id="chat-close"` with an `aria-label` — confirm it fails (`base.html` doesn't have the widget yet)
- [X] T003 Implement the launcher button and chat panel skeleton in `src/albercik_chatbot/public_site/templates/base.html` per data-model.md/contracts doc's element ids, plus a `<script src="/static/site/js/chat.js" defer></script>` tag — confirm T002 now passes
- [X] T004 [P] Add baseline widget CSS to `src/albercik_chatbot/public_site/static/css/site.css`: `.js .chat-launcher` (fixed-position floating button using existing design tokens, bottom-right, never overlapping the skip-link or footer); `.js .chat-panel` (hidden by default, revealed via an `is-open` class; on desktop a bottom-right anchored card bounded by `max-width`/`max-height` so it never takes over the viewport — FR-028); message-bubble base styles distinguishing `.chat-message--user` / `.chat-message--assistant`; `#chat-status` styling; and, within the existing ≤46rem breakpoint, panel sizing so it may occupy most of the viewport with all controls reachable (FR-027) — confirm `uv run pytest` (specifically `tests/contract/test_public_site_pages.py`) still passes with no regression
- [X] T005 [P] Create `src/albercik_chatbot/public_site/static/js/chat.js`: an IIFE skeleton; DOM element lookups by id; `sessionStorage` read/write helpers for the `ChatSession` shape (data-model.md) with a try/catch fallback to an empty session on any storage/parse failure; a `renderMessage(role, text, sources)` helper that builds message elements via `document.createElement` and sets text via `.textContent` only (never `.innerHTML`), appending to `#chat-messages`; a history-restore call on `DOMContentLoaded` using that helper; and a basic open/close toggle wired to `#chat-launcher`/`#chat-close` (toggling the panel's `hidden` attribute/`is-open` class and the launcher's `aria-expanded`) — confirm manually in a browser that the panel opens and closes (no automated test yet; no request-handling exists at this point)

**Checkpoint**: Foundation ready — the shared launcher/panel chassis exists, is styled, is present on every page, and opens/closes. No question can be submitted yet; every user story below builds on this.

---

## Phase 3: User Story 1 - Visitor asks a question and gets a grounded answer (Priority: P1) 🎯 MVP

**Goal**: Open the launcher on any page, submit a question known to be answerable from site content, and see the answer plus its sources — the widget's entire reason for existing.

**Independent Test**: On any public page, open the launcher, submit a question that the seeded knowledge base can answer, and confirm the answer and a compact, deduplicated sources line appear in the panel without a full page reload.

### Tests for User Story 1

- [X] T006 [P] [US1] Write static-source unit test `tests/unit/test_chat_widget_client_script.py`: read `chat.js` as text and assert — exactly one occurrence of the literal `/api/v1/chat`, and no other `/api/` path literal anywhere in the file; the request body passed to `fetch` is constructed with only a `question` key (no literal `model`/`provider`/`llm_provider`/`max_tokens`/`top_k`/`system_prompt`/`temperature`/`think`/`retries`/`budget` key in a request-construction context); `.innerHTML` does not appear anywhere in the file; `.textContent` does — confirm it fails (`chat.js` has no `fetch` call yet)

### Implementation for User Story 1

- [X] T007 [US1] Implement the submit handler in `chat.js`: prevent default form submission; read/trim `#chat-input`'s value and ignore an empty/whitespace-only submission (Edge Case); return early if a request is already in flight (duplicate-submission guard, FR-016); otherwise set the guard, disable `#chat-send`/`#chat-input`, show a loading message in `#chat-status` (e.g. "Albertos AI pisze odpowiedź…"), and append the visitor's question to the message log via the Foundational `renderMessage` helper, persisting it
- [X] T008 [US1] Implement the `POST /api/v1/chat` call in `chat.js`: `fetch('/api/v1/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question})})`; on a `200` response whose body has a string `outcome` and `answer` (per contracts/chat-widget-client-contract.md's mapping table), branch explicitly on `outcome`; for `"grounded"`, render `answer` plus — when `sources` is non-empty — a deduplicated, first-seen-order, comma-joined `"Źródła: ..."` line built only from each source's `label` (never `document_id`, FR-009a/FR-014); clear `#chat-status`; release the duplicate-submission guard and re-enable the controls in a `finally` block regardless of outcome — confirm T006 now passes
- [X] T009 [US1] Persist each completed exchange (the user's question plus the assistant's answer and its deduplicated source labels) to `sessionStorage` via the Foundational helper, so it survives navigation to another public page — confirm manually per quickstart.md Scenario 4, steps 1–3

**Checkpoint**: User Story 1 (MVP) fully functional and independently demoable.

---

## Phase 4: User Story 2 - Visitor honestly told when a question is out of scope or unanswerable (Priority: P2)

**Goal**: `insufficient_information` and `out_of_scope` responses render a friendly, honest message — never a fabricated answer, never a silent no-op, and never a sources line.

**Independent Test**: Submit a question engineered to return `insufficient_information`, and separately one engineered to return `out_of_scope` (see `tests/contract/test_chat_answerability.py` / `test_chat.py` for how the existing backend triggers each), and confirm each renders `answer` with no sources line.

### Tests for User Story 2

- [X] T010 [P] [US2] Extend `tests/unit/test_chat_widget_client_script.py`: assert the outcome-handling code in `chat.js` contains explicit branches (not just an implicit fallthrough) for both `"insufficient_information"` and `"out_of_scope"`, and that neither branch ever constructs a `"Źródła:"` sources line — confirm it fails

### Implementation for User Story 2

- [X] T011 [US2] Extend the outcome branch in `chat.js` to explicitly handle `"insufficient_information"` and `"out_of_scope"` — both render `answer` via the same `renderMessage` path used for `"grounded"`'s answer text, but the sources line is explicitly omitted for any outcome other than `"grounded"`, rather than relying on the backend's `sources` array happening to be empty — confirm T010 now passes

**Checkpoint**: User Stories 1–2 both independently functional — the widget never overclaims or gives a confusing non-answer.

---

## Phase 5: User Story 3 - Visitor sees a clear message when the assistant is temporarily unavailable or the network fails (Priority: P3)

**Goal**: A 429, a 503/`unavailable`, a network failure, a malformed response, or any other unexpected status all degrade to a distinct-enough or shared friendly Polish message — never a stuck spinner, a blank panel, or raw error text — and the visitor can always try again.

**Independent Test**: Simulate each of a 429 response, a 503 response, and a network failure (browser devtools, per quickstart.md Scenario 5), and confirm each produces a friendly message with no raw error text, and that the panel remains fully usable afterward.

### Tests for User Story 3

- [X] T012 [P] [US3] Extend `tests/unit/test_chat_widget_client_script.py`: assert `chat.js` contains a `429` status branch that reads the `Retry-After` response header, a `503` branch, a `catch`/`.catch` for a rejected `fetch` promise, and a single shared fallback code path reachable both from an unparseable/malformed response body and from any other unhandled status (FR-018a) — confirm it fails

### Implementation for User Story 3

- [X] T013 [US3] Implement the `429` branch in `chat.js`: read the `Retry-After` response header; if present and a positive integer, include the wait time in a friendly Polish rate-limit message; otherwise show a generic rate-limit message (FR-019)
- [X] T014 [US3] Implement the `503` branch: attempt the same `outcome`/`answer` shape parse used in T008; if it parses, render `answer` exactly as the `"unavailable"` case (reusing the backend's own safe message, research.md §1); if it does not parse, fall through to the generic fallback (T015)
- [X] T015 [US3] Implement the single generic fallback friendly error message, used for: a thrown/rejected `fetch` (network failure), a `200`/`503` response whose body fails the `outcome`/`answer` shape check, and any HTTP status other than `200`/`429`/`503` (FR-018a) — ensure the duplicate-submission guard and controls are always re-enabled afterward (reusing T007's `finally` block) so the visitor can immediately try again (FR-020) — confirm T012 now passes
- [X] T016 [US3] Confirm manually (quickstart.md Scenario 5) that the close button remains clickable throughout every state added in T013–T015 (FR-017) — guaranteed structurally since the close handler is wired independently of the submission guard in T007; verify no regression

**Checkpoint**: User Stories 1–3 all independently functional — every outcome the existing backend (or a dead network) can produce has defined, friendly, non-technical handling.

---

## Phase 6: User Story 4 - Visitor operates the widget entirely by keyboard (Priority: P4)

**Goal**: The launcher, panel, input, send, and close controls are all fully keyboard-operable, with focus moving into the panel on open, back to the launcher on close, and Escape closing the panel.

**Independent Test**: Using only Tab, Enter/Space, and Escape (no mouse), reach the launcher from any page, open the panel, confirm focus moved into it, close it with Escape, and confirm focus returned to the launcher.

### Tests for User Story 4

- [X] T017 [P] [US4] Extend `tests/unit/test_chat_widget_client_script.py`: assert `chat.js` contains an `Escape`/`Esc` keydown check, at least two distinct `.focus()` call sites (into the panel on open, back to the launcher on close), and a `Tab`/`shiftKey` check (the focus-trap wrap logic) — confirm it fails

### Implementation for User Story 4

- [X] T018 [US4] Implement focus management in `chat.js`'s open handler: move keyboard focus to the panel's heading or `#chat-input` when the panel opens (FR-030)
- [X] T019 [US4] Implement focus management in `chat.js`'s close handler (covering both the close-button click and Escape): return keyboard focus to `#chat-launcher` (FR-030), using a reference captured at open time
- [X] T020 [US4] Implement an `Escape` keydown listener scoped to the panel that closes it (FR-031), and a small Tab/Shift+Tab focus trap that wraps focus among the panel's focusable elements while it is open — confirm T017 now passes
- [X] T021 [US4] Confirm manually (quickstart.md Scenario 4 step 2; spec.md US4's acceptance scenarios) that the `#chat-status`/`#chat-messages` updates from User Stories 1–3 are announced by assistive technology without requiring a mouse at any point — structurally guaranteed by the Foundational `role="log"`/`role="status"` markup; verify no regression

**Checkpoint**: User Stories 1–4 all independently functional — the entire widget is operable with only Tab, Enter/Space, and Escape.

---

## Phase 7: User Story 5 - Visitor with JavaScript disabled still gets a fully usable public site (Priority: P5)

**Goal**: With JavaScript disabled, all 8 public pages remain exactly as usable as before this feature, and the launcher/panel are absent rather than a visibly broken control.

**Independent Test**: Disable JavaScript (or fetch each page with a plain HTTP client) and confirm all 8 public pages still render their full existing content and navigation, with the chat launcher simply absent.

### Tests for User Story 5

- [X] T022 [P] [US5] Extend `tests/contract/test_public_site_chat_widget.py`: assert every one of the 8 public pages still returns 200 and that the widget markup added in T003 has no `href` or inline event-handler attribute that could make it appear interactive without `chat.js` running — confirm it passes without modification (should already hold, since T002/T003 were purely additive)

### Implementation for User Story 5

- [X] T023 [US5] Verify (do not re-implement — enforced structurally by T003/T004's `.js`-class gating, the same mechanism feature 005 established for the mobile-nav toggle, reused per research.md §3) that every widget CSS selector in `site.css` is scoped under `.js `, so the launcher/panel are invisible without JavaScript rather than present-but-dead — fix any selector found not to be so scoped
- [X] T024 [US5] Run `tests/contract/test_public_site_pages.py` (feature 005's existing full page suite) and confirm 100% still pass unmodified — proves this feature's additions did not regress any of the 8 pages' pre-existing content (spec SC-005)

**Checkpoint**: All 5 user stories independently functional. Feature complete per spec.md.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Whole-feature verification that spans multiple stories

- [X] T025 Run the full existing automated suite (`uv run pytest`) and confirm 100% of pre-existing tests still pass unmodified, alongside all new tests from T002/T006/T010/T012/T017/T022 (spec SC-008)
- [X] T026 Run the project's standard quality gate — `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `docker compose config` — and fix any findings
- [X] T027 [P] Execute quickstart.md Scenarios 1–3 and 6–7 end-to-end against a running `docker compose up -d` stack (launcher/panel markup via curl, `chat.js` self-containment, the automated suite, no-JS non-regression) and record results
- [X] T028 [P] Execute quickstart.md Scenarios 4–5 manually in a real browser (conversation flow across all four backend outcomes; 429/503/network-failure error states; duplicate-click guard; fully keyboard-only operation per User Story 4) and record results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story phase.
- **User Stories (Phases 3–7)**: All depend on Foundational completion. Each phase extends the same shared `chat.js`/`site.css` (and, for US5, re-verifies `base.html`), so edits within a story are sequential *within* that story; the phases are intended to be implemented in priority order (P1 → P5) per this project's established single-developer workflow (feature 005's precedent), though each remains independently testable on its own once its predecessor lands.
- **Polish (Phase 8)**: Depends on all desired user story phases being complete.

### Within Each User Story

- Tests are written first and confirmed failing before the corresponding implementation task.
- Within `chat.js`, later tasks in a story build directly on earlier ones in the same story (same file, sequential) — noted per task above where it applies.
- Story complete and its own tests green before moving to the next priority.

### Parallel Opportunities

- T004 and T005 (CSS and `chat.js` skeleton) can run in parallel once T003 (`base.html` markup) exists — different files, neither depends on the other's content.
- Within each user story phase, the test-writing task marked `[P]` can start as soon as the previous story's implementation is complete (it is a distinct file from every implementation task) and must be confirmed failing before that story's implementation tasks begin.
- T027 and T028 (Polish) can run in parallel with each other.

---

## Parallel Example: Foundational chassis

```bash
# After T003 (base.html markup) is done:
Task: "Add baseline widget CSS to src/albercik_chatbot/public_site/static/css/site.css"
Task: "Create src/albercik_chatbot/public_site/static/js/chat.js with the open/close skeleton"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1 (grounded answer flow).
4. **STOP and VALIDATE**: open the launcher on any page and ask a known-answerable question, per its Independent Test above.
5. Deploy/demo if ready — a widget that answers real questions with sources is a credible, demonstrable MVP on its own.

### Incremental Delivery

1. Setup + Foundational → shared launcher/panel chassis exists, styled, on every page, opens/closes.
2. Add User Story 1 → validate independently → this is the MVP.
3. Add User Story 2 (honest scope/insufficient-info handling) → validate independently — protects the widget's credibility.
4. Add User Story 3 (error resilience) → validate independently — the most visible way this feature could otherwise embarrass the site.
5. Add User Story 4 (full keyboard/screen-reader operability) → validate independently.
6. Add User Story 5 (no-JS non-regression) → validate independently — mostly a verification pass on guarantees already built in.
7. Phase 8 Polish → full-suite + quickstart + quality-gate verification.

### Notes

- No parallel-team story split is recommended, matching feature 005's established precedent: every story after US1 extends the same shared `chat.js` and (for US4) the same shared `site.css` selectors, so sequential P1→P5 delivery avoids merge conflicts, even though each story remains independently testable once its predecessor lands.
- This feature's entire implementation surface is two edited files (`base.html`, `site.css`) and one new file (`chat.js`) — no new Python module, no new route, no new dependency.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently before moving to the next.
- Avoid: vague tasks, same-file conflicts within a phase, cross-story dependencies that would break a story's independent testability.
