---

description: "Task list for feature implementation"
---

# Tasks: Conversational UX for Public Chat

**Input**: Design documents from `/specs/007-conversational-chat-ux/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/small-talk-classification-contract.md, quickstart.md

**Tests**: Included — spec.md's Testing requirements section explicitly requires automated proof of 20 numbered behaviors, so test tasks are part of every relevant phase, written before the implementation task(s) they validate.

**Organization**: Tasks are grouped by user story (spec.md priorities: US1/US2 = P1, US3/US5 = P2, US4 = P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US5)
- File paths are exact and relative to the repository root

## Path Conventions

Single project (existing `albercik-chatbot` layout, extended in place — see plan.md's Project Structure):
- Backend: `src/albercik_chatbot/{domain,application,api}/`
- Widget: `src/albercik_chatbot/public_site/{templates,static/css,static/js,static/img}/`
- Tests: `tests/{unit,contract}/`

---

## Phase 1: Setup

**Purpose**: Confirm a clean starting point. This feature adds no new dependency, config, or directory structure that isn't created by a later story task, so Setup is deliberately minimal.

- [X] T001 Run `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests` at the repository root and confirm the entire pre-existing suite passes cleanly before any change (establishes the SC-008 regression baseline)

**Checkpoint**: Baseline green. Safe to start Foundational work.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared plumbing every user story depends on — the additive `small_talk` outcome value and the classifier scaffold/pipeline hook. No story-specific reply content or patterns yet; this phase leaves `classify_small_talk()` matching nothing (always returns `None`), so it is safe and behavior-preserving on its own.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `"small_talk"` to the `Outcome` Literal type in `src/albercik_chatbot/application/ask_question.py`
- [X] T003 [P] Add `"small_talk"` to `ChatResponse.outcome`'s Literal type in `src/albercik_chatbot/api/schemas.py`
- [X] T004 [P] Create `src/albercik_chatbot/domain/small_talk.py`, mirroring `src/albercik_chatbot/domain/scope.py`'s structure: a `SmallTalkCategory` Literal type (`"greeting" | "goodbye" | "thanks" | "courtesy" | "capability" | "identity"`), a `_normalize(question: str) -> str` helper (lowercase, trim whitespace/trailing punctuation), a `_PATTERNS: dict[SmallTalkCategory, tuple[re.Pattern[str], ...]]` registry (empty per category for now), a `_REPLIES: dict[SmallTalkCategory, str]` registry (empty for now), `classify_small_talk(question: str) -> SmallTalkCategory | None` (whole-normalized-message anchored match against `_PATTERNS`, per research.md §2), and `small_talk_reply(category: SmallTalkCategory) -> str` (looks up `_REPLIES`)
- [X] T005 Wire the short-circuit into `ask_question()` in `src/albercik_chatbot/application/ask_question.py`: call `classify_small_talk(question)` immediately after the concurrency guard is acquired and before `is_albertos_scope(question)`; on a match, `return AskQuestionResult(outcome="small_talk", answer=small_talk_reply(category))` without touching embeddings/retrieval/the LLM (research.md §4) — depends on T002, T004
- [X] T006 [P] Add a case to `tests/contract/test_chat_no_client_override.py` proving a client-supplied field such as `"intent": "small_talk"` alongside `question` is still rejected with `400` by the existing `extra="forbid"` validation (testing requirement 17; contracts/small-talk-classification-contract.md's request-contract section)

**Checkpoint**: `small_talk` outcome plumbing exists end-to-end but is currently unreachable (no patterns registered yet) — `uv run pytest` still passes in full, unchanged, since no existing behavior is altered. User story implementation can now begin.

---

## Phase 3: User Story 1 - Visitor exchanges natural small talk with the assistant (Priority: P1) 🎯 MVP

**Goal**: Greetings, goodbyes, thanks, courtesy messages, and capability questions get short, friendly, deterministic replies instead of the "insufficient information" message, without invoking embeddings, retrieval, or the LLM.

**Independent Test**: `POST /api/v1/chat` with `{"question": "Cześć"}` (and the other four categories' example phrases) returns `200` + `outcome: "small_talk"` + a friendly reply; `fake_llm_provider.call_count == 0` and `fake_embedding_provider.embed_calls == []` after the call; no new `UsageRecord` row is created; a small-talk-shaped request still triggers the existing rate limiter/kill switch when those are exercised (SC-009).

### Tests for User Story 1

- [X] T007 [P] [US1] Create `tests/unit/test_small_talk_classifier.py` with a parametrized table (mirroring `tests/unit/test_scope.py`'s style) covering greeting/goodbye/thanks/courtesy/capability example phrases and common Polish + English variants from spec.md's Scope §1, asserting `classify_small_talk(...)` returns the expected category for each
- [X] T008 [P] [US1] Create `tests/contract/test_chat_small_talk.py` with HTTP-level tests for each of the five categories: `POST /api/v1/chat` → `200` + `outcome == "small_talk"` + non-empty `answer` + `sources == []`; assert `fake_llm_provider.call_count == 0`, `fake_embedding_provider.embed_calls == []`, and `session.query(UsageRecord).count() == 0` after each call (reusing `tests/conftest.py`'s `fake_llm_provider`/`fake_embedding_provider`/`db_session` fixtures)
- [X] T009 [US1] In `tests/contract/test_chat_small_talk.py`, add a test proving a small-talk-shaped request still counts against and can trigger the existing rate limiter (reuse the pattern from `tests/contract/test_chat_rate_limit.py`, pointed at `"Cześć"` instead of a real question) — SC-009
- [X] T010 [US1] In `tests/contract/test_chat_small_talk.py`, add a test proving the LLM kill switch / budget check still short-circuits a small-talk-shaped request to `outcome: "unavailable"` *before* small-talk classification would otherwise apply (reuse patterns from `tests/contract/test_chat_kill_switch.py` / `test_chat_budget.py`) — SC-009. Also added an equivalent concurrency-guard case in the same file (beyond the task's literal wording, to fully cover tasks.md's own "concurrency guard behavior is preserved" testing goal).

### Implementation for User Story 1

- [X] T011 [US1] Populate `_PATTERNS`/`_REPLIES` in `src/albercik_chatbot/domain/small_talk.py` for the `greeting`, `goodbye`, `thanks`, `courtesy`, and `capability` categories — whole-message-anchored regex patterns per research.md §2, canned Polish reply text per research.md §5 matching spec.md's worked examples verbatim where given — depends on T004; makes T007/T008/T009/T010 pass
- [X] T012 [US1] Add an explicit `"small_talk"` branch to `handleResponse()` in `src/albercik_chatbot/public_site/static/js/chat.js`: `appendAndPersist("assistant", body.answer, [])` and return, alongside the existing `grounded`/`insufficient_information`+`out_of_scope`/`unavailable` branches (research.md §7a) — without this, a `small_talk` reply would incorrectly render as the generic fallback error. A companion static-source test was added to `tests/unit/test_chat_widget_client_script.py` (written first, confirmed failing, then this task made it pass).
- [X] T013 [US1] Update the in-flight status text in `src/albercik_chatbot/public_site/static/js/chat.js` (currently `"Albertos AI pisze odpowiedź…"`) — depends on T012 touching the same file; kept here since it is required for US1's own natural-feel goal and has no dependency on identity-question work in US3. Changed to `"Asystent Albertos pisze odpowiedź…"`; `base.html`'s panel title is intentionally left as `"Albertos AI"` (that rename is T020, User Story 3, out of this session's scope).

**Checkpoint**: Sending a greeting/thanks/goodbye/courtesy/capability message through the public widget or the raw API now produces a natural reply with zero retrieval/LLM cost, and existing safeguards still apply. This alone is a viable, demoable MVP increment.

---

## Phase 4: User Story 2 - Visitor asks a real question phrased with a greeting or courtesy opener (Priority: P1)

**Goal**: A message that opens with small talk but asks a genuine factual question is routed through the normal RAG pipeline, never swallowed by the small-talk short-circuit.

**Independent Test**: `POST /api/v1/chat` with `{"question": "Cześć, o której są treningi początkujących w Wierzbinie?"}` returns the same `outcome`/`answer` as the same question asked without the "Cześć, " prefix (grounded or insufficient_information, per seeded content) — never `outcome: "small_talk"`.

### Tests for User Story 2

- [X] T014 [P] [US2] In `tests/unit/test_small_talk_classifier.py`, add a parametrized "must NOT classify as small talk" table covering spec.md's worked negative examples ("Cześć, o której jest trening w Wierzbinie?", "Dzięki, a kiedy jest następny egzamin?") plus additional combined greeting/thanks+question variants, asserting `classify_small_talk(...) is None` for each. Extended the existing negative table (from T007) with 5 new US2-specific cases, including two *suffix* variants (small-talk phrase trailing the question) not previously covered.
- [X] T015 [US2] In `tests/contract/test_chat_small_talk.py`, add tests proving combined greeting/thanks+question messages are routed through the normal RAG pipeline unchanged — `outcome` is `"grounded"` or `"insufficient_information"` as appropriate (reuse the seeded-chunk fixture pattern from `tests/contract/test_chat.py`), and `fake_embedding_provider.embed_calls` is non-empty, proving retrieval *was* invoked for these messages
- [X] T016 [US2] In `tests/contract/test_chat_small_talk.py`, add a regression test confirming `insufficient_information` and `out_of_scope` outcomes for factual/off-topic questions with no small-talk prefix are byte-for-byte unchanged from pre-feature behavior (FR-005, SC-003)

### Implementation for User Story 2

- [X] T017 [US2] Review the whole-message anchoring and any filler-word allowances in `src/albercik_chatbot/domain/small_talk.py` (populated by T011) against T014's negative table; tighten patterns if any combined-message case incorrectly matches — depends on T011, T014. **Review outcome: no production code change was needed.** All T014 cases (including new suffix and combined-category cases) passed against the existing `fullmatch`-anchored implementation on the first run — the design's conservative-by-construction property (a mismatch anywhere falls through to `None`, never a false positive) already satisfies US2 completely. Documented this checkpoint directly in `domain/small_talk.py`'s module docstring rather than modifying any pattern.

**Checkpoint**: User Stories 1 and 2 together fully prove the classifier's safe boundary — small talk is handled naturally, and real questions are never swallowed by it.

---

## Phase 5: User Story 3 - Visitor learns the assistant's identity without being misled (Priority: P2)

**Goal**: Direct "are you human?"/"what are you?" questions get a clear, deterministic, non-LLM answer identifying the assistant as a virtual Albertos assistant; the widget's own chrome consistently presents a non-technical "Asystent Albertos" identity.

**Independent Test**: `POST /api/v1/chat` with `{"question": "Czy jesteś człowiekiem?"}` returns `outcome: "small_talk"` with reply text that states it is a virtual assistant and does not claim to be human, with zero LLM/embedding calls; the rendered panel title reads "Asystent Albertos" and no "AI chatbot"/"LLM"/"RAG"/"Ollama" string appears in visitor-facing markup.

### Tests for User Story 3

- [X] T018 [P] [US3] In `tests/unit/test_small_talk_classifier.py`, add a parametrized table for identity-question phrases ("Czy jesteś człowiekiem?", "Czy rozmawiam z człowiekiem?", "Kim jesteś?", "Co to jest?" and variants), asserting `classify_small_talk(...)` returns `"identity"` for each. Also added 3 mixed-intent negative cases ("Kim jesteś i kiedy są treningi?" etc.) to the existing negative table.
- [X] T019 [P] [US3] In `tests/contract/test_chat_small_talk.py`, add a test for an identity question: `outcome == "small_talk"`, `answer` text asserts it does NOT contain human/employee/instructor-claiming language and DOES state it is a virtual Albertos assistant, `fake_llm_provider.call_count == 0`. Also added a contract-level mixed-intent test (identity + real question → `grounded`, never `small_talk`).
- [X] T020 [P] [US3] Extend `tests/contract/test_public_site_chat_widget.py`: assert the panel title element reads "Asystent Albertos" (not "Albertos AI"), and assert none of the literal strings "AI chatbot", "LLM", "RAG", "Ollama" appear anywhere in the rendered markup of any of the 8 public pages

### Implementation for User Story 3

- [X] T021 [US3] Add the `identity` category's regex patterns and canned reply to `src/albercik_chatbot/domain/small_talk.py`'s `_PATTERNS`/`_REPLIES`, matching spec.md's worked example wording ("Nie — jestem wirtualnym Asystentem Albertos...") — depends on T011/T017 (same file)
- [X] T022 [P] [US3] Rename the panel title from "Albertos AI" to "Asystent Albertos" in `src/albercik_chatbot/public_site/templates/base.html`
- [X] T023 [P] [US3] Confirm/update the in-flight status text in `src/albercik_chatbot/public_site/static/js/chat.js` (set by T013) is fully non-technical and consistent with "Asystent Albertos" (no residual "Albertos AI"/"AI" wording). **Verification only — no change needed**: T013 had already set it to `"Asystent Albertos pisze odpowiedź…"`, and a repo-wide grep found no other "Albertos AI"/standalone "AI" occurrence in `chat.js` or `base.html` (the only "AI" substring match is "WAI-ARIA" in a code comment, not visitor-facing).

**Checkpoint**: Identity questions are answered naturally and honestly; the widget's own presentation is consistent with that identity everywhere.

---

## Phase 6: User Story 4 - Visitor sees a recognizable assistant avatar (Priority: P3)

**Goal**: A small, simple, non-robot, on-brand avatar appears on the launcher and assistant messages, is decorative for assistive technology, and never blocks the widget if it fails to load.

**Independent Test**: Load any public page — the launcher shows the avatar; open the panel and ask a question — the assistant's reply bubble shows the same avatar; inspecting the accessibility tree shows the avatar is not separately announced; blocking the avatar asset in devtools leaves the widget fully functional with no broken-image glyph.

### Tests for User Story 4

- [X] T024 [P] [US4] Extend `tests/contract/test_public_site_chat_widget.py`: assert an avatar element is present on the launcher, marked `aria-hidden="true"`, and its styling references a local static asset path under `/static/site/img/` (no external/CDN URL). Added 4 tests: asset-exists, launcher-element+aria-hidden+accessible-name-preserved, CSS-references-local-asset-only, CSS-has-background-color-fallback.
- [X] T025 [P] [US4] Extend `tests/unit/test_chat_widget_client_script.py`: static-source assertions that `chat.js` constructs a decorative avatar element (`aria-hidden="true"`) for assistant message bubbles, and that avatar rendering uses the CSS-`background-image`-on-a-`<span>` approach (no bare `<img>` with an unhandled failure mode) per research.md §6. Added a brace-matching `_function_body()` helper so the assertion inspects actual `renderMessage()` DOM-construction code (className/setAttribute calls), not a substring match that a comment could satisfy.

### Implementation for User Story 4

- [X] T026 [P] [US4] Create `src/albercik_chatbot/public_site/static/img/assistant-avatar.svg` — a simple, non-robot, Japanese-inspired decorative mark consistent with `site.css`'s `--accent: #b3382c`. Design: an abstract "enso" (incomplete Zen circle / brushstroke), matching the site's existing minimalist circular brand mark — fully abstract, no face, no robot.
- [X] T027 [US4] Add avatar markup (`<span class="chat-avatar" aria-hidden="true">`) to the launcher button in `src/albercik_chatbot/public_site/templates/base.html` — depends on T026 for the asset path it references. Replaced the previous inline speech-bubble SVG icon (no test asserted its presence) to avoid two competing icons on one small button.
- [X] T028 [P] [US4] Add `.chat-avatar` rules to `src/albercik_chatbot/public_site/static/css/site.css`: fixed size, `background-image: url(...)` pointing at the new SVG, a `background-color` fallback on the same rule so a failed image load still shows a neutral shape, no dependency on the image loading successfully for layout — depends on T026. Also added `.chat-message-row` (flex wrapper placing the avatar beside the assistant bubble) and a `.chat-launcher .chat-avatar` size/border override.
- [X] T029 [US4] Add a matching decorative avatar element to each assistant message bubble in `renderMessage()`, `src/albercik_chatbot/public_site/static/js/chat.js` — depends on T028 (CSS class must exist). User messages are unaffected (no row wrapper, no avatar) — only `role === "assistant"` gets the new `.chat-message-row` + `.chat-avatar` treatment.

**Checkpoint**: Avatar visible on launcher and assistant messages, accessible, fails gracefully.

---

## Phase 7: User Story 5 - Visitor no longer sees technical source labels (Priority: P2)

**Goal**: The public widget never renders a "Źródła: ..." line or any source filename/chunk identifier, for any outcome — while the backend response still carries `sources` unchanged.

**Independent Test**: Ask a question that produces a grounded answer with sources — the rendered panel shows only the answer text, with no source line anywhere; inspecting the raw network response for the same request shows `sources` still populated.

### Tests for User Story 5

- [X] T030 [P] [US5] Extend `tests/unit/test_chat_widget_client_script.py`: static-source assertion that no `"Źródła"` string literal (or equivalent sources-joining/rendering call) remains reachable from any branch of `chat.js`. Added 2 tests: a whole-file "Źródła"/`dedupeSourceLabels` absence check, and a `renderMessage(...)` signature check (`["role", "text"]` — the `sources` parameter itself removed, not merely unused).
- [X] T031 [P] [US5] Run and confirm `tests/contract/test_chat.py`'s existing grounded-answer assertion on the response's `sources` field continues to pass unmodified — record as the regression proof that the backend contract is untouched (SC-004's backend half; FR-014). **Verification only, no test/code change**: `git diff --stat tests/contract/test_chat.py` is empty; `test_grounded_answer_includes_source` (asserting `body["sources"] == [{"document_id": ..., "label": "godziny.txt"}]`) passes unmodified.

### Implementation for User Story 5

- [X] T032 [US5] In `src/albercik_chatbot/public_site/static/js/chat.js`, remove the sources-rendering branch from `renderMessage()` (drop the `sources` parameter/the `"Źródła: " + sources.join(...)` element) and delete the now-dead `dedupeSourceLabels()` helper and its call site — depends on T012 (same function touched for the new `small_talk` branch; sequence after to avoid merge conflicts within the same edit). Also removed `sources` from `appendAndPersist()`'s signature and every one of its 8 call sites, and from the `ChatSession` history-replay/storage shape, per data-model.md's decision that the client-side shape drops the field entirely (not just stops rendering it). Also deleted the now-dead `.chat-message__sources` rule from `site.css` (nothing constructs that class any more).

**Checkpoint**: Public widget never shows source labels for any outcome; backend response still carries them unchanged for future admin/observability tooling.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final end-to-end validation across all five user stories.

- [X] T033 [P] Run quickstart.md's Scenarios 1–7 against the running stack (`docker compose up -d`) and record results, including the manual browser-based avatar/identity/no-sources checks (Scenario 5) and the offline-avatar failure check. **Executed**: Prerequisites + Scenarios 1, 2, 3, 4, 7 fully executed against a freshly rebuilt `docker compose` stack (`docker compose build app && docker compose up -d`) and the automated suite — all as specified. Scenario 5's curl/static-verifiable facts (avatar markup, panel title, absence of technical terms, avatar SVG served, `.chat-avatar` CSS fallback, `sources` present in the raw API response, no source-label string in `chat.js`) and the JS-disabled non-regression (all 8 pages return 200) were verified live. **Not executed — genuinely require a real browser, honestly reported as not run**: Scenario 5 steps requiring actual visual rendering, DevTools Network-tab request blocking, and Accessibility Tree/screen-reader inspection; all of Scenario 6 (sessionStorage transcript persistence across page navigation, which requires a real browser tab). These remain covered only by the passing structural/static tests plus quickstart.md's documented manual procedure for a human to run — not claimed as tested here.
- [X] T034 Run `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && docker compose config` and confirm 100% pass — every pre-existing test file (contract/test_chat*.py, unit/test_scope.py, etc.) passes unmodified alongside all new/extended tests from Phases 2–7 (SC-008) — depends on all prior phases. **Result**: 499/499 passed, `ruff check` clean, `ruff format --check` clean (122 files), `mypy src tests` clean (115 files), `docker compose config` valid (exit 0).
- [X] T035 [P] Re-read the Constitution Check table in `specs/007-conversational-chat-ux/plan.md` against the final diff and confirm it still holds as written (no new dependency, no new endpoint, no new database table, exactly one additive outcome value) — update the plan only if something actually drifted during implementation. **Result: no drift.** Verified via `git diff` against `pyproject.toml`/`uv.lock` (empty), `alembic/`+`persistence/models.py` (untouched), `api/routers/` (untouched), and `api/schemas.py` (exactly the one promised additive `Literal` change). Appended a "Post-implementation re-check (T035)" note to `plan.md` recording this.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — no dependency on other stories; delivers the MVP
- **User Story 2 (Phase 4)**: Depends on Foundational; its implementation task (T017) depends on US1's T011 populating the categories it tightens — cannot start meaningfully before US1's classifier content exists, though its test-writing (T014) can be drafted in parallel
- **User Story 3 (Phase 5)**: Depends on Foundational; T021 depends on US1/US2's `small_talk.py` state (same file, additive) — implement after US1, independent of US2's own outcome
- **User Story 4 (Phase 6)**: Depends on Foundational only — fully independent of US1/US2/US3/US5 (avatar work touches no classifier logic); could be implemented in parallel with US1–US3/US5 by a different contributor
- **User Story 5 (Phase 7)**: Depends on Foundational; T032 sequenced after US1's T012 (both edit `chat.js`'s response-handling area) to avoid rework, but is otherwise independent in behavior
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### Within Each User Story

- Tests are written first and MUST fail before their corresponding implementation task
- `domain/small_talk.py` category population is strictly sequential across US1 → US2 (tightening) → US3 (new category), since all three edit the same file's registries
- `chat.js` edits are sequential across US1 (new outcome branch) → US4 (avatar) → US5 (remove sources) for the same reason

### Parallel Opportunities

- T002, T003, T004, T006 (Phase 2) can all run in parallel — four different files, no cross-dependency
- T007 and T008 (Phase 3 tests) can run in parallel — different files
- T014 (Phase 4) can be drafted in parallel with Phase 3 work — different file section, though its implementation counterpart (T017) must wait for T011
- T018, T019, T020 (Phase 5 tests) can all run in parallel — three different files
- T024, T025, T026 (Phase 6) can run in parallel — different files; T028 can join once T026 exists
- T030, T031 (Phase 7 tests) can run in parallel — different files
- **User Story 4 as a whole (Phase 6) has no file overlap with US1/US2/US3/US5's `domain/small_talk.py` work** and only touches `chat.js` in a distinct region (avatar rendering) from US1/US5's edits — a second contributor could implement all of Phase 6 concurrently with Phases 3–5 and 7, provided `chat.js` edits are merged sequentially at the end

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all independent foundational tasks together:
Task: "Add \"small_talk\" to the Outcome Literal type in src/albercik_chatbot/application/ask_question.py"
Task: "Add \"small_talk\" to ChatResponse.outcome's Literal type in src/albercik_chatbot/api/schemas.py"
Task: "Create src/albercik_chatbot/domain/small_talk.py scaffold (types, normalize helper, empty registries, classify/reply functions)"
Task: "Add a client-override-rejection case to tests/contract/test_chat_no_client_override.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (greeting/goodbye/thanks/courtesy/capability small talk)
4. **STOP and VALIDATE**: `POST /api/v1/chat` with `{"question": "Cześć"}` returns a friendly `small_talk` reply with zero LLM/embedding calls; full suite still green
5. Deploy/demo if ready — this alone already fixes the core "Hi" → "I don't have enough information" problem from the spec

### Incremental Delivery

1. Setup + Foundational → foundation ready, behavior-preserving
2. + User Story 1 → small talk works, zero-cost → Deploy/Demo (MVP!)
3. + User Story 2 → greeting-prefixed real questions proven safe → Deploy/Demo
4. + User Story 3 → identity questions + consistent "Asystent Albertos" naming → Deploy/Demo
5. + User Story 5 → source labels hidden from the public → Deploy/Demo
6. + User Story 4 → avatar polish → Deploy/Demo
7. Polish phase → full regression + quickstart sign-off

### Suggested Team Split (if parallelized)

- Developer A: Phase 2 (Foundational) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) — all `domain/small_talk.py`-centric, naturally sequential for one person
- Developer B: Phase 6 (US4, avatar) — fully independent once Phase 2 lands
- Developer C: Phase 7 (US5, hide sources) — independent once Phase 2 lands, light sequencing with Developer A's `chat.js` change from US1 (T012)
