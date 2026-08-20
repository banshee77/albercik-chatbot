---

description: "Task list for Feature 011 — Conversations & Analytics"
---

# Tasks: Conversations & Analytics

**Input**: Design documents from `/specs/011-conversations-analytics/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included — the spec's User Story acceptance scenarios and Success Criteria explicitly require automated verification (SC-001, SC-002, SC-005, SC-006, SC-008, SC-009 all say "verified by automated tests"), and constitution Principle XI makes this NON-NEGOTIABLE for security-sensitive behavior (tenant isolation, safe failure handling, cost-safety-adjacent recording).

**Organization**: Tasks are grouped by user story from spec.md. Story *labels* keep the spec's declared priority (P1: US1, US2, US3, US4, US6, US7; P2: US5), but **phase order** follows real buildable dependency — US6 (cross-tenant isolation proof) needs the five endpoints US1–US5 create, so it is phased after them despite being P1, exactly mirroring Feature 010's US6 precedent. See Dependencies & Execution Order below.

**Foundational-phase deviation from the Feature 010 precedent**: Feature 010's Foundational phase added no *new* dedicated test files (only a "does the existing suite still pass" checkpoint), deferring all new-behavior tests to the story that first exercises them. This feature's Foundational phase is different in kind — it is a brand-new write path on the public, unauthenticated `/chat` endpoint (the riskiest, most novel part of this feature, and the specific subject of two dedicated clarification rounds on SAVEPOINT semantics and fail-closed tenant resolution). Foundational therefore *does* include the tests that prove this write path itself is correct (T010–T013), before any admin read endpoint is built on top of data it produces.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US7, per spec.md
- File paths are exact and relative to the repository root.

## Path Conventions

Single existing backend project — `src/shiruno/`, `tests/`, `alembic/versions/` at repository root (plan.md's Structure Decision; no new project is created).

---

## Phase 1: Setup

No setup tasks are required. This feature extends the existing `shiruno`
backend project in place — no new dependency, tool, or project
scaffolding is introduced (plan.md Technical Context: zero new
dependencies).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new `ConversationRecord` schema, the shared question-
normalization utility, the extended `AskQuestionResult`/`BudgetCheckResult`
return contracts, fail-closed public-tenant resolution, and the
SAVEPOINT-isolated recording write itself — the public write path every
later admin-facing story reads from.

**⚠️ CRITICAL**: No user story task may start until this phase is
complete. In particular, T009's `chat.py` wiring is what makes every later
story's data exist at all, and T012's recording-correctness test is what
proves that data is trustworthy before anything is built to read it.

- [X] T001 [P] Add `ConversationOutcome` and `FailureCategory` enums and the `ConversationRecord` model (all columns, three composite indexes, `request_id` unique constraint) to `src/shiruno/persistence/models.py` (data-model.md)
- [X] T002 Create Alembic migration `add_conversation_records` in `alembic/versions/` — `CREATE TYPE conversation_outcome`, `CREATE TYPE conversation_failure_category`, `CREATE TABLE conversation_records` (FK to `tenants.id`, `provider_name` reusing the existing `provider_name` enum type), the three composite indexes plus the `request_id` unique constraint; fully reversible `downgrade()` dropping the table then both new enum types (data-model.md "Migration plan"; no backfill — the table has no historical rows; depends on T001)
- [X] T003 [P] Create `src/shiruno/domain/question_normalization.py::normalize_question(text: str) -> str` — lowercase + whitespace-collapse only, no punctuation stripping, no semantic processing (research.md §6)
- [X] T004 [P] Extend `BudgetCheckResult` in `src/shiruno/infra/budget.py` with `reason: Literal["kill_switch", "budget_exceeded"] | None = None`, set to `"kill_switch"` when `LLM_ENABLED=false`, and to `"budget_exceeded"` both when the hourly count is exceeded and when the budget-check query itself fails (research.md §5)
- [X] T005 Extend `AskQuestionResult` in `src/shiruno/application/ask_question.py` with `provider_name`, `provider_model`, `input_tokens`, `output_tokens`, `provider_metrics`, `failure_category` (all optional, default `None`); populate them at every return site from data already computed in that branch — budget/kill-switch block sets `failure_category` from `BudgetCheckResult.reason`; concurrency-guard-full sets `failure_category="concurrency_limit"`; caught `LLMProviderError` sets `failure_category="provider_error"` plus `provider_name`/`provider_model`; the `result.supported is False` and `grounded` branches populate the full provider/token/metrics set from the successful `LLMResult`; `small_talk`, `out_of_scope`, and the zero-chunk `insufficient_information` branches leave every new field `None` (research.md §5; depends on T004)
- [X] T006 [P] Add `PUBLIC_CHAT_TENANT_SLUG: str = "albertos"`, `CONVERSATION_LIST_DEFAULT_PAGE_SIZE: int = 20`, `CONVERSATION_LIST_MAX_PAGE_SIZE: int = 100`, `ANALYTICS_DEFAULT_LOOKBACK_DAYS: int = 30` to `src/shiruno/config.py`
- [X] T007 [P] Create `src/shiruno/application/resolve_public_tenant.py::resolve_public_tenant(session, *, slug: str) -> Tenant | None` — exists-and-`TenantStatus.active` check only; no `.first()`/fallback of any kind; never constructs a `Tenant` row; never raises for a missing/inactive tenant (research.md §4)
- [X] T008 Create `src/shiruno/application/record_conversation.py` — calls `resolve_public_tenant()` first; if it returns `None`, logs one `logger.warning(...)` line naming only the configured slug and returns immediately (no insert attempted); if a tenant resolves, opens `session.begin_nested()` and inserts a `ConversationRecord` snapshotting the `AskQuestionResult` plus `normalize_question(question)` and the caller-supplied end-to-end `latency_ms` (research.md §2a, §3, §4; depends on T001, T003, T005, T007)
- [X] T009 Wire `src/shiruno/api/routers/chat.py::post_chat` — measure end-to-end latency with `time.monotonic()` around the existing `ask_question(...)` call; call `record_conversation(...)` immediately after, wrapped in `try`/`except Exception` that logs via `logger.exception(...)` with only `request_id` as context (never question/answer content) and always falls through to build and return `ChatResponse` regardless of outcome (research.md §3, §9; depends on T008)
- [X] T010 [P] Create `tests/unit/test_question_normalization.py` — lowercase/whitespace collapsing behavior, idempotence, punctuation deliberately preserved (depends on T003)
- [X] T011 [P] Create `tests/unit/test_resolve_public_tenant.py` — configured tenant exists and active resolves it; configured tenant missing returns `None`; configured tenant exists but `inactive` returns `None`; a second, differently-slugged tenant present at the same time is never selected as a fallback; no `Tenant` row is ever created as a side effect of any case (research.md §4 "Testing implication"; depends on T007)
- [X] T012 Create `tests/contract/test_chat_conversation_recording.py` — a `grounded`, `insufficient_information` (both the zero-chunk and the real-LLM-call flavors), `out_of_scope`, `small_talk`, and `unavailable` (all four failure categories: `provider_error`, `budget_exceeded`, `kill_switch`, `concurrency_limit`) request each produces exactly one correctly-populated `ConversationRecord`, including `small_talk` having zero token/provider fields; a forced `ConversationRecord` insert failure still returns a normal, successful `ChatResponse`, and any `UsageRecord` row already flushed earlier in that same request is still present afterward (proving only the `SAVEPOINT` rolled back, not the outer transaction); a missing or `inactive` configured public tenant still returns a normal `ChatResponse` with no `ConversationRecord` written for that request (research.md §3, §4, §5; depends on T009)
- [X] T013 [P] Create `tests/integration/test_conversation_records_migration.py` — upgrade creates `conversation_records` with both new enum types and all indexes; downgrade drops the table and both enum types cleanly; re-upgrading to head after a full downgrade succeeds (mirrors `specs/010-knowledge-base-admin`'s `test_knowledge_document_migration.py` pattern; depends on T002)

**Checkpoint**: `uv run pytest tests/contract tests/unit tests/integration -q` is fully green, including every new Foundational test above — the public write path (the riskiest, most novel part of this feature) is proven correct before any admin read endpoint is built on top of it.

---

## Phase 3: User Story 1 - Administrator reviews what visitors are asking (Priority: P1) 🎯 MVP

**Goal**: Tenant-scoped, filterable, searchable, bounded-pagination conversation list — the foundation every other admin-facing story builds on.

**Independent Test**: quickstart.md §3 — request the conversation list as an authenticated administrator and confirm it reflects only your own tenant's conversations, newest-first, with working outcome/date/search filters and bounded pagination.

### Implementation for User Story 1

- [X] T014 [P] [US1] Add `ConversationSummary` and `ConversationListResponse` schemas to `src/shiruno/api/schemas.py` (contracts/conversations-api.md)
- [X] T015 [P] [US1] Create `src/shiruno/application/list_conversations.py` — tenant-scoped; ordered `created_at` descending, `id` descending tiebreak; optional `outcome`, `start_date`/`end_date`, and `q` (case-insensitive `ILIKE` substring over `question`) filters; `limit`/`offset` clamped to `[1, CONVERSATION_LIST_MAX_PAGE_SIZE]`/`[0, ∞)`, never rejected; returns items plus a total count independent of pagination (research.md §7, §8; contracts/conversations-api.md; depends on T001)
- [X] T016 [US1] Add `GET /admin/conversations` to a new `src/shiruno/api/routers/conversations.py` (`APIRouter(prefix="/api/v1/admin", tags=["conversations"])`); register the router in `src/shiruno/main.py` (research.md §10; depends on T014, T015)

### Tests for User Story 1

- [X] T017 [P] [US1] Create `tests/contract/test_conversations_list.py` — newest-first deterministic ordering; a tenant with zero conversations gets a valid empty result; outcome filter, date-range filter, and question search each narrow results correctly, including zero-match cases; requesting more than the configured maximum page size is clamped, never rejected and never exceeded; only the authenticated tenant's own conversations are ever returned (depends on T016)

**Checkpoint**: `uv run pytest tests/contract/test_conversations_list.py -q` passes independently.

---

## Phase 4: User Story 2 - Administrator inspects a single conversation in detail (Priority: P1)

**Goal**: Full conversation detail — question, answer, operational metadata, and (for `grounded`) the exact source evidence — with cross-tenant lookups failing closed and every field behaving as an immutable, at-write-time snapshot.

**Independent Test**: quickstart.md §4 — open a specific conversation's detail and confirm it shows the full question/answer/outcome plus timing and (when grounded) sources; confirm the same request against a nonexistent or foreign-tenant conversation fails identically.

### Implementation for User Story 2

- [X] T018 [P] [US2] Add `ConversationDetail` schema to `src/shiruno/api/schemas.py` (contracts/conversations-api.md; depends on T001)
- [X] T019 [P] [US2] Create `src/shiruno/application/get_conversation.py` — tenant-scoped single-record fetch, raising the existing `NotFoundAppError` for a missing or foreign-tenant conversation id (depends on T001)
- [X] T020 [US2] Add `GET /admin/conversations/{conversation_id}` to `src/shiruno/api/routers/conversations.py`, registered after the list route (contracts/conversations-api.md; depends on T016, T018, T019)

### Tests for User Story 2

- [X] T021 [P] [US2] Create `tests/contract/test_conversations_detail.py` — full detail shape for a `grounded` conversation including its `sources`; `sources` is `null` (never a fabricated empty list) for every other outcome; `safe_failure_category` is non-`null` only for `unavailable`; `404` for a nonexistent conversation and an identical `404` for a foreign-tenant one; **historical-snapshot immutability**: recording a grounded conversation, then replacing or soft-deleting the `KnowledgeDocument` it cited (via Feature 010's existing replace/delete operations), leaves that conversation's `sources` completely unchanged when re-fetched; two conversations recorded with two different `provider_name`/`provider_model` values each continue to report their own originally-recorded value via this endpoint regardless of the test app's current `LLM_PROVIDER` configuration (research.md §2a "Testing implication"; depends on T020)

**Checkpoint**: `uv run pytest tests/contract/test_conversations_list.py tests/contract/test_conversations_detail.py -q` passes.

---

## Phase 5: User Story 3 - Administrator sees an at-a-glance analytics summary (Priority: P1)

**Goal**: Tenant-scoped, date-ranged aggregate view — request volume, outcome counts/rates, latency, and token/provider usage — computed with plain PostgreSQL aggregation.

**Independent Test**: quickstart.md §6 — request the analytics summary for a date range and confirm totals, outcome counts/rates, latency figures, and token/provider usage are correct for only your own tenant, including the zero-activity case.

### Implementation for User Story 3

- [X] T022 [P] [US3] Add `DateRangeOut`, `OutcomeStatsOut`, `LatencyStatsOut`, `TokenTotalsOut`, `ProviderUsageOut`, and `AnalyticsSummaryResponse` schemas to `src/shiruno/api/schemas.py` (contracts/analytics-api.md)
- [X] T023 [P] [US3] Create `src/shiruno/application/conversation_analytics.py::get_analytics_summary` — tenant-scoped; date range defaults to `[now - ANALYTICS_DEFAULT_LOOKBACK_DAYS, now]` when omitted; total requests, per-outcome count/rate (`0.0` rate when total is `0`), `AVG(latency_ms)` plus `percentile_cont(0.5)`/`percentile_cont(0.95)` (both `null` when zero matching rows), summed `input_tokens`/`output_tokens`, and a `provider_name`/`provider_model` breakdown with per-group request count and token totals — all computed directly from `ConversationRecord`, never joining `UsageRecord` or reading current `config.Settings` provider configuration (research.md §2a, §7, §9; contracts/analytics-api.md; depends on T001)
- [X] T024 [US3] Add `GET /admin/analytics/summary` to a new `src/shiruno/api/routers/analytics.py` (`APIRouter(prefix="/api/v1/admin", tags=["analytics"])`); register the router in `src/shiruno/main.py` (depends on T022, T023)

### Tests for User Story 3

- [X] T025 [P] [US3] Create `tests/contract/test_analytics_summary.py` — outcome counts/rates correct against seeded fixtures; `small_talk` contributes to `total_requests` but nothing to `tokens`/`providers`; latency average/p50/p95 correct; a tenant with zero activity in range returns `200` with every figure validly zeroed/`null`, never an error; omitting the date range applies the documented 30-day default; two conversations recorded under two different `provider_name`/`provider_model` values both appear in `providers`, each with its own recorded figures, regardless of the test app's current `LLM_PROVIDER` configuration (research.md §2a; depends on T024)

**Checkpoint**: `uv run pytest tests/contract/test_analytics_summary.py -q` passes independently.

---

## Phase 6: User Story 4 - Administrator identifies recurring knowledge gaps (Priority: P1)

**Goal**: Deterministic, `insufficient_information`-only, normalized-text ranking of recurring unanswered questions — the most actionable output of this feature.

**Independent Test**: quickstart.md §6 — seed insufficient-information conversations including near-duplicate wording and confirm the knowledge-gaps view groups and ranks them deterministically, using only insufficient-information data.

### Implementation for User Story 4

- [X] T026 [P] [US4] Add `QuestionFrequencyItem` and `KnowledgeGapsResponse` schemas to `src/shiruno/api/schemas.py` (contracts/analytics-api.md)
- [X] T027 [US4] Add `get_knowledge_gaps` to `src/shiruno/application/conversation_analytics.py` — tenant-scoped, `outcome = insufficient_information` only, `GROUP BY normalized_question`, ordered by `count` descending then `last_seen_at` descending, `example_question` = the raw `question` text of the most recently seen row in that group, `limit` clamped to `[1, 100]` (research.md §6; contracts/analytics-api.md; depends on T023 — same file as T023, sequential)
- [X] T028 [US4] Add `GET /admin/analytics/knowledge-gaps` to `src/shiruno/api/routers/analytics.py` (depends on T024, T026, T027)

### Tests for User Story 4

- [X] T029 [P] [US4] Create `tests/contract/test_analytics_knowledge_gaps.py` — questions differing only in case/whitespace group into one ranked entry; ranked by frequency descending; `grounded`, `out_of_scope`, `small_talk`, and `unavailable` conversations never contribute even when present alongside `insufficient_information` ones; an empty range or a tenant with no insufficient-information conversations returns a valid empty `items` list (depends on T028)

**Checkpoint**: `uv run pytest tests/contract/test_analytics_knowledge_gaps.py -q` passes independently.

---

## Phase 7: User Story 5 - Administrator reviews the most common questions overall (Priority: P2)

**Goal**: The same deterministic grouping mechanics as knowledge gaps, applied across all outcomes, for general usage-pattern visibility.

**Independent Test**: quickstart.md §6 — seed repeated and distinct questions across outcomes and confirm the most-common-questions view ranks them deterministically for a date range, using only the tenant's own data.

### Implementation for User Story 5

- [X] T030 [US5] Add `get_common_questions` to `src/shiruno/application/conversation_analytics.py` — identical grouping/ranking mechanics to `get_knowledge_gaps` (T027) but across **all** outcomes, not filtered to `insufficient_information` (research.md §6; contracts/analytics-api.md; depends on T027 — same file, sequential)
- [X] T031 [US5] Add `GET /admin/analytics/questions` to `src/shiruno/api/routers/analytics.py`, reusing `KnowledgeGapsResponse`'s shape (depends on T024, T026, T030)

### Tests for User Story 5

- [X] T032 [P] [US5] Create `tests/contract/test_analytics_questions.py` — questions from every outcome (not only `insufficient_information`) contribute to ranking; frequency ranking is deterministic; omitting the date range applies the same documented default as the other analytics endpoints (depends on T031)

**Checkpoint**: `uv run pytest tests/contract/test_analytics_questions.py -q` passes independently.

---

## Phase 8: User Story 6 - No administrator can ever reach another organization's conversation or analytics data (Priority: P1)

**Goal**: Explicit, dedicated proof that every one of the five new capabilities (list, detail, summary, knowledge gaps, common questions) is cross-tenant isolated and fails closed for missing/invalid/expired authentication and for a deactivated tenant.

**Independent Test**: quickstart.md §5 — with two tenants, confirm every new capability performed by one tenant's administrator against the other tenant's data is blocked or empty, and that no client-supplied tenant identifier has any effect.

- [X] T033 [US6] Create `tests/contract/test_conversations_analytics_isolation.py` — with two tenants each holding their own conversation history, Tenant A's administrator never sees Tenant B's data via list, detail, analytics summary, knowledge gaps, or common questions; a client-supplied tenant identifier in the request body, query string, or headers has no effect on any of the five routes; a cross-tenant conversation-detail lookup returns a response identical to a nonexistent one (FR-034, FR-035, FR-036; depends on T016, T020, T024, T028, T031)
- [X] T034 [US6] Extend `tests/contract/test_admin_authorization_fail_closed.py`'s existing parametrized route list (Feature 009) to include the five new routes; prove missing, malformed, and expired authentication all fail closed with the exact same generic `401` status and body already used by every other tenant-scoped admin route, and — reusing the existing Feature 009 deactivated-tenant fixture/test pattern — that an administrator belonging to a deactivated tenant is denied on all five new routes too (mandatory security-boundary coverage; depends on T016, T020, T024, T028, T031)

**Checkpoint**: `uv run pytest tests/contract/test_conversations_analytics_isolation.py tests/contract/test_admin_authorization_fail_closed.py -q` passes — every new capability's tenant boundary is proven end-to-end, mirroring Feature 010's US6 precedent (phased after the endpoints it tests despite being P1).

---

## Phase 9: User Story 7 - Everything that already worked keeps working (Priority: P1)

**Goal**: Confirm the entire pre-existing behavior surface (public chat outcomes, small talk, source hiding, tenant isolation, knowledge administration) is unaffected, now that every new capability from this feature exists.

**Independent Test**: quickstart.md §9-§10 — run the pre-existing contract suites unmodified in intent alongside the full new suite.

- [X] T035 [US7] Run `uv run pytest tests/contract tests/unit tests/integration -q` and confirm 100% pass with original assertion intent preserved — in particular `test_chat.py`, `test_chat_small_talk.py`, `test_documents_auth.py`, and `test_admin_me.py` unmodified in intent (FR-039, FR-040; depends on T012–T034)

**Checkpoint**: Full pre-existing behavior surface plus every new capability verified together, unchanged and correct.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T036 [P] Walk through `quickstart.md` end to end manually against the local `docker compose` stack (`shiruno` project) and confirm every documented expected outcome
- [X] T037 Run `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src tests`, and confirm all clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies (Setup is a no-op) — BLOCKS every later phase.
- **US1 (Phase 3)**: depends only on Foundational.
- **US2 (Phase 4)**: depends on Foundational and, for its own router file, on US1 (T016) already having created `api/routers/conversations.py`.
- **US3 (Phase 5)**: depends only on Foundational.
- **US4 (Phase 6)**: depends on Foundational and, for its own router file and shared analytics module, on US3 (T023, T024) already existing.
- **US5 (Phase 7)**: depends on Foundational and, similarly, on US3/US4 (T023/T024, T026, T027) already existing.
- **US6 (Phase 8)**: depends on US1 (T016), US2 (T020), US3 (T024), US4 (T028), and US5 (T031) — phased after all five despite being P1, since it tests operations they create, exactly mirroring Feature 010's US6 precedent.
- **US7 (Phase 9)**: depends on every prior phase (runs the whole suite together).
- **Polish (Phase 10)**: depends on all prior phases.

### Parallel Opportunities

- T001, T003, T004, T006, and T007 are independent files with no dependencies on each other — run together at the start of Foundational. T002 then depends only on T001; T005 depends only on T004; T008 depends on T001/T003/T005/T007 together; T009 depends only on T008.
- T010 (depends on T003), T011 (depends on T007), and T013 (depends on T002) are independent test files — run together once their respective dependencies land. T012 depends on T009 specifically and is not parallel with T010/T011/T013.
- Within US1, T014 and T015 are independent files — run together, then T016 integrates them.
- Within US2, T018 and T019 are independent files — run together, then T020 integrates them (and depends on T016 already existing).
- Within US3, T022 and T023 are independent files — run together, then T024 integrates them.
- T027 (US4) and T030 (US5) both edit `conversation_analytics.py` — sequential, not parallel, despite being different stories; likewise T028/T031 both edit `analytics.py` — sequential. This mirrors research.md §10's decision to keep the three analytics query functions in one cohesive module.
- T033 and T034 (US6) are independent files — run together once their shared dependencies (T016, T020, T024, T028, T031) land.
- T036 (Polish) has no dependency on T037 and can start as soon as everything else is done; T037 should run last as the final gate.

---

## Parallel Example: Foundational Phase

```bash
# Launch the independent Foundational tasks together:
Task: "Add ConversationRecord model + enums (T001)"
Task: "Create question_normalization.py (T003)"
Task: "Extend BudgetCheckResult with reason (T004)"
Task: "Add new config settings (T006)"
Task: "Create resolve_public_tenant.py (T007)"
```

---

## Implementation Strategy

### MVP First (Foundational + US1 + US6's route coverage deferred, US7)

This feature's core, non-negotiable promise is "visitor conversations are
durably and safely recorded, and an administrator can see their own
tenant's data and never another's." The absolute minimum slice that
delivers real, verifiable value is:

1. Complete Phase 2: Foundational — the recording mechanism itself, fully
   proven correct (T012 is the single most important test in this
   feature).
2. Complete Phase 3: User Story 1 — validate independently. This alone
   already delivers "an administrator can see what visitors are asking."
3. **STOP and VALIDATE**: run `test_chat_conversation_recording.py` and
   `test_conversations_list.py` together — this is the point at which
   real conversation data exists, is trustworthy, and is visible to its
   correct tenant only.

### Incremental Delivery

Foundational (recording proven correct) → US1 (list) → US2 (detail) → US3
(summary) → US4 (knowledge gaps) → US5 (common questions) → US6 (isolation
proven across all five) → US7 (full non-regression) → Polish.

Each story adds one new, independently testable capability without
touching the previous ones' behavior — the only inter-story coupling is
file-level (US4/US5 extend the same `conversation_analytics.py`/
`analytics.py` files US3 creates, per the Parallel Opportunities note
above), never behavioral.
