---

description: "Task list template for feature implementation"
---

# Tasks: Albertos RAG Support Chatbot (MVP)

**Input**: Design documents from `/specs/001-albertos-rag-chatbot/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md (all present)

**Tests**: Included — the spec explicitly requires them (FR-054, FR-055, SC-010) and the project constitution makes security-relevant test coverage NON-NEGOTIABLE (Principle XI). Tests are written before the implementation they cover, per story. Every automated test (unit, integration, contract) uses the fake, deterministic `LLMProvider`/`EmbeddingProvider` doubles from Foundational (T023, T024) — no automated test loads the real `sentence-transformers` model or calls the real Anthropic API; the real `LocalSentenceTransformerEmbeddingProvider` is exercised only via quickstart.md's manual/runtime scenarios.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P4) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Every task lists an exact file path

## Path Conventions

Single backend project (plan.md "Structure Decision: Single project, Option 1"):

- App code: `src/albercik_chatbot/`
- Tests: `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/fakes/`
- Migrations: `alembic/`
- Root: `docker-compose.yml`, `Dockerfile`, `alembic.ini`, `.env.example`, `pyproject.toml`

## Design Constraints Carried Into These Tasks

Three cross-cutting rules apply to multiple tasks below; stated once here rather than repeated everywhere:

1. **Retry ownership**: bounded provider retries live in exactly one layer — `AnthropicLLMProvider` (T017). No other layer (`ask_question.py`, `upload_document.py`, or any test double) retries a provider call; application code receives either one successful result or one post-retry failure. T018 and T060 exist specifically to prove retries cannot multiply across layers.
2. **Local embedding lifecycle**: `LocalSentenceTransformerEmbeddingProvider` (T019) loads its model at most once per application process — never per call or per request. T020 proves this without downloading real weights. No unit, integration, or contract test loads the real model; all use `FakeEmbeddingProvider` (T024). No separate embedding-serving process/container is introduced — the model runs in-process, CPU-only.
3. **Usage/budget accounting**: the MVP's hard monetary/token budget covers Claude (LLM) usage only. `UsageRecord.provider_kind` (`llm` | `embedding`, data-model.md) distinguishes the two; local embedding calls may be recorded for operational visibility (T065) but MUST NEVER be summed into, or otherwise reduce, the LLM budget computed in T063.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton, dependency management, and local/dev infrastructure — no application behavior yet.

- [X] T001 Create the full directory skeleton with `__init__.py` placeholders per plan.md Project Structure: `src/albercik_chatbot/{api/routers,application,domain,providers/llm,providers/embedding,persistence,infra}`, `tests/{unit,integration,contract,fakes}`, `alembic/versions`
- [X] T002 Add project dependencies to `pyproject.toml` via `uv`: `fastapi`, `uvicorn`, `sqlalchemy>=2`, `alembic`, `pgvector`, `anthropic`, `sentence-transformers` (CPU `torch`), `bcrypt`, `pyjwt`, `python-multipart`, `pydantic-settings`; dev group: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy` (plan.md Primary Dependencies; research.md §4/§4a — no Voyage/OpenAI embedding client)
- [X] T003 [P] Configure `ruff` (lint + format) and `mypy` (type checking) in `pyproject.toml` (Constitution Principle XII — type hints throughout)
- [X] T004 [P] Create `docker-compose.yml` with `db` (Postgres + `pgvector` image), `db-test`, and `app` services (research.md §8) — no separate embedding-service container (Design Constraint 2)
- [X] T005 [P] Create `Dockerfile`: CPU-only Python base image; pre-download `intfloat/multilingual-e5-small` weights at build time so first container start has no runtime dependency on Hugging Face Hub network access (research.md §4a, quickstart.md)
- [X] T006 [P] Create `.env.example` with safe placeholder values: `ANTHROPIC_API_KEY`, `AUTH_JWT_SECRET`, `EMBEDDING_MODEL_NAME` (default `intfloat/multilingual-e5-small`), `DATABASE_URL`, `LLM_ENABLED`, chunking/retrieval/rate-limit/budget config keys — **no embedding-provider API key of any kind** (FR-051; research.md §4a)
- [X] T007 Create `alembic.ini` and `alembic/env.py` scaffold wired to the project's SQLAlchemy metadata, with an empty `alembic/versions/`

**Checkpoint**: Repo builds, dependencies install, containers start (no app logic yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every user story depends on — config, schema, provider boundaries with test doubles, error handling. No user-facing behavior yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 Implement `src/albercik_chatbot/config.py`: Pydantic Settings covering `EMBEDDING_MODEL_NAME`, `LLM_ENABLED`, `CHUNK_SIZE_CHARS`/`CHUNK_OVERLAP_CHARS`, retrieval `TOP_K`/relevance threshold, `PROVIDER_MAX_RETRIES`, rate-limit and budget thresholds, `AUTH_JWT_SECRET`/JWT expiry, `DATABASE_URL`, max upload size, max question length (plan.md config.py; research.md §2–7)
- [X] T009 Implement `src/albercik_chatbot/persistence/database.py`: SQLAlchemy engine/session factory, `pgvector` extension enablement
- [X] T010 Implement `src/albercik_chatbot/persistence/models.py`: ORM models for `Administrator`, `KnowledgeDocument`, `DocumentChunk` (`embedding` = `vector(384)`), `UsageRecord` (`provider_kind` enum `llm`/`embedding` is the field T063 filters on and T065 writes to — see Design Constraint 3), `RateLimitWindow` exactly per data-model.md
- [X] T011 Create the initial Alembic migration in `alembic/versions/` from `models.py`: all five tables, `CREATE EXTENSION IF NOT EXISTS vector`, `HNSW` index on `document_chunks.embedding` (`vector_cosine_ops`), index on `document_chunks.document_id`, unique `(document_id, position)`, composite PK `(source_key, window_start)` on `rate_limit_windows` (data-model.md; research.md §6) — depends on T010
- [X] T012 [P] Implement `src/albercik_chatbot/infra/logging.py`: structured, privacy-conscious logging config that never logs passwords/tokens/API keys/full content (FR-052, Principle IX)
- [X] T013 [P] Implement `src/albercik_chatbot/infra/security.py`: `bcrypt` password hashing and JWT issue/verify helpers (research.md §1)
- [X] T014 [P] Implement `src/albercik_chatbot/api/errors.py`: exception → HTTP response mapping; no stack traces, secrets, or internal config in any response body (FR-049, FR-050, Principle VIII)
- [X] T015 [P] Implement `src/albercik_chatbot/providers/llm/protocol.py`: `LLMProvider` `Protocol` (Principle V)
- [X] T016 [P] Implement `src/albercik_chatbot/providers/embedding/protocol.py`: `EmbeddingProvider` `Protocol`, documented 384-dim contract (Principle VI, FR-024, FR-034)
- [X] T017 Implement `src/albercik_chatbot/providers/llm/anthropic_provider.py`: `AnthropicLLMProvider` implementing `LLMProvider` — **the only layer in the codebase that retries a provider call**, bounded per research.md §7 (max `PROVIDER_MAX_RETRIES` attempts, exponential backoff, no retry on 4xx); returns exactly one success or one post-retry failure to its caller, which MUST NOT retry again (Design Constraint 1) — depends on T015
- [X] T018 [P] Unit test proving `AnthropicLLMProvider` is the sole retry layer: inject a fake transport that fails a controlled number of times, assert the provider makes at most `PROVIDER_MAX_RETRIES + 1` attempts total and returns exactly one outcome, in `tests/unit/test_anthropic_provider_retries.py` — depends on T017
- [X] T019 Implement `src/albercik_chatbot/providers/embedding/local_sentence_transformer_provider.py`: `LocalSentenceTransformerEmbeddingProvider` — the only file in the codebase importing `sentence_transformers`; reads `EMBEDDING_MODEL_NAME` from settings and loads the model **at most once per application process** (never per call/request), reusing that one instance for every `embed()` call (research.md §4a; Design Constraint 2) — depends on T008, T016
- [X] T020 [P] Unit test proving `LocalSentenceTransformerEmbeddingProvider` loads its model at most once per process: mock `sentence_transformers.SentenceTransformer` (no real weights downloaded or loaded) and assert the constructor is invoked exactly once across repeated provider construction/`embed()` calls, in `tests/unit/test_local_embedding_provider_lifecycle.py` — depends on T019
- [X] T021 Implement `src/albercik_chatbot/main.py`: FastAPI app factory; constructs the process-wide `LocalSentenceTransformerEmbeddingProvider` and `AnthropicLLMProvider` once at startup (never per request) and injects them via dependencies (research.md §4a) — depends on T017, T019
- [X] T022 [P] Implement `src/albercik_chatbot/api/routers/health.py`: `GET /health` (contracts/openapi.yaml)
- [X] T023 [P] Implement `tests/fakes/fake_llm_provider.py`: deterministic in-memory `LLMProvider` test double, no network, no retry loop of its own (research.md §8)
- [X] T024 [P] Implement `tests/fakes/fake_embedding_provider.py`: deterministic in-memory `EmbeddingProvider` test double producing fixed 384-dim vectors from input text (e.g. seeded hash) — **MUST NOT import `sentence_transformers`**; this is the only `EmbeddingProvider` any automated test injects (research.md §4a/§8; Design Constraint 2)
- [X] T025 Implement `tests/conftest.py`: pytest fixtures for a real-Postgres session (integration tests), the fake providers from T023/T024 (unit/integration/contract tests alike), and an `httpx.AsyncClient` wired to the app factory with fakes injected (research.md §8) — depends on T021, T023, T024

**Checkpoint**: Foundation ready — schema exists, providers are swappable and testable, no story-specific behavior yet.

---

## Phase 3: User Story 1 - Visitor gets a grounded, in-scope answer (Priority: P1) 🎯 MVP

**Goal**: A public visitor asks a question; the system returns a grounded answer with sources, an insufficient-information notice, or a scope-limited notice — the three outcomes FR-027 requires.

**Independent Test**: Seed `document_chunks` directly (no upload endpoint needed), then send three questions — one answerable, one Albertos-related but uncovered, one unrelated — and confirm each produces the matching outcome.

### Tests for User Story 1 ⚠️ write first, confirm they fail

- [ ] T026 [P] [US1] Unit tests for the deterministic paragraph-aware chunker in `tests/unit/test_chunking.py` (FR-018–FR-021)
- [ ] T027 [P] [US1] Unit tests for the Albertos-scope classifier, including mixed-intent → whole message out-of-scope, in `tests/unit/test_scope.py` (FR-027c, FR-030, Clarifications 2026-08-17)
- [ ] T028 [P] [US1] Unit tests for relevance-threshold / insufficient-context decision logic in `tests/unit/test_retrieval.py` (FR-026, FR-027b)
- [ ] T029 [P] [US1] Unit tests for trusted-instructions vs. untrusted-retrieved-context prompt assembly in `tests/unit/test_prompting.py` (Principle III, FR-028, FR-031)
- [ ] T030 [P] [US1] Contract test: `POST /api/v1/chat` returns `grounded` / `insufficient_information` / `out_of_scope` with fake providers, sources present only when grounded, in `tests/contract/test_chat.py` (Acceptance Scenarios US1.1–US1.4)
- [ ] T031 [P] [US1] Integration test: real `pgvector` cosine similarity search Top-K ordering and threshold behavior against `db-test`, seeding chunks with `FakeEmbeddingProvider` vectors rather than the real model, in `tests/integration/test_retrieval_pgvector.py` (research.md §6, §8; Design Constraint 2)

### Implementation for User Story 1

- [ ] T032 [US1] Implement `src/albercik_chatbot/domain/chunking.py`: deterministic paragraph-aware character chunker (research.md §5)
- [ ] T033 [US1] Implement `src/albercik_chatbot/domain/scope.py`: Albertos-scope classifier, Polish-language (FR-027c, FR-030, FR-030a)
- [ ] T034 [US1] Implement `src/albercik_chatbot/domain/retrieval.py`: relevance-threshold evaluation and insufficient-context decision (FR-026, FR-027b)
- [ ] T035 [US1] Implement `src/albercik_chatbot/domain/prompting.py`: assembles trusted system instructions separately from a clearly delimited untrusted retrieved-context block, plus source-reference extraction (Principle III, FR-028, FR-029, FR-031)
- [ ] T036 [US1] Implement `src/albercik_chatbot/persistence/repositories.py` chunk similarity-search query: cosine `<=>` operator, configurable Top-K, excludes soft-deleted documents/chunks (data-model.md) — depends on T010, T011
- [ ] T037 [US1] Implement `src/albercik_chatbot/application/ask_question.py`: embed the question, retrieve chunks, apply domain decision (T032–T036), call the LLM **once** and handle its single success/failure result (no retry loop here — retries belong solely to `AnthropicLLMProvider`, Design Constraint 1), assemble the response — depends on T017, T019, T032–T036
- [ ] T038 [US1] Implement `src/albercik_chatbot/api/schemas.py` `ChatRequest`/`ChatResponse`/`SourceReference` mirroring `contracts/openapi.yaml`
- [ ] T039 [US1] Implement `src/albercik_chatbot/api/routers/chat.py`: `POST /api/v1/chat`, no authentication required (FR-002), Polish-language responses (FR-030a) — depends on T037, T038
- [ ] T040 [US1] Wire the chat router into the app factory in `src/albercik_chatbot/main.py` — depends on T039

**Checkpoint**: User Story 1 is fully functional and independently testable (seed chunks → ask → get grounded/insufficient/out-of-scope with sources).

---

## Phase 4: User Story 2 - Administrator manages the Albertos knowledge base (Priority: P2)

**Goal**: An authenticated Administrator signs in, uploads/lists/deletes `.txt` knowledge documents; a Public User can do none of this.

**Independent Test**: Sign in, upload a distinctive `.txt` file, confirm it's listed, confirm US1's chat endpoint answers from it, delete it, confirm the same question falls back to insufficient-information.

### Tests for User Story 2 ⚠️ write first, confirm they fail

- [ ] T041 [P] [US2] Contract test: `/api/v1/documents` (POST/GET) and `/api/v1/documents/{id}` (DELETE) reject a Public User and unauthenticated requests in `tests/contract/test_documents_auth.py` (FR-003, FR-004, FR-007, SC-004)
- [ ] T042 [P] [US2] Contract test: upload validation — non-`.txt`, invalid UTF-8, empty content, oversized, path-traversal-style filename — in `tests/contract/test_documents_upload.py` (FR-009–FR-013)
- [ ] T043 [P] [US2] Contract test: list shows uploaded documents; delete removes it from the list in `tests/contract/test_documents_lifecycle.py` (FR-014–FR-016)
- [ ] T044 [P] [US2] Contract test: `POST /api/v1/auth/login` success and generic invalid-credentials failure (no field-level leak) in `tests/contract/test_auth_login.py` (FR-008, Acceptance Scenario US2.6)
- [ ] T045 [P] [US2] Integration test: an uploaded document's chunks become retrievable end-to-end against real `pgvector`, and deletion excludes them immediately (no restart) in `tests/integration/test_document_lifecycle.py` (SC-006, SC-007) — uses `FakeEmbeddingProvider` injected into the app under test, not the real model (Design Constraint 2)

### Implementation for User Story 2

- [ ] T046 [US2] Implement `src/albercik_chatbot/cli.py` `create-admin` command: hash password via `infra/security.py`, insert an `Administrator` row out-of-band (FR-004a) — depends on T010, T013
- [ ] T047 [US2] Implement `src/albercik_chatbot/api/routers/auth.py`: `POST /api/v1/auth/login` issuing a JWT via `infra/security.py`, generic failure response (FR-008) — depends on T013
- [ ] T048 [US2] Implement the `get_current_administrator` auth dependency in `src/albercik_chatbot/api/deps.py`: validates the JWT bearer token, checks `is_active` — depends on T013
- [ ] T049 [US2] Implement `src/albercik_chatbot/application/upload_document.py`: validate upload (extension/UTF-8/size/non-empty, filename never used as a path), chunk via `domain/chunking.py`, embed each chunk via the injected `EmbeddingProvider` (usage-record writing for these embedding calls is added later, in T065), store `KnowledgeDocument` + `DocumentChunk` rows, `processing` → `ready`/`failed` (FR-009–FR-024) — depends on T019, T032
- [ ] T050 [US2] Implement `src/albercik_chatbot/application/list_documents.py`: list active (non-deleted) documents
- [ ] T051 [US2] Implement `src/albercik_chatbot/application/delete_document.py`: soft-delete (`deleted_at`), immediate exclusion from retrieval (FR-015, FR-016)
- [ ] T052 [US2] Implement `src/albercik_chatbot/api/routers/documents.py`: `POST`/`GET /api/v1/documents`, `DELETE /api/v1/documents/{document_id}`, admin-only via `deps.py` — depends on T048–T051
- [ ] T053 [US2] Wire `auth.py` and `documents.py` routers into the app factory in `src/albercik_chatbot/main.py` — depends on T047, T052

**Checkpoint**: User Stories 1 and 2 both work independently (US2 upload feeds US1's already-built retrieval path).

---

## Phase 5: User Story 3 - Public endpoint resists abuse and runaway cost (Priority: P3)

**Goal**: Every `/chat` request — admin or public — is subject to rate limiting, size/length limits, bounded retries, a budget, and a kill switch, uniformly, fail-closed.

**Independent Test**: Configure conservative limits, burst past the rate cap and an over-length question, confirm both rejected pre-provider-call; flip the kill switch, confirm a safe fallback with no provider call, for both a Public User and an Administrator.

### Tests for User Story 3 ⚠️ write first, confirm they fail

- [ ] T054 [P] [US3] Unit tests for the Postgres-backed fixed-window rate limiter in `tests/unit/test_rate_limit.py` (research.md §2)
- [ ] T055 [P] [US3] Unit tests for budget-check and fail-closed-on-DB-error behavior, **including a case proving `provider_kind='embedding'` usage rows never count toward or exhaust the LLM budget**, in `tests/unit/test_budget.py` (research.md §3, FR-045; Design Constraint 3)
- [ ] T056 [P] [US3] Contract test: rate limit exceeded → `429` + `Retry-After`, no `usage_records` row for the rejected request, in `tests/contract/test_chat_rate_limit.py` (Acceptance Scenario US3.1, FR-041)
- [ ] T057 [P] [US3] Contract test: over-length question / oversized payload → `400`/`413` before any embedding or provider call, in `tests/contract/test_chat_size_limits.py` (Acceptance Scenario US3.2, FR-038, FR-039)
- [ ] T058 [P] [US3] Contract test: `LLM_ENABLED=false` → `outcome: "unavailable"`, no provider call, identical for Administrator and Public User, in `tests/contract/test_chat_kill_switch.py` (Acceptance Scenarios US3.3, US3.7, FR-043)
- [ ] T059 [P] [US3] Contract test: configured LLM budget exhausted → subsequent questions get `"unavailable"`, no further LLM calls; separately confirm heavy embedding volume alone (many chunk/query embeddings, zero or few LLM calls) does **not** exhaust the budget, in `tests/contract/test_chat_budget.py` (Acceptance Scenario US3.4, FR-044; Design Constraint 3)
- [ ] T060 [P] [US3] Contract test: provider failures are retried a bounded number of times by `AnthropicLLMProvider` only, then a safe failure response — assert the fake/mock LLM provider is invoked at most `PROVIDER_MAX_RETRIES + 1` times total for the request, proving `ask_question.py` adds no further retry loop on top of T017/T018, in `tests/contract/test_chat_provider_failure.py` (Acceptance Scenario US3.6, FR-036; Design Constraint 1)
- [ ] T061 [P] [US3] Contract test: request body cannot override model/max-tokens/Top-K/system instructions in `tests/contract/test_chat_no_client_override.py` (Acceptance Scenario US3.5, FR-035)

### Implementation for User Story 3

- [ ] T062 [US3] Implement `src/albercik_chatbot/infra/rate_limit.py`: Postgres-backed fixed-window counter, trusted-proxy source-key resolution only (research.md §2, FR-040) — depends on T010, T011
- [ ] T063 [US3] Implement `src/albercik_chatbot/infra/budget.py`: query `usage_records` **filtered to `provider_kind='llm'` only** for the configured budget window — local embedding calls carry no per-call provider cost and MUST NOT reduce or count toward this budget (Design Constraint 3) — read the `LLM_ENABLED` kill switch, fail closed on any DB/verification error (research.md §3, FR-043–FR-046) — depends on T010, T011
- [ ] T064 [US3] Add the rate-limit guard dependency to `src/albercik_chatbot/api/deps.py` and apply it to `/chat` (`429` + `Retry-After`) — depends on T062
- [ ] T065 [US3] Extend `src/albercik_chatbot/application/ask_question.py` and `application/upload_document.py` to record usage and enforce cost/abuse controls: enforce max question length/payload size before embedding (`ask_question.py`), check the kill switch and budget (T063) before any LLM call (fail closed) — the retry policy itself stays solely in `AnthropicLLMProvider` (Design Constraint 1); `ask_question.py` only ever handles its single success/failure result — and write a `UsageRecord` row after every provider call: `provider_kind='llm'` for the Claude call (counted by T063's budget query) and `provider_kind='embedding'` for every embedding call in both `ask_question.py` (query-time) and `upload_document.py` (per-chunk, at ingestion) — embedding rows are operational visibility only and MUST NOT feed the budget calculation (Design Constraint 3) — depends on T037, T049, T063
- [ ] T066 [US3] Add a bounded-concurrency guard for `/chat` in `src/albercik_chatbot/api/routers/chat.py` or `main.py` (FR-042)
- [ ] T067 [US3] Add request-timeout enforcement for `/chat` (FR-038)
- [ ] T068 [US3] Extend `api/schemas.py`/`chat.py` response handling so the kill-switch/budget path returns `outcome: "unavailable"` with a safe message and no internal config/budget detail (FR-046) — depends on T065

**Checkpoint**: User Stories 1–3 all independently functional; the public endpoint cannot generate uncontrolled cost.

---

## Phase 6: User Story 4 - System resists prompt injection and untrusted content (Priority: P4)

**Goal**: Prove the defenses already built into `domain/prompting.py` (US1) and `application/upload_document.py` (US2) hold under adversarial visitor messages and adversarial document content, with no bypass of normal auth/rate/cost controls.

**Independent Test**: Send a visitor message containing an injection attempt; separately upload a document with an embedded instruction and ask a question that retrieves it. Confirm neither leaks system instructions/credentials nor bypasses scope, auth, rate, or budget controls.

### Tests for User Story 4 ⚠️ write first, confirm they fail

- [X] T069 [P] [US4] Contract test: visitor injection attempt ("ignore previous instructions…", "reveal your system prompt/API key") does not leak instructions/credentials and scope control still applies, in `tests/contract/test_prompt_injection_visitor.py` (Acceptance Scenario US4.1, FR-031, FR-037)
- [X] T070 [P] [US4] Integration test: upload a document whose content contains an embedded instruction, ask a question that retrieves it, confirm the answer does not follow the embedded instruction, in `tests/integration/test_prompt_injection_document.py` (Acceptance Scenario US4.2, FR-031) — uses the fake providers from Foundational, not the real model or a real LLM call — depends on T049
- [X] T071 [P] [US4] Contract test: an injection attempt is still subject to normal auth/rate/budget controls — no bypass — in `tests/contract/test_prompt_injection_no_bypass.py` (Acceptance Scenario US4.3)

### Implementation for User Story 4

- [X] T072 [US4] Review `src/albercik_chatbot/domain/prompting.py` against the injection test fixtures from T069/T070 and harden the untrusted-context delimiting if any test fails (Principle III)
- [X] T073 [P] [US4] Add reusable malicious-content fixtures (visitor message + uploaded document) in `tests/fixtures/prompt_injection.py` for T069–T071

**Checkpoint**: All four user stories independently functional and mutually reinforcing.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Auditability, remaining edge cases, and final verification against quickstart.md and the constitution's testing gate.

- [X] T074 [P] Add audit logging for admin actions (login attempt, upload, delete) identifying the acting Administrator, no sensitive content, in `api/routers/auth.py` and `api/routers/documents.py` (FR-053, Principle IX)
- [X] T075 [P] Add tests for remaining spec.md Edge Cases not yet covered (empty knowledge base → insufficient-information; ambiguous-but-plausible question routed through retrieval; delete of an already-deleted/unknown document → safe `404`) in `tests/unit/` and `tests/contract/`
- [X] T076 Run quickstart.md Scenarios 1–5 end-to-end against the Docker Compose stack and record results
- [X] T077 [P] Verify `.env.example`, `README`, and quickstart.md setup commands match the final implementation (no stale `VOYAGE_API_KEY` or other drift)
- [X] T078 Run the full suite — `uv run pytest tests/unit tests/integration tests/contract` — with no `ANTHROPIC_API_KEY` set and confirm zero real provider calls, no `sentence_transformers` model load outside `LocalSentenceTransformerEmbeddingProvider`, no retry-count multiplication (T018/T060 both pass), and correct budget category separation (T055/T059 both pass) (Principle XI, SC-010)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US1 (Phase 3)**: Depends only on Foundational.
- **US2 (Phase 4)**: Depends only on Foundational for its own implementation tasks; its *Independent Test* additionally exercises the already-built US1 `/chat` endpoint to prove upload → retrieval, which is why US1 is built first even though the two stories don't share implementation files.
- **US3 (Phase 5)**: Depends on Foundational **and US1** — it extends `ask_question.py` and `/chat` (T065, T068) rather than duplicating them, and also extends US2's `upload_document.py` (T065) to add embedding usage-recording; per the spec's own "Why this priority" for User Story 3, the core answer-generation behavior is validated first in a controlled setting before the endpoint is hardened for public exposure.
- **US4 (Phase 6)**: Depends on Foundational, **US1** (`domain/prompting.py`) and **US2** (`application/upload_document.py`, needed by T070) — it is explicitly "a defense-in-depth requirement layered on top of the working RAG flow and the ingestion pipeline" per spec.md.
- **Polish (Phase 7)**: Depends on all four user stories.

### Within Each User Story

- Tests are written first and MUST fail before implementation begins.
- Domain logic → persistence/application → API routes → router wiring into `main.py`.

### Parallel Opportunities

- All Setup tasks marked [P] (T003–T006) can run together.
- Within Foundational, T012–T016, T018, T020, T022–T024 (marked [P]) can run together once their respective single dependency lands.
- Within each story, all [P]-marked test tasks can run together before that story's implementation tasks begin.
- US2's tests (T041–T045) can be written in parallel with US1's implementation, since they target different files — but US2 code should not be written until Foundational is done and US1's chat endpoint exists for its Independent Test to exercise.

---

## Parallel Example: User Story 1

```bash
# Tests together:
Task: "Unit tests for chunker in tests/unit/test_chunking.py"
Task: "Unit tests for scope classifier in tests/unit/test_scope.py"
Task: "Unit tests for retrieval decision in tests/unit/test_retrieval.py"
Task: "Unit tests for prompt assembly in tests/unit/test_prompting.py"
Task: "Contract test for POST /api/v1/chat in tests/contract/test_chat.py"
Task: "Integration test for pgvector retrieval in tests/integration/test_retrieval_pgvector.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: seed chunks directly, confirm all three chat outcomes with sources
5. This validates the core RAG hypothesis in a controlled (non-public) setting — do **not** expose `/chat` publicly yet, since Phase 5 (US3) is what makes that safe.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → grounded/insufficient/out-of-scope answers work against seeded data (internal validation only).
3. US2 → admin can populate/manage the knowledge base that US1 answers from.
4. US3 → `/chat` becomes safe for public exposure (rate limits, budget, kill switch, bounded retries, correct usage/budget accounting).
5. US4 → prompt-injection resistance verified end-to-end.
6. Polish → audit logging, remaining edge cases, quickstart validation, full-suite provider-free run.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. Once Foundational is done: Developer A takes US1; Developer B can start US2's tests/CLI/auth (T041–T048) in parallel, holding US2's upload/list/delete implementation until US1's chat path exists to validate against.
3. US3 and US4 start once US1 (and, for US4, US2) are complete.
