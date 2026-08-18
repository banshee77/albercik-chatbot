# Implementation Plan: Albertos RAG Support Chatbot (MVP)

**Branch**: `001-albertos-rag-chatbot` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-albertos-rag-chatbot/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A single-tenant FastAPI backend that lets an authenticated Administrator
upload Polish-language `.txt` Albertos knowledge documents (chunked, embedded
locally via a self-hosted `sentence-transformers` model — no external
embedding API, no embedding-provider API key — stored in PostgreSQL +
`pgvector`) and lets an unauthenticated
public visitor ask Albertos-related questions, answered by Claude (via the
Anthropic API) grounded strictly in retrieved chunks — with every chat
request, admin or public, uniformly subject to Postgres-backed rate limiting,
size limits, bounded retries, usage accounting, and a configurable
budget/kill switch, so the public endpoint can never generate uncontrolled
LLM cost. LLM and embedding access sit behind small `Protocol` interfaces so
either provider can be replaced without touching core RAG logic. See
`research.md` for how each deferred technical decision was resolved.

## Technical Context

**Language/Version**: Python 3.14 (per `pyproject.toml` / `.python-version`)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Alembic, `pgvector` (Python
client), `anthropic` SDK (behind an `LLMProvider` Protocol),
`sentence-transformers` with a CPU-only `torch` backend — running the
`intfloat/multilingual-e5-small` model locally in-process (behind an
`EmbeddingProvider` Protocol; no external embedding API, no
embedding-provider API key), `bcrypt`, a JWT library (e.g., `pyjwt`),
`python-multipart` (file upload), Pydantic Settings.

**Storage**: PostgreSQL + `pgvector` extension (single database, no per-tenant
schemas — Principle II).

**Testing**: `pytest` (+ `pytest-asyncio`, `httpx` for API tests). Unit tests
run provider- and DB-free; integration tests run against a real Postgres +
`pgvector` instance via Docker Compose; contract tests use fake `LLMProvider`
/ `EmbeddingProvider` implementations (research.md §8).

**Target Platform**: Linux container (Docker / Docker Compose); no cloud
provider fixed yet (constitution Principle VII).

**Project Type**: Single backend web service — no frontend in this MVP
(production chat widget UI and admin UI are explicitly out of scope per
spec §30).

**Performance Goals**: No hard SLA for this MVP (spec has no stated latency
target); the system must stay responsive under its own configured rate/
concurrency limits rather than meet a specific req/s figure. Not a blocking
unknown — validating the RAG architecture, not production throughput, is the
MVP's stated goal.

**Constraints**: Single-tenant (no `organization_id`/RLS/tenant tables —
Principle II); Polish-language only (chat, scope classification, responses —
FR-030a); no Redis/Celery/Kubernetes/microservices (Principle XIII); every
automated test run must be provider-network-free (Principle XI); budget/rate
checks must fail closed (Principle X).

**Scale/Scope**: One customer (Albertos), one knowledge base, MVP validation
traffic (not a stated production concurrent-user target — see spec
Assumptions). Rate-limit/budget defaults are configuration values tuned
later, not fixed now (research.md §2–3).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Check | Status |
|---|---|---|---|
| I | Security by Default | Auth/authz never delegated to the LLM; secrets via env/`.env`, never committed; `.env.example` ships with placeholders only | PASS |
| II | Tenancy Posture (Single-Tenant MVP) | Data model (`data-model.md`) has no `organization_id`, no tenant table, no tenant-aware retrieval, no RLS; single Albertos knowledge base | PASS |
| III | Secure RAG | Retrieved chunks passed to Claude as data inside a clearly delimited context block, never concatenated into system instructions; system prompt is the only source of instructions | PASS |
| IV | Secure Document Ingestion | Upload validated (extension, UTF-8, size) before any processing; filename never used as a storage path; system-generated document IDs | PASS |
| V | LLM Provider Neutrality | `LLMProvider` Protocol in `providers/llm/`; `application/` and `domain/` never import `anthropic` directly | PASS |
| VI | Embedding Provider Neutrality | `EmbeddingProvider` Protocol in `providers/embedding/`; retrieval code depends only on the Protocol — `sentence_transformers` is imported only inside `LocalSentenceTransformerEmbeddingProvider`, never in `domain/`/`application/` | PASS |
| VII | Provider and Cloud Neutrality | No cloud-specific SDK in core logic; Docker Compose only, no AWS/Azure/GCP-specific service used | PASS |
| VIII | API Security | Auth resolved via a FastAPI dependency before any route body executes; no stack traces/secrets in error responses (`api/errors.py`) | PASS |
| IX | Privacy and Logging | `usage_records` excludes prompt/document content by design (`data-model.md`); logging config excludes passwords/tokens/API keys | PASS |
| X | Cost Safety Is a Security Requirement | Rate limiting, size limits, bounded retries, budget check, and kill switch all sit in front of every provider call, for every role uniformly (research.md §2–3, §7) | PASS |
| XI | Testing Discipline | Role-based access-control tests, mockable providers, no paid calls in CI, prioritized test list carried into `tasks.md` | PASS (verify at task generation) |
| XII | Engineering Quality Principles | Layered structure below keeps modules cohesive; `Protocol`s used instead of ABC hierarchies; type hints throughout | PASS |
| XIII | Simplicity for MVP | No Redis/Celery/K8s/LangGraph/agents; rate limiting and budgets reuse Postgres, the one infra dependency already mandated | PASS |
| XIV | Approved MVP Technology Stack | Python/FastAPI/PostgreSQL/`pgvector`/SQLAlchemy/Alembic/Claude/Anthropic API/Docker/`uv`, plus `sentence-transformers` for local embeddings — the constitution's own Principle VI text explicitly allows a "self-hosted/open-source embedding model" behind the Protocol, so this isn't a new stack element outside what's already sanctioned | PASS |

No violations requiring justification — **Complexity Tracking is empty.**

**Post-Design Re-check** (after Phase 1 `data-model.md` / `contracts/` /
`quickstart.md` were written): no tenant column or provider-SDK coupling in
core logic was introduced during design. `RateLimitWindow` and the budget
query both reuse PostgreSQL — the one infrastructure dependency already
mandated (Principle XIII) — rather than adding Redis or another service.
The embedding provider was switched from a hosted API (Voyage AI) to a
locally-run `sentence-transformers` model (`intfloat/multilingual-e5-small`,
384-dim — research.md §4/§4a); this is a same-Protocol implementation swap,
not a new service or infrastructure dependency, and it removes an external
API key rather than adding one. The accepted tradeoff — CPU/RAM consumption
and a larger container image in exchange for zero per-request embedding
cost and no external embedding-provider dependency — is recorded in
research.md §4a. All 14 principles remain **PASS**; the gate is still clean.

## Project Structure

### Documentation (this feature)

```text
specs/001-albertos-rag-chatbot/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── openapi.yaml      # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Single project (Option 1) — a backend web service with no frontend, laid out
along the constitution's Separation of Concerns layering
(API → Application → RAG/domain → {Persistence, Provider interfaces}):

```text
src/albercik_chatbot/
├── main.py                     # FastAPI app factory / entrypoint — constructs the process-wide
│                                #   SentenceTransformer instance once at startup (research.md §4a)
├── config.py                   # Pydantic Settings: budgets, rate limits, chunking, LLM_ENABLED,
│                                #   EMBEDDING_MODEL_NAME (default intfloat/multilingual-e5-small), etc.
├── cli.py                      # `create-admin` seed command (out-of-band provisioning, FR-004a)
├── api/                        # API / HTTP layer (constitution: "Separation of Concerns")
│   ├── deps.py                 # auth dependency, rate-limit guard, current-admin resolver
│   ├── errors.py                # exception → HTTP response mapping (no stack traces/secrets)
│   ├── schemas.py                # Pydantic request/response models (mirrors contracts/openapi.yaml)
│   └── routers/
│       ├── chat.py               # POST /api/v1/chat
│       ├── auth.py               # POST /api/v1/auth/login
│       ├── documents.py          # POST/GET/DELETE /api/v1/documents
│       └── health.py             # GET /health
├── application/                 # Application / service layer: use-case orchestration
│   ├── ask_question.py
│   ├── upload_document.py
│   ├── list_documents.py
│   └── delete_document.py
├── domain/                      # RAG / domain logic — independently testable, no I/O
│   ├── chunking.py               # deterministic paragraph-aware chunker (research.md §5)
│   ├── scope.py                  # Albertos-scope classifier (FR-027, FR-030)
│   ├── retrieval.py               # relevance evaluation / insufficient-context decision
│   └── prompting.py               # trusted-instructions vs. untrusted-context assembly (Principle III)
├── providers/                    # Provider boundaries (constitution Principles V, VI)
│   ├── llm/
│   │   ├── protocol.py            # LLMProvider Protocol
│   │   └── anthropic_provider.py  # Claude/Anthropic implementation
│   └── embedding/
│       ├── protocol.py            # EmbeddingProvider Protocol
│       └── local_sentence_transformer_provider.py  # LocalSentenceTransformerEmbeddingProvider —
│                                     #   sentence-transformers, intfloat/multilingual-e5-small,
│                                     #   loaded once per process (research.md §4a); the only file
│                                     #   in the codebase importing sentence_transformers
├── persistence/                  # Persistence layer
│   ├── database.py                # SQLAlchemy engine/session
│   ├── models.py                  # ORM models (see data-model.md)
│   └── repositories.py            # per-aggregate repository functions
└── infra/                        # Cross-cutting infrastructure
    ├── security.py                 # password hashing, JWT issue/verify
    ├── rate_limit.py                # Postgres-backed rate limiter (research.md §2)
    ├── budget.py                    # usage-budget check + kill switch (research.md §3)
    └── logging.py                   # structured, privacy-conscious logging (Principle IX)

alembic/
├── env.py
└── versions/

tests/
├── unit/          # domain/ logic — no DB, no network
├── integration/   # persistence/ + real Postgres+pgvector via Docker Compose
└── contract/      # api/ routes via httpx.AsyncClient, fake LLM/EmbeddingProvider

docker-compose.yml   # app + db (+ db-test)
Dockerfile
alembic.ini
.env.example
```

**Structure Decision**: Single project, Option 1. A frontend tree is
deliberately omitted — the spec explicitly puts the production chat widget
and admin UI out of scope (spec §30), so this plan covers the API service
only. The `api/ → application/ → domain/ → {persistence/, providers/}`
package layout is a direct, literal mapping of the constitution's Separation
of Concerns diagram, chosen specifically so a future multi-tenancy migration
(Principle II) would touch `persistence/` and a handful of `application/`
call sites rather than requiring a RAG-pipeline rewrite.

## Complexity Tracking

*No entries — Constitution Check above found no violations to justify.*
