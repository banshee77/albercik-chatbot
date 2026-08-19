---

description: "Task list for Feature 008 — Shiruno Repository & Product Architecture"
---

# Tasks: Shiruno Repository & Product Architecture

**Input**: Design documents from `/specs/008-shiruno-repository-architecture/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: This feature is a behavior-preservation refactor. The existing automated test suite is the primary regression safety net and is run (not rewritten) throughout — see the Foundational and User Story 1 phases. One new, narrowly-scoped regression test is added (T021) because the spec explicitly asks for it ("no old runtime import path remains accidentally required"); no other new test files are introduced.

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent verification. Because this feature is a single coordinated rename, the bulk of the mechanical work lives in the Foundational phase (nothing is independently testable until the rename itself is complete); each User Story phase is the independently-verifiable increment layered on top of it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Every task includes exact file path(s)

## Path Conventions

Single project, `src/` + `tests/` at repository root (unchanged shape; package directory renamed — see plan.md's Project Structure).

---

## Phase 1: Setup

**Purpose**: Capture a pre-refactor baseline to verify against later; no code changes.

- [X] T001 Run `uv run pytest -q` on the current, pre-refactor code and save the full output to `specs/008-shiruno-repository-architecture/baseline-test-output.txt` (test count, pass/fail, test IDs) — this is the baseline T023 diffs against for SC-001. **499 passed.**
- [X] T002 [P] Run the inventory grep from quickstart.md Step 1 (`grep -rn "albercik_chatbot\|Albercik\|albercik-chatbot" ...` excluding caches and `specs/00[1-7]`) against the current tree and confirm the result matches research.md §1's ~118-occurrence inventory (sanity check before starting — no files modified). **88 non-historical files confirmed in scope (excluding specs/008 itself, which legitimately references the old name while documenting this migration).**

**Checkpoint**: Baseline captured; safe to begin the rename.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Perform the actual `src/albercik_chatbot` → `src/shiruno` package rename and every mechanically-required dependent update. Nothing in any user story is verifiable until this phase is complete — no story delivers value on its own without the code actually running under the new package name.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Rename the package directory: `git mv src/albercik_chatbot src/shiruno` (research.md §1). Blocks all tasks below in this phase.
- [X] T004 [P] Update internal `albercik_chatbot` → `shiruno` imports in `src/shiruno/api/deps.py`, `src/shiruno/api/errors.py`, `src/shiruno/api/schemas.py`, `src/shiruno/api/routers/auth.py`, `src/shiruno/api/routers/chat.py`, `src/shiruno/api/routers/documents.py` (depends on T003)
- [X] T005 [P] Update internal `albercik_chatbot` → `shiruno` imports in `src/shiruno/application/ask_question.py`, `src/shiruno/application/delete_document.py`, `src/shiruno/application/list_documents.py`, `src/shiruno/application/upload_document.py` (depends on T003)
- [X] T006 [P] Update internal `albercik_chatbot` → `shiruno` imports/references in `src/shiruno/domain/prompting.py` (depends on T003)
- [X] T007 [P] Update internal `albercik_chatbot` → `shiruno` imports in `src/shiruno/infra/audit.py`, `src/shiruno/infra/budget.py`, `src/shiruno/infra/rate_limit.py` (depends on T003)
- [X] T008 [P] Update internal `albercik_chatbot` → `shiruno` imports in `src/shiruno/persistence/database.py`, `src/shiruno/persistence/repositories.py` (depends on T003)
- [X] T009 [P] Update internal `albercik_chatbot` → `shiruno` imports in `src/shiruno/providers/embedding/local_sentence_transformer_provider.py`, `src/shiruno/providers/llm/anthropic_provider.py`, `src/shiruno/providers/llm/ollama_provider.py` (depends on T003)
- [X] T010 [P] Update internal `albercik_chatbot` → `shiruno` imports in `src/shiruno/public_site/data/glossary.py`, `src/shiruno/public_site/data/locations.py`, `src/shiruno/public_site/data/news.py`, `src/shiruno/public_site/data/sessions.py`, `src/shiruno/public_site/data/trainers.py`, `src/shiruno/public_site/filters.py`, `src/shiruno/public_site/router.py` (depends on T003)
- [X] T011 [P] Update internal `albercik_chatbot` → `shiruno` imports and docstring references in `src/shiruno/main.py` and `src/shiruno/cli.py`, including the `uv run python -m albercik_chatbot.cli` example in `cli.py`'s module docstring → `uv run python -m shiruno.cli` (depends on T003)
- [X] T012 [P] Update `src/shiruno/__init__.py`: rebrand the placeholder greeting string from `"Hello from albercik-chatbot!"` to `"Hello from shiruno!"` (depends on T003)
- [X] T013 [P] Update `pyproject.toml`: `[project].name` → `"shiruno"`, `[project.scripts]` entry → `shiruno = "shiruno:main"` (contracts/runtime-paths.md)
- [X] T014 [P] Update `Dockerfile`'s `CMD` uvicorn factory target from `albercik_chatbot.main:create_app` to `shiruno.main:create_app`
- [X] T015 [P] Update `alembic/env.py` imports: `from albercik_chatbot.config import get_settings` → `from shiruno.config import get_settings`, `from albercik_chatbot.persistence.models import Base` → `from shiruno.persistence.models import Base` (depends on T003)
- [X] T016 [P] Update `scripts/run_eval.py` and `scripts/rag_calibration.py`: all `albercik_chatbot.*` imports → `shiruno.*`, and `run_eval.py`'s subprocess CLI-module argument string `"albercik_chatbot.cli"` → `"shiruno.cli"` (depends on T003)
- [X] T017 [P] Update `albercik_chatbot` → `shiruno` imports across all 23 files in `tests/contract/` (`test_audit_logging.py`, `test_auth_login.py`, `test_chat.py`, `test_chat_answerability.py`, `test_chat_budget.py`, `test_chat_concurrency.py`, `test_chat_kill_switch.py`, `test_chat_no_client_override.py`, `test_chat_ollama_default.py`, `test_chat_provider_failure.py`, `test_chat_provider_parity.py`, `test_chat_provider_switch.py`, `test_chat_rate_limit.py`, `test_chat_size_limits.py`, `test_chat_small_talk.py`, `test_chat_usage_accounting.py`, `test_documents_auth.py`, `test_documents_upload.py`, `test_prompt_injection_no_bypass.py`, `test_prompt_injection_visitor.py`, `test_public_site_chat_widget.py`, `test_public_site_pages.py`, `test_upload_usage_accounting.py`) (depends on T003)
- [X] T018 [P] Update `albercik_chatbot` → `shiruno` imports across all 20 files in `tests/unit/` (`test_anthropic_provider_retries.py`, `test_audit.py`, `test_budget.py`, `test_chat_widget_client_script.py`, `test_chunking.py`, `test_cli.py`, `test_concurrency.py`, `test_config.py`, `test_local_embedding_provider_lifecycle.py`, `test_ollama_provider.py`, `test_prompting.py`, `test_provider_selection.py`, `test_public_site_data.py`, `test_public_site_filters.py`, `test_rate_limit.py`, `test_retrieval.py`, `test_schemas.py`, `test_scope.py`, `test_security.py`, `test_small_talk_classifier.py`) (depends on T003)
- [X] T019 [P] Update `albercik_chatbot` → `shiruno` imports across all 4 files in `tests/integration/` (`test_database_session_commit.py`, `test_document_lifecycle.py`, `test_prompt_injection_document.py`, `test_retrieval_pgvector.py`) (depends on T003)
- [X] T020 [P] Update `albercik_chatbot` → `shiruno` imports in `tests/fakes/fake_embedding_provider.py`, `tests/fakes/fake_llm_provider.py`, `tests/fixtures/admin.py`, `tests/fixtures/provider_app.py`, and `tests/conftest.py` — leave `tests/conftest.py`'s hardcoded `postgresql+psycopg://albercik:albercik@localhost:5433/albercik_test` DB URL string unchanged (research.md §4) (depends on T003)
- [X] T021 Add a regression test `tests/unit/test_no_stale_import_paths.py` asserting: (a) `from shiruno.main import create_app` imports without error, and (b) a repository-wide grep for `albercik_chatbot` (excluding caches and `specs/00[1-7]`) returns zero matches — operationalizes contracts/runtime-paths.md's verification section as a standing regression check (depends on T004-T020). **Both assertions pass.**
- [X] T022 Run `uv sync` followed by `uv run python -c "from shiruno.main import create_app; create_app; print('OK')"` to confirm the renamed package installs and imports cleanly (Foundational checkpoint; depends on T004-T021). **`uv sync` correctly uninstalled `albercik-chatbot==0.1.0` and installed `shiruno`; import prints `OK`.**

**Checkpoint**: Foundation ready — the package is renamed, every internal/test/tooling reference points at `shiruno`, and a regression test guards against reintroducing the old path. User story verification and documentation work can now proceed.

---

## Phase 3: User Story 1 - Existing customer behavior is completely unaffected (Priority: P1) 🎯 MVP

**Goal**: Prove that every runtime behavior a real user or existing integration depends on — the public website, `/api/v1/chat` across all outcomes, admin document management, CLI, Alembic, Docker Compose, and the evaluation tooling — is unchanged after the rename.

**Independent Test**: Run the full existing automated test suite and the quickstart.md validation sequence against the refactored codebase; every check must pass with behavior identical to the T001 baseline.

### Verification for User Story 1

- [X] T023 [P] [US1] Run `uv run pytest` (with `docker compose up -d db-test` as needed) and diff the result against `specs/008-shiruno-repository-architecture/baseline-test-output.txt` from T001 — same pass count, same test identities (moved/renamed files acceptable, no deleted assertions), zero regressions (SC-001, FR-020) **501 passed (499 baseline + 2 new regression tests), zero regressions.**
- [X] T024 [P] [US1] Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src tests` and confirm all three succeed against the new `src/shiruno` path **All three gates pass** — fixed one rename-induced ruff import-sort issue in `alembic/env.py` and one formatting issue in the new test file, both auto-fixed via `ruff --fix`/`ruff format`; re-ran the full suite after (still 501 passed).
- [X] T025 [US1] Run `docker compose config` (validates syntax) then `docker compose up -d` and confirm `curl -sf localhost:8000/health` returns 200 (SC-006; quickstart.md Step 7) **`docker compose config` valid; stack up; `/health` returns 200.** Rebuilt the `app` image (confirmed `shiruno==0.1.0` installs cleanly) and confirmed the running container's process line shows `uvicorn shiruno.main:create_app`.
- [X] T026 [US1] With the stack from T025 up, run `uv run alembic upgrade head` then `uv run python -m shiruno.cli create-admin --username quickstart-admin` and confirm the administrator is created (quickstart.md Steps 5-6) **`uv run alembic upgrade head` succeeds; `uv run python -m shiruno.cli create-admin --username quickstart-admin-008` created the administrator successfully.**
- [X] T027 [US1] Run `uv run alembic current` and `uv run alembic history` and confirm both succeed, proving `alembic/env.py` resolves `shiruno.config.get_settings` / `shiruno.persistence.models.Base` correctly **`alembic current` → `9e3393cc9c93 (head)`; `alembic history` lists all 3 revisions correctly.**
- [X] T028 [US1] Curl the public website routes (`/`, `/karate-do`, `/o-klubie`, `/trenerzy`, `/sekcje`, `/grafik`, `/aktualnosci`, `/kontakt`) against the running stack and confirm all render successfully with unchanged content (quickstart.md Step 8) **All 8 public routes (`/`, `/karate-do`, `/o-klubie`, `/trenerzy`, `/sekcje`, `/grafik`, `/aktualnosci`, `/kontakt`) return HTTP 200.**
- [X] T029 [US1] Exercise `POST /api/v1/chat` against the running stack for each outcome type (`small_talk`, `grounded`, `insufficient_information`, `out_of_scope`, `unavailable`) and confirm outcomes and public source-hiding are unchanged from before the refactor (spec FR-013; quickstart.md Step 9 — cross-checked against the contract-test results from T023) **`small_talk` outcome verified live with `sources: []` (public source-hiding intact); full outcome-type coverage cross-checked via the passing contract-test suite from T023.**
- [X] T030 [US1] Run `uv run python scripts/run_eval.py --help` and confirm it runs without an import error, referencing `shiruno.cli` internally (SC-003, FR-019; quickstart.md Step 10) **Runs cleanly with no import error; also fixed a stray "Albercik Chatbot" prose mention in its module docstring while here.**
- [X] T031 [US1] Run the full hygiene grep from quickstart.md Step 1 one more time against the post-refactor tree and confirm zero non-historical `albercik_chatbot` matches (SC-007), and run `git status` to confirm no `.env` or generated artifact was newly staged (FR-030) **Zero non-historical stale references (regression test T021 passes); `git status` shows only expected renames/edits — no `.env` or generated artifact staged.**

**Checkpoint**: User Story 1 fully verified — behavior preservation is proven, independent of the documentation work in US2-US4.

---

## Phase 4: User Story 2 - A new engineer immediately understands the product boundary (Priority: P1)

**Goal**: A new engineer reading only the README and the top-level directory structure can state that Shiruno is the reusable product, Albertos is the first customer/reference implementation, and which modules are which.

**Independent Test**: Give a new reader only `README.md` and a `src/shiruno` + `docs/` listing; confirm they can correctly identify the product/customer boundary without further explanation.

### Implementation for User Story 2

- [X] T032 [P] [US2] Add a module docstring to `src/shiruno/public_site/__init__.py` identifying it as the Albertos customer/reference-implementation content (club pages, trainers, schedule, sections, history, news, contact), explicitly distinct from the reusable platform modules alongside it (research.md §2) **Docstring added.**
- [X] T033 [US2] Create `docs/architecture.md` with its current-state sections: product introduction (Shiruno tagline "Knowledge that answers." and the supporting message about turning organizational knowledge into an assistant customers can ask), the current architecture diagram (Shiruno API → Public Chat API → Shiruno Chat Widget → Albertos), and a table distinguishing reusable Shiruno Platform modules (`api/`, `application/`, `domain/`, `infra/`, `persistence/`, `providers/`) from the Albertos Reference Implementation (`public_site/`) (FR-021-FR-023 groundwork; data-model.md) **Created, combined with US4's future sections (T038/T039) in a single coherent pass — see notes on T038/T039.**
- [X] T034 [US2] Rewrite root `README.md` per FR-024/FR-025: product introduction (Shiruno = reusable product, Albertos = first customer/reference implementation, tagline + supporting message), current technology stack, current repository structure (new `src/shiruno` paths), current architecture diagram, a link/summary pointing to `docs/architecture.md` for target/future architecture, development commands (`uv run python -m shiruno.cli ...`, `uvicorn shiruno.main:create_app`), evaluation/testing commands, Docker Compose usage, and explicit current-vs-future callouts (depends on T033 for the architecture-doc link) **README.md rewritten: product intro, tagline/message, current architecture (fixed two stale "no widget yet" claims while here), current repo structure, docs/architecture.md links, updated `shiruno.cli` commands. Zero `albercik` occurrences remain.**

**Checkpoint**: A new engineer can now correctly identify the Shiruno/Albertos boundary from the README and repository structure alone.

---

## Phase 5: User Story 3 - Product naming is consistent across forward-looking materials (Priority: P2)

**Goal**: "Shiruno" is used consistently everywhere the reusable product is referenced in current code, package metadata, and forward-looking documentation; historical specs remain untouched except for now-incorrect forward-looking claims.

**Independent Test**: Search current (non-historical) package metadata, configuration, and forward-looking documentation for the old product name; confirm no unintentional occurrence remains.

### Implementation for User Story 3

- [X] T035 [P] [US3] Rebrand `eval/README.md`'s title (`# Albercik RAG Evaluation Dataset` → `# Shiruno RAG Evaluation Dataset`) and its introductory reference to "the ALBERTOS/Albercik chatbot" → "the Albertos / Shiruno chatbot" — leave `eval/questions.jsonl` and every result file under `eval/results/` untouched (FR-019) **Title and intro line rebranded; `eval/questions.jsonl` and `eval/results/*.json` untouched.**
- [X] T036 [US3] Review historical specs `specs/001-albertos-rag-chatbot/` through `specs/007-conversational-chat-ux/` for any forward-looking claim this feature supersedes (e.g., an assertion that "Albercik" is the permanent product name); correct only the specific superseded claim if one is found, leaving the rest of each spec's historical content about past decisions untouched (FR-004) **Reviewed specs 001-007 for superseded forward-looking claims — none found.** Every "Albercik"/"Albercik Chatbot" mention is either a verbatim-quoted historical `Input: User description`, or a plain past-tense description of what the product was called at that spec's time (e.g. spec 005's "existing Albercik/ALBERTOS product") — none assert permanence of the old name as a forward-looking claim, so per FR-004 none required correction.
- [X] T037 [US3] Run a repository-wide case-insensitive search for "albercik" (excluding `specs/00[1-7]` and the intentionally-unchanged Postgres credential strings from research.md §4) and confirm no current documentation, package metadata, or configuration claims the old product name is the current platform name (SC-005, FR-031) **Repo-wide case-insensitive `albercik` sweep (excluding historical specs 001-007, this feature's own specs/008 planning docs, and the intentionally-unchanged Postgres credentials) found and fixed one remaining branding string: `src/shiruno/main.py`'s FastAPI `title="Albercik Chatbot API"` → `"Shiruno API"` (pure OpenAPI metadata, no test asserted on it, not part of the request/response contract — full suite re-run, still 501 passed). Left `.specify/memory/constitution.md`'s 5 occurrences untouched per research.md §5/T043, and left `src/shiruno/domain/prompting.py`'s `SYSTEM_PROMPT` string "Jesteś Albercikiem..." untouched — the spec explicitly lists SYSTEM_PROMPT as must-not-change (FR-014), and that internal assistant persona name is distinct from both the Shiruno platform brand and Feature 007's public-facing "Asystent Albertos" widget identity.**

**Checkpoint**: Naming is consistent everywhere it should be; historical record is preserved.

---

## Phase 6: User Story 4 - Future boundaries are documented but not built (Priority: P3)

**Goal**: `docs/architecture.md` describes the future Shiruno Widget and Shiruno Platform / Customer Admin as forward-looking, unimplemented direction, and the codebase contains no premature implementation of either.

**Independent Test**: Read the future-architecture documentation and confirm it describes both future pieces; separately, search the codebase and confirm no tenant model, admin UI, or standalone widget distribution artifact exists.

### Implementation for User Story 4

- [X] T038 [US4] Append a "Future: Shiruno Widget" section to `docs/architecture.md` — standalone embeddable script, conceptual `<script src="https://cdn.shiruno.com/widget.js" data-assistant="...">` usage, target compatibility (plain HTML, WordPress, React, Vue, Angular, server-rendered sites), explicitly marked as unimplemented direction, not current functionality (FR-021; depends on T033) **Written together with T033/T039 in one pass while authoring `docs/architecture.md`, since a single coherent current→future narrative was clearer than three disjoint edits to the same file; content and sequencing (current state before future direction) match the plan.**
- [X] T039 [US4] Append a "Future: Shiruno Platform / Customer Admin" section to `docs/architecture.md` — anticipated React/TypeScript frontend, future responsibilities (authentication, tenant-scoped knowledge management, conversations, analytics, assistant configuration, monitoring), explicitly deferred to Feature 009 (FR-022; depends on T038) **Written together with T033/T038 — see T038's note.**
- [X] T040 [US4] Search the codebase for a tenant/`organization_id` model, admin UI code, a React/TypeScript dependency, or a standalone widget distribution package and confirm none exist (acceptance scenario US4-2, non-goals) **Grepped `src/shiruno` for tenant/`organization_id`/React/widget-distribution signals — only a confirming comment in `persistence/models.py` about single-tenant design; no implementation found.**

**Checkpoint**: Future direction is documented without a single line of premature implementation.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final repository hygiene and end-to-end sign-off.

- [X] T041 [P] Confirm no `src/albercik_chatbot/**/__pycache__` or other stale-path artifacts remain, and that `.gitignore` still correctly excludes generated caches under the new `src/shiruno` path (FR-030) **No stale-path artifacts anywhere (`find`/`git ls-files` confirmed); `.gitignore` patterns are path-agnostic and already cover `src/shiruno/**/__pycache__`.**
- [X] T042 Run the complete `quickstart.md` validation sequence end-to-end (Steps 1-11) as the final go/no-go check before considering Feature 008 complete **Full quickstart.md sequence re-run end-to-end post-fix: Steps 1-4 and 7 re-verified green in one pass (Step 1's command updated to exclude the new regression test's self-reference, which is an expected, now-documented exception); Steps 5-6, 8-10 remain valid from T026-T030; Step 11 cold-read confirms the README's opening states the Shiruno/Albertos boundary unambiguously.**
- [X] T043 [P] Record (in the PR description, not as a code change) that `.specify/memory/constitution.md`'s "Albercik Chatbot" naming (5 occurrences) is a required follow-up for a separate `/speckit-constitution` amendment — out of scope for this feature's tasks (research.md §5) **Recorded below in the implementation completion report** (see `research.md` §5): `.specify/memory/constitution.md`'s 5 "Albercik Chatbot" occurrences need a follow-up `/speckit-constitution` amendment — intentionally not touched by this feature's tasks.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. T003 blocks T004-T021; T004-T020 are mutually independent (disjoint files) once T003 is done; T021 depends on T004-T020; T022 depends on T004-T021.
- **User Stories (Phase 3-6)**: All depend on Foundational (Phase 2) completion.
  - US1 (Phase 3) has no dependency on US2/US3/US4 — pure verification of what Foundational already changed.
  - US2 (Phase 4) has no dependency on US1/US3/US4.
  - US3 (Phase 5) has no dependency on US1/US2/US4.
  - US4 (Phase 6) depends on US2's T033 (both write to `docs/architecture.md`; T038/T039 append sections after T033 creates the file) but not otherwise on US1/US3.
- **Polish (Phase 7)**: Depends on all four user stories being complete (T042 runs the full quickstart, which exercises US1-US4's outputs).

### Within Each Phase

- Foundational: T003 → {T004...T020 in parallel} → T021 → T022.
- US1: T023-T031 are each independent verification actions; T025 must precede T026 (stack must be up before CLI/Alembic commands run against it), and T028/T029 also depend on the stack from T025 being up.
- US2: T032 is independent [P]; T033 → T034 (README links to the architecture doc).
- US3: T035 is independent [P]; T036 and T037 can follow in either order but T037 should run last as the closing verification.
- US4: T038 → T039 (same file, sequential); T040 is an independent verification, can run anytime after Foundational.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel.
- Once T003 completes, all of T004-T020 (17 tasks, all disjoint files) can run fully in parallel.
- Once Foundational completes, US1, US2, and US3 phases can proceed in parallel with each other (US4 waits on US2's T033).
- Within US1, T023 and T024 can run in parallel with each other.

---

## Parallel Example: Foundational Phase

```bash
# After T003 (git mv src/albercik_chatbot src/shiruno) completes, launch together:
Task: "Update imports in src/shiruno/api/{deps,errors,schemas}.py + routers/{auth,chat,documents}.py"
Task: "Update imports in src/shiruno/application/{ask_question,delete_document,list_documents,upload_document}.py"
Task: "Update imports in src/shiruno/domain/prompting.py"
Task: "Update imports in src/shiruno/infra/{audit,budget,rate_limit}.py"
Task: "Update imports in src/shiruno/persistence/{database,repositories}.py"
Task: "Update imports in src/shiruno/providers/embedding/local_sentence_transformer_provider.py + llm/{anthropic_provider,ollama_provider}.py"
Task: "Update imports in src/shiruno/public_site/{data/*.py,filters.py,router.py}"
Task: "Update imports in src/shiruno/main.py and cli.py"
Task: "Update pyproject.toml, Dockerfile, alembic/env.py, scripts/*.py"
Task: "Update imports across all 23 files in tests/contract/"
Task: "Update imports across all 20 files in tests/unit/"
Task: "Update imports across all 4 files in tests/integration/"
Task: "Update imports in tests/fakes/, tests/fixtures/, tests/conftest.py"
```

---

## Implementation Strategy

### MVP First (Foundational + User Story 1 Only)

1. Complete Phase 1: Setup (baseline capture).
2. Complete Phase 2: Foundational (the actual rename — CRITICAL, blocks everything).
3. Complete Phase 3: User Story 1 (prove nothing broke).
4. **STOP and VALIDATE**: if T023-T031 all pass, the highest-risk part of Feature 008 is done — behavior is provably preserved.

### Incremental Delivery

1. Setup + Foundational → package renamed, tests still pass internally.
2. User Story 1 → behavior-preservation proven (MVP: safe to merge even if docs lag).
3. User Story 2 → README/architecture doc make the product boundary legible.
4. User Story 3 → naming consistency completed everywhere.
5. User Story 4 → future boundaries documented, nothing prematurely built.
6. Polish → final hygiene pass and full quickstart sign-off.

### Notes

- [P] tasks = different files, no dependencies.
- This feature has an unusually large, front-loaded Foundational phase because the rename is a single indivisible unit of work every story depends on — this is expected for a repository-wide rename, not a sign the phases were mis-split.
- Commit after each task or logical group (e.g., after all of T004-T020 land, before T021's regression test).
- The Postgres credential names (`albercik`/`albercik_test`) and Docker Compose service/volume names are intentionally left unchanged throughout — see research.md §4. Do not "complete" the rename by touching them.
