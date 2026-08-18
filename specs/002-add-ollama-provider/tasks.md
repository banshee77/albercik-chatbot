---

description: "Task list template for feature implementation"
---

# Tasks: Local Ollama LLM Provider

**Input**: Design documents from `/specs/002-add-ollama-provider/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all present)

**Tests**: Included — the spec explicitly requires mockable-HTTP `OllamaLLMProvider` tests (FR-017) and the project constitution makes security-relevant/cost-relevant test coverage NON-NEGOTIABLE (Principle XI). Tests are written before the implementation they cover, per task. No automated test requires a real Ollama process or a real Anthropic call — every test injects the existing `FakeLLMProvider`/`FakeEmbeddingProvider` doubles or a mocked HTTP transport for `OllamaLLMProvider` itself, mirroring how `AnthropicLLMProvider`'s own tests already work.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P3, plus the P2 User Story 4 addendum) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Every task lists an exact file path

## Path Conventions

Single existing backend project (plan.md "Structure Decision": unchanged
layout from `001-albertos-rag-chatbot`):

- App code: `src/albercik_chatbot/`
- Tests: `tests/unit/`, `tests/contract/`
- Migrations: `alembic/versions/`
- Root: `docker-compose.yml`, `.env.example`, `README.md`
- Dev tooling: `scripts/run_eval.py`, `eval/README.md`

## Design Constraints Carried Into These Tasks

1. **`provider_name` backfill is deterministic and never inferred from
   `provider_model`** (data-model.md Migration): keyed exclusively on the
   existing `provider_kind` column — `llm` → `anthropic`,
   `embedding` → `local_sentence_transformer`. The column is added nullable,
   backfilled, verified, then set `NOT NULL` — never briefly `NOT NULL`
   with guessed data for any row (T005).
2. **Retry ownership stays per-provider** (research.md §3, carrying forward
   Design Constraint 1 from `001-albertos-rag-chatbot`): `OllamaLLMProvider`
   owns its own bounded retry loop, reusing the existing
   `PROVIDER_MAX_RETRIES` setting — no other layer retries a provider call,
   and `application/ask_question.py` gains no Ollama-specific branching
   (T007, T012).
3. **Startup logging never includes secrets or internal URLs** (spec
   FR-018/SC-007, research.md §8): the one new startup log line names the
   active provider and model only — never `OLLAMA_BASE_URL`,
   `ANTHROPIC_API_KEY`, or any other configuration value (T010, T011).
4. **Budget exclusion is structural, not inferred** (data-model.md,
   research.md §4): `infra/budget.py`'s query filters on the new
   `provider_name` column, never on `provider_model` string matching (T008,
   T009).
5. **Automatic model provisioning stays a Compose-level concern, never
   application/domain code** (spec addendum FR-025, research.md §6a): the
   entire mechanism — waiting for `ollama` to be healthy, running `ollama
   pull`, and the one `LLM_PROVIDER`-gated skip check for non-Ollama
   deployments — lives in `docker-compose.yml`'s `ollama-init` service
   definition. No task in this phase touches `main.py`,
   `application/ask_question.py`, or any other Python source file (T020–T022).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Docker Compose and environment-template scaffolding — no application code yet.

- [X] T001 [P] Add an `ollama` service to `docker-compose.yml`: official `ollama/ollama` image, **no `ports:` mapping** (internal Compose network only, reachable at `http://ollama:11434`), included in the default `docker compose up` set — **not** gated behind a Compose profile, since `LLM_PROVIDER` defaults to `ollama` (research.md §6)
- [X] T002 [P] Add `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS` placeholder entries to `.env.example`, with the documented development defaults (`ollama`, `http://ollama:11434`, `qwen3:4b`) and a comment noting `LLM_PROVIDER=anthropic` requires a real `ANTHROPIC_API_KEY`

**Checkpoint**: Compose stack has an Ollama service available; env template documents the new settings. No app code touched yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every user story depends on — config, schema, the second provider implementation, budget isolation, composition wiring. No user-facing behavior yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Add `LLM_PROVIDER` (enum `anthropic`/`ollama`, default `ollama`), `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS` to `src/albercik_chatbot/config.py` (data-model.md Configuration table)
- [X] T004 [P] Add a `ProviderName` enum (`anthropic`, `ollama`, `local_sentence_transformer`) and a required `provider_name` column on `UsageRecord` in `src/albercik_chatbot/persistence/models.py` (data-model.md)
- [X] T005 Create the Alembic migration for `usage_records.provider_name` in `alembic/versions/`: (1) add column nullable, (2) backfill deterministically — `UPDATE ... SET provider_name='anthropic' WHERE provider_kind='llm'` and `UPDATE ... SET provider_name='local_sentence_transformer' WHERE provider_kind='embedding'`, keyed only on `provider_kind`, never on `provider_model` — (3) assert zero remaining NULLs, (4) `ALTER COLUMN ... SET NOT NULL`; no `SERVER DEFAULT` left in place (data-model.md Migration) — depends on T004
- [X] T006 [P] Unit tests for `OllamaLLMProvider` using a mocked HTTP transport in `tests/unit/test_ollama_provider.py`: successful generation, timeout, connection failure, invalid/malformed response, configured model sent correctly in the request body, `options.num_predict` (output cap) always server-controlled and never client-influenced, bounded retry count proven exactly like `tests/unit/test_anthropic_provider_retries.py` (spec FR-013, FR-014, FR-017; research.md §2, §3) — write first, confirm failure
- [X] T007 Implement `OllamaLLMProvider` behind the existing `LLMProvider` Protocol in `src/albercik_chatbot/providers/llm/ollama_provider.py`: `httpx`-based `POST {OLLAMA_BASE_URL}/api/chat`, `stream: false`, own bounded retry loop reusing `PROVIDER_MAX_RETRIES` (Design Constraint 2 above), `OLLAMA_TIMEOUT_SECONDS` per attempt, server-side failure logging mirroring `anthropic_provider.py`'s existing pattern (research.md §1, §2, §3) — depends on T003, T006
- [X] T008 [P] Unit test extending `tests/unit/test_budget.py`: budget check excludes rows with `provider_name='ollama'` and `provider_name='local_sentence_transformer'`, counting only `provider_kind='llm' AND provider_name='anthropic'` (data-model.md Budget query change; Design Constraint 4 above) — write first, confirm failure
- [X] T009 Extend `src/albercik_chatbot/infra/budget.py`'s query to filter `provider_kind='llm' AND provider_name='anthropic'` — depends on T004, T005, T008
- [X] T010 [P] Unit test proving `create_app()` constructs `OllamaLLMProvider` when `LLM_PROVIDER=ollama` and `AnthropicLLMProvider` when `LLM_PROVIDER=anthropic`, and a separate assertion that the startup log record contains the provider and model values but never `OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY`, or `AUTH_JWT_SECRET` (spec FR-002, FR-018/SC-007; research.md §5, §8) — write first, confirm failure
- [X] T011 Wire `LLM_PROVIDER`-driven provider construction and the one startup `INFO` log line (provider + model only) into `src/albercik_chatbot/main.py::create_app()` — depends on T007, T010
- [X] T012 Extend `src/albercik_chatbot/application/ask_question.py` (new `provider_name` parameter threaded from `src/albercik_chatbot/api/routers/chat.py` via `settings.LLM_PROVIDER`, alongside the existing `llm_model_name` parameter — no provider-specific branching added, Design Constraint 2 above) and `src/albercik_chatbot/application/upload_document.py` (embedding-kind `UsageRecord` rows now pass `provider_name='local_sentence_transformer'`) so every `UsageRecord` write populates the new required column — depends on T004

**Checkpoint**: Both providers exist and are individually correct; budget isolation is structurally enforced; the app boots with either backend selected via configuration alone and logs which one safely. No end-to-end HTTP-level proof yet — that's what the user story phases add.

---

## Phase 3: User Story 1 - Operator runs the chatbot on a local model instead of a paid API (Priority: P1) 🎯 MVP

**Goal**: With no `LLM_PROVIDER` override (the documented default), a visitor's in-scope, knowledge-base-covered question is answered by the local model backend, and the usage record for that request is clearly attributable to it.

**Independent Test**: Seed a document chunk (no upload endpoint dependency needed, mirroring `001-albertos-rag-chatbot`'s own US1 test style), leave `LLM_PROVIDER` unset, ask the matching question through `/api/v1/chat`, and confirm a grounded answer with a `provider_name='ollama'` usage record — no Anthropic call attempted.

### Tests for User Story 1 ⚠️ write first, confirm they fail

- [X] T013 [P] [US1] Contract test: with `LLM_PROVIDER` unset (default), `POST /api/v1/chat` for a knowledge-base-covered question returns `outcome: "grounded"` generated by the local-backend fake provider, and the Anthropic-backed fake provider (if also present in the test app) is never called, in `tests/contract/test_chat_ollama_default.py` (spec Acceptance Scenario US1.1)

### Implementation for User Story 1

- [X] T014 [US1] Contract test (same file): the request's resulting `usage_records` row has `provider_kind='llm'` and `provider_name='ollama'` (spec Acceptance Scenario US1.2) — depends on T013

**Checkpoint**: User Story 1 is independently functional — the default configuration answers grounded questions via the local backend, with correctly-attributed usage accounting.

---

## Phase 4: User Story 2 - Operator switches backends with configuration only, protections unchanged (Priority: P2)

**Goal**: Switching `LLM_PROVIDER` requires configuration only, and every existing abuse/cost/security control — rate limiting, the kill switch, concurrency limits, prompt-injection defenses, budget enforcement, no-client-override — produces identical outcomes regardless of which backend is active.

**Independent Test**: With each backend selected in turn (via the app's provider-selection wiring from Phase 2, no code change), exercise the existing rate-limit/kill-switch/budget/prompt-injection contract tests and confirm identical outcomes; separately confirm heavy local-backend usage never reduces the Anthropic budget.

### Tests for User Story 2 ⚠️ write first, confirm they fail

- [X] T015 [P] [US2] Contract test: reconstructing the test app with `LLM_PROVIDER=ollama` vs. `LLM_PROVIDER=anthropic` (both backed by fakes) routes a request to the correspondingly-active fake provider, proving the switch is config-only, in `tests/contract/test_chat_provider_switch.py` (spec Acceptance Scenario US2.1, FR-004)
- [X] T016 [P] [US2] Contract test: rate-limit-exceeded, `LLM_ENABLED=false` kill-switch, concurrency-guard-full, and a representative prompt-injection message all produce the same outcome (429/503/unavailable/safe-refusal, no leaked detail) under both configured backends, in `tests/contract/test_chat_provider_parity.py` (spec Acceptance Scenario US2.2, FR-009)
- [X] T017 [P] [US2] Contract test extending `tests/contract/test_chat_no_client_override.py`: request-body fields attempting to specify a provider, model, or generation parameter have no effect under either configured backend (spec Acceptance Scenario US2.4, FR-002)
- [X] T018 [P] [US2] Contract test extending `tests/contract/test_chat_budget.py`: heavy `provider_name='ollama'` usage volume (many local-backend requests) never reduces or exhausts the Anthropic budget, confirmed by the same budget check that already gates real Anthropic calls, in the same file (spec Acceptance Scenario US2.3, FR-010)

### Implementation for User Story 2

No new implementation tasks — Phase 2's provider-selection wiring (T011),
budget isolation (T009), and the pre-existing cost/abuse controls (rate
limit, kill switch, concurrency, prompt-injection — all already
provider-agnostic by construction, per FR-007/FR-009) are exercised, not
extended, by this story. If any test above fails, the fix belongs in
whichever Phase 2 task owns the gap it reveals, not a new task here.

**Checkpoint**: User Stories 1–2 both independently functional — backend switching is proven config-only, and every existing protection is proven backend-agnostic.

---

## Phase 5: User Story 4 - Operator gets a fully working local backend from a single startup command (Priority: P2)

**Goal**: A normal `docker compose up -d` — with no separate manual `ollama pull` command — results in the configured `OLLAMA_MODEL` being ready before `app` starts serving local-backend traffic; restarting without removing the model volume never re-downloads it; a model that can't be provisioned fails visibly and blocks `app` from starting rather than silently continuing.

**Independent Test**: Per quickstart.md Scenario 4 — `docker compose down -v` then `docker compose up -d` on a machine with no previously-downloaded model, confirm `ollama-init` pulls the configured model and exits `0` before `app` becomes ready; confirm a second `down`/`up` cycle (no `-v`) does not re-download; confirm an invalid `OLLAMA_MODEL` makes `ollama-init` fail and `app` never start.

### Tests for User Story 4 ⚠️ write first, confirm they fail

- [X] T019 [P] [US4] Structural test of `docker-compose.yml`'s automatic-provisioning wiring (parses the file with PyYAML — no Docker daemon, no real Ollama process, no model download, per testing constraint FR-030): the `ollama` service defines a `healthcheck`; an `ollama-init` service exists, reuses the `ollama/ollama` image, has no `ports:` entry, has `restart: "no"` (or no `restart` key at all), depends on `ollama` with `condition: service_healthy`, and its `environment`/`command` reference `OLLAMA_MODEL` and `LLM_PROVIDER` (never a hardcoded model string); the `app` service's `depends_on` includes `ollama-init` with `condition: service_completed_successfully` alongside the existing `db: condition: service_healthy` — in `tests/unit/test_docker_compose_provisioning.py` (spec FR-019–FR-029, requirement 8)

### Implementation for User Story 4

- [X] T020 [US4] `docker-compose.yml`: add an `ollama list` healthcheck to the `ollama` service (in-container CLI call against its own server, no extra tooling needed) and replace its existing "model weights are not auto-pulled" comment with one describing automatic provisioning via `ollama-init` (research.md §6a) — depends on T019
- [X] T021 [US4] `docker-compose.yml`: add the new one-shot `ollama-init` service — reuses the `ollama/ollama` image, `restart: "no"`, `environment: OLLAMA_HOST=http://ollama:11434`, `OLLAMA_MODEL=${OLLAMA_MODEL:-qwen3:4b}`, `LLM_PROVIDER=${LLM_PROVIDER:-ollama}`, `depends_on: ollama: condition: service_healthy`, and a shell `command:` that exits `0` immediately (no download attempted) when `LLM_PROVIDER != ollama`, otherwise runs `ollama pull "$OLLAMA_MODEL"` (research.md §6a — `ollama pull` is natively idempotent, so no separate existence check is written) — depends on T020
- [X] T022 [US4] `docker-compose.yml`: add `ollama-init: condition: service_completed_successfully` to the `app` service's existing `depends_on` block, alongside the unchanged `db: condition: service_healthy` — depends on T021

**Checkpoint**: User Stories 1, 2, and 4 all independently functional — a fresh `docker compose up -d` produces a fully working local-backend chatbot with zero manual steps, restarts don't re-download, and a bad model configuration fails loudly instead of silently.

---

## Phase 6: User Story 3 - Operator compares answer quality between backends (Priority: P3)

**Goal**: The same fixed evaluation question set can be run once per backend, producing directly comparable, backend-labeled results.

**Independent Test**: Run `scripts/run_eval.py` once with each backend configured (restarting the app between runs, no question-set modification) and confirm each run's report clearly states which backend produced it.

### Implementation for User Story 3

- [X] T023 [US3] Extend `scripts/run_eval.py` to read the active `LLM_PROVIDER` from configuration and label its printed report header with it (research.md §7; spec FR-016) — depends on Phase 2 (T003)
- [X] T024 [P] [US3] Update `eval/README.md`'s "Running it locally" section to document running the eval once per backend (switching `LLM_PROVIDER` and restarting between runs) and comparing the two labeled reports — depends on T023

**Checkpoint**: All four user stories independently functional — the eval dataset now supports direct backend comparison without any dual-provider tooling.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation accuracy and final verification against quickstart.md and the constitution's testing gate.

- [X] T025 [P] Update `README.md`'s architecture section to mention the dual-provider capability (Claude via Anthropic, or a local Ollama model), that the local backend is the default, and that `docker compose up -d` alone provisions the configured local model automatically — no manual `ollama pull` step
- [X] T026 Run `specs/002-add-ollama-provider/quickstart.md` Scenarios 1–5 end-to-end against the real Docker Compose stack (real `ollama`/`ollama-init` services, automatic model provisioning — no manual `ollama pull`) and record results
- [X] T027 Run the full quality gate — `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` — and confirm the automated suite passes with the `ollama` container stopped and no `ANTHROPIC_API_KEY` set (spec FR-017/SC-006, FR-030)
- [X] T028 [P] Repository-hygiene check: confirm no Ollama-related internal URL or credential leaked into any tracked file, `.env.example`'s entries remain placeholders only, and the new `ollama-init` service has no published port (mirrors the pre-commit review already established for this project)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US1 (Phase 3)**: Depends only on Foundational.
- **US2 (Phase 4)**: Depends only on Foundational — its tests exercise Phase 2's provider-selection wiring and the pre-existing (unmodified) cost/abuse controls together; no new implementation of its own.
- **US4 (Phase 5)**: Depends only on Setup (specifically T001, which created the `ollama` service `ollama-init` extends) — entirely independent of Foundational/US1/US2/US3, since it's pure Docker Compose configuration with no application code involved.
- **US3 (Phase 6)**: Depends only on Foundational (specifically T003, for `LLM_PROVIDER` to read).
- **Polish (Phase 7)**: Depends on all four user stories.

### Within Each User Story

- Tests are written first and MUST fail before any corresponding fix/implementation.
- Foundational schema/provider/composition work → user-story-level HTTP contract tests that prove it end-to-end.

### Parallel Opportunities

- Setup: T001, T002 (different files).
- Within Foundational: T003, T004 can run together (different files); T006, T008, T010 (all test-writing tasks) can run together once their single respective dependency, if any, is satisfied.
- US1's T013 can start as soon as Foundational is complete.
- US2's T015–T018 can all run together (independent test files) once Foundational is complete.
- US4 (T019–T022) can proceed entirely in parallel with US1/US2/US3, and even with Foundational — it only needs Setup's T001; within US4 itself, T020→T021→T022 are sequential (same file, each building on the previous edit).
- US3's T024 can run parallel to nothing else in its own phase (depends on T023) but is independent of US1/US2/US4.
- Polish: T025, T028 can run together; T026 and T027 are sequential verification passes.

---

## Parallel Example: Foundational Phase

```bash
# Config + schema together:
Task: "Add LLM_PROVIDER/OLLAMA_* settings in src/albercik_chatbot/config.py"
Task: "Add ProviderName enum + UsageRecord.provider_name in src/albercik_chatbot/persistence/models.py"

# All three write-first test files together:
Task: "OllamaLLMProvider unit tests in tests/unit/test_ollama_provider.py"
Task: "Budget-isolation unit test extending tests/unit/test_budget.py"
Task: "Provider-selection + safe-startup-log unit test"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: default configuration answers a grounded question via the local backend, with correctly-attributed usage accounting — this is the entire value proposition of the feature.

### Incremental Delivery

1. Setup + Foundational → both providers exist, selected by configuration, budget-isolated, safely logged.
2. US1 → the local backend works end-to-end as the default (MVP!).
3. US2 → switching backends is proven configuration-only, with zero protection regressions.
4. US4 → `docker compose up -d` alone is sufficient — no manual model pull, restarts don't re-download, bad config fails loudly.
5. US3 → the existing eval dataset supports direct cross-backend comparison.
6. Polish → docs, full quickstart run, final quality gate, hygiene check.

### Parallel Team Strategy

1. Team completes Setup + Foundational together (the schema/budget/composition work in Phase 2 has real internal dependencies — T005 needs T004, T007 needs T003+T006, T009 needs T004+T005+T008, T011 needs T007+T010 — so Foundational itself benefits from one owner per task but not from splitting the phase's *order*).
2. Once Setup is done, US4 can start immediately (it only needs T001) without waiting for Foundational.
3. Once Foundational is done: US1, US2, and US3 have no dependencies on each other and can proceed fully in parallel, alongside US4.
