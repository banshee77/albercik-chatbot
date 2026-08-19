# Implementation Plan: Shiruno Repository & Product Architecture

**Branch**: `008-shiruno-repository-architecture` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-shiruno-repository-architecture/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Behavior-preserving repository/product architecture refactor: rename the
reusable Python package `src/albercik_chatbot` → `src/shiruno` (research.md
§1) and every dependent import/config/script/doc; keep the Albertos public
website (`public_site/`) physically nested inside the `shiruno` package
rather than relocating it (research.md §2), making the reusable-vs-
customer-specific boundary obvious through documentation instead; add a
new `docs/architecture.md` describing the current architecture plus the
forward-looking, unimplemented Shiruno Widget and Shiruno Platform / Admin
boundaries; rewrite the root `README.md` around the Shiruno-product /
Albertos-customer framing; and leave every runtime behavior, API contract,
RAG behavior, test outcome, and evaluation baseline byte-for-byte
unchanged. No new dependencies, services, database schema, or HTTP surface
are introduced.

## Technical Context

**Language/Version**: Python 3.14 (unchanged)

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, pgvector,
sentence-transformers, Anthropic SDK, PyJWT, bcrypt, uvicorn (all
unchanged — this feature renames the package that depends on them, not
the dependencies themselves)

**Storage**: PostgreSQL + pgvector (unchanged; no schema/migration change — see research.md §4 for why Postgres credential *names* are also explicitly left unchanged)

**Testing**: pytest (unit/contract/integration), `tests/fakes/` for
provider doubles — unchanged; only import paths inside test files move
(research.md §1, contracts/runtime-paths.md)

**Target Platform**: Linux server via Docker Compose (unchanged; no
Kubernetes, no new orchestration platform — constitution Principle XIII,
XIV)

**Project Type**: Single-project web service (FastAPI backend + server-
rendered public website), `src/` layout, `uv` for dependency management —
unchanged structure, renamed package

**Performance Goals**: N/A — no performance target changes; behavior
preservation (identical latency/outcome characteristics to before this
feature) is the only relevant bar, verified via the existing test suite
and eval benchmark, not a new numeric target (spec Assumptions)

**Constraints**: Zero intentional behavior change to the public website,
chat API, RAG pipeline, auth, cost/abuse controls, or eval baseline
(spec FR-013–FR-020); no compatibility alias for the old package name
without a documented reason (FR-011); no empty placeholder directories
(FR-007)

**Scale/Scope**: One reusable package (~29 modules), ~51 test files,
2 Docker/Compose files, 1 Alembic env, 3 scripts, 2 markdown docs with
direct references — see research.md §1 for the full inventory. Single
customer (Albertos) today; architecture must make a second customer
additively pluggable later without implying one exists now.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature is a pure rename/reorganization/documentation change with no
new runtime behavior, so most principles apply as "must not regress"
rather than "must newly satisfy." Evaluated against
`.specify/memory/constitution.md` v3.1.0:

| Principle | Status | Notes |
|---|---|---|
| I. Security by Default | ✅ Pass | No auth/authz/secrets-handling code changes; `.env`/secrets never touched or newly exposed (FR-030, edge cases) |
| II. Tenancy Posture (Single-Tenant MVP) | ✅ Pass | Explicitly reinforced, not violated — no `organization_id`, tenant table, or tenant middleware introduced (FR-022, non-goals); the rename/boundary work is exactly the "clean layering" this principle asks for so a *future* tenancy change is additive |
| III. Secure RAG | ✅ Pass | Retrieval/prompting/grounding logic untouched (FR-014) |
| IV. Secure Document Ingestion | ✅ Pass | Upload validation code untouched |
| V. LLM Provider Neutrality | ✅ Pass | `LLMProvider` Protocol and both implementations move (rename) but are not redesigned (FR-015) |
| VI. Embedding Provider Neutrality | ✅ Pass | Same as V, for embeddings |
| VII. Provider and Cloud Neutrality | ✅ Pass | Docker Compose remains the only orchestration; no cloud-specific dependency added (FR-026, FR-028) |
| VIII. API Security | ✅ Pass | No new endpoint, no change to validation/authz ordering |
| IX. Privacy and Logging | ✅ Pass | Logging code untouched; log line content unaffected by module rename |
| X. Cost Safety (NON-NEGOTIABLE) | ✅ Pass | Rate limit/budget/kill-switch/concurrency code untouched (FR-016) |
| XI. Testing Discipline (NON-NEGOTIABLE) | ✅ Pass | Existing security/RBAC/cost tests preserved with original assertion semantics (FR-020); no test weakened to pass |
| XII. Engineering Quality Principles | ✅ Pass | No new abstraction introduced; module boundaries already existing are documented, not re-architected |
| XIII. Simplicity for MVP | ✅ Pass | Explicitly rejects speculative `apps/`/`packages/`/`examples/` scaffolding (research.md §3, FR-007); rejects a compatibility shim (FR-011); rejects relocating `public_site` where doing so would only serve the target diagram cosmetically (research.md §2) |
| XIV. Approved MVP Technology Stack | ✅ Pass | No technology added or removed; Python/FastAPI/PostgreSQL/pgvector/SQLAlchemy/Alembic/Anthropic/Docker Compose/`uv` all unchanged |

**Gate result**: PASS — no violations, no Complexity Tracking entries
required. Re-checked after Phase 1 design below.

### Post-Phase-1 re-check

Phase 1 outputs (data-model.md, contracts/, quickstart.md) confirm the
design stays within the boundaries evaluated above: no new entities, no
new HTTP contract, no new infrastructure. The one governance-adjacent
item — `constitution.md` itself still saying "Albercik Chatbot"
(research.md §5) — is explicitly deferred to a separate
`/speckit-constitution` amendment rather than folded into this feature's
tasks, so it does not affect this gate. **Gate result: PASS, unchanged.**

## Project Structure

### Documentation (this feature)

```text
specs/008-shiruno-repository-architecture/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── http-api-unchanged.md
│   └── runtime-paths.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Single-project web service, `src/` layout (unchanged shape; package
renamed). No frontend/backend split, no mobile target — this project type
was already "Option 1: Single project" before this feature and remains so.

```text
src/shiruno/                      # was src/albercik_chatbot/ (research.md §1)
├── api/                          # Shiruno Platform (reusable): routers, schemas, error mapping
│   └── routers/
├── application/                  # Shiruno Platform (reusable): use-case orchestration
├── domain/                       # Shiruno Platform (reusable): chunking, retrieval, prompting, scope, small-talk
├── infra/                        # Shiruno Platform (reusable): security, logging, audit, rate limit, budget, concurrency
├── persistence/                  # Shiruno Platform (reusable): SQLAlchemy models, session, repositories
├── providers/                    # Shiruno Platform (reusable): LLM/embedding Protocols + implementations
│   ├── embedding/
│   └── llm/
├── public_site/                  # Albertos Reference Implementation (customer-specific) — stays here, not
│   ├── data/                     #   relocated to a top-level examples/ tree (research.md §2); module
│   ├── static/                   #   docstring + docs/architecture.md make the boundary explicit instead
│   └── templates/
├── cli.py                        # `create-admin` out-of-band provisioning
├── config.py                     # Settings (env-driven)
└── main.py                       # FastAPI app factory — composition root wiring platform + Albertos site

docs/                              # NEW — forward-looking architecture documentation (research.md §3, §6)
└── architecture.md                # current architecture + future Shiruno Widget / Admin Platform boundaries

tests/
├── contract/
├── integration/
├── unit/
├── fakes/
├── fixtures/
└── conftest.py                    # imports updated to `shiruno.*`; hardcoded test DB URL unchanged (research.md §4)

alembic/
└── env.py                         # imports updated to `shiruno.config` / `shiruno.persistence.models`

eval/
├── README.md                      # title/prose rebranded (research.md §1)
└── questions.jsonl                # UNCHANGED — dataset and expected outcomes are frozen (FR-019)

scripts/
├── run_eval.py                    # imports + CLI subprocess reference updated to `shiruno.*`
├── rag_calibration.py             # imports updated to `shiruno.*`
└── compare_eval_runs.py           # no package import — unaffected

pyproject.toml                     # [project].name → "shiruno"; console script → shiruno = "shiruno:main"
Dockerfile                         # CMD's uvicorn factory target → shiruno.main:create_app
docker-compose.yml                 # app service unaffected beyond image rebuild; DB credential names unchanged (research.md §4)
README.md                          # rewritten: Shiruno product / Albertos customer framing, current + target architecture (FR-024, FR-025)
```

**Structure Decision**: Keep the existing single-project `src/` layout;
rename `src/albercik_chatbot/` → `src/shiruno/` in place (research.md §1).
Do not relocate `public_site/` out of the package (research.md §2) — the
reusable-platform/Albertos-reference-implementation boundary already
exists at the `public_site/` vs. everything-else module level and is made
legible through documentation (a `public_site/__init__.py` docstring, the
README's repository-layout section, and the new `docs/architecture.md`)
rather than through directory relocation. Add exactly one new top-level
directory, `docs/`, for the architecture documentation FR-021–FR-023
require; do not create `apps/`, `packages/`, or `examples/` skeletons,
since none would have real content yet (research.md §3, FR-007).

## Complexity Tracking

*No entries — Constitution Check above shows no violations. This feature
reduces ambiguity (clearer naming, one new documentation file) without
adding any new abstraction, dependency, service, or architectural layer.*
