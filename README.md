# Albercik Chatbot

A security-first RAG customer-support chatbot for a single company,
**Albertos**. A Public User asks Polish-language questions on a public,
unauthenticated `/api/v1/chat` endpoint; an Administrator signs in and
manages the `.txt` knowledge base the chatbot answers from. Every answer
is grounded exclusively in that knowledge base — the chatbot declines
off-topic questions and says so plainly when it doesn't have enough
information, rather than guessing.

This is an MVP. See [Known limitations](#known-limitations) before
treating it as production-ready.

## Architecture

- **API**: FastAPI (Python), single backend service — no separate
  frontend/chat widget yet.
- **Database**: PostgreSQL + `pgvector`, single-tenant (no
  `organization_id`/tenant table — one Albertos knowledge base).
- **Embeddings**: local `sentence-transformers`
  (`intfloat/multilingual-e5-small`, 384-dim, CPU-only), pre-baked into
  the Docker image at build time — no embedding-provider API key, no
  per-request embedding cost.
- **LLM**: Claude via the Anthropic API, behind a `Protocol` so the
  provider is swappable without touching core RAG logic.
- **Admin auth**: JWT (HS256), bcrypt-hashed passwords, a single privilege
  tier (no roles). Administrator accounts are provisioned out-of-band via
  a CLI command — there is no self-registration endpoint.
- **Cost/abuse controls on `/chat`**: PostgreSQL-backed fixed-window rate
  limiting (no Redis), a configurable hourly LLM usage budget backed by
  `usage_records`, an `LLM_ENABLED` kill switch, a process-local bounded
  concurrency guard for paid LLM calls, bounded provider retries/timeouts,
  and server-controlled context/token limits the client can never
  override.
- **Prompt-injection defenses**: trusted system instructions, the
  visitor's question, and retrieved document content are always kept in
  clearly delimited, separate parts of the prompt; delimiter tokens are
  neutralized in untrusted text so a document or question can't forge a
  fake boundary. Defense in depth only — application-level controls
  (auth, rate limit, budget, kill switch) never depend on the LLM
  behaving correctly.

## Quickstart

See [`specs/001-albertos-rag-chatbot/quickstart.md`](specs/001-albertos-rag-chatbot/quickstart.md)
for a full walkthrough (setup, admin provisioning, upload, chat, deletion,
abuse-control, and prompt-injection scenarios). Short version:

```bash
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run python -m albercik_chatbot.cli create-admin --username admin
docker compose up -d app
curl localhost:8000/health
```

## Development

```bash
uv run pytest              # unit + integration + contract tests
uv run ruff check .        # lint
uv run ruff format --check .
uv run mypy src tests      # type check
```

No automated test ever calls the real Anthropic API or loads the real
`sentence-transformers` model — both are behind `Protocol`s and every
test injects deterministic fakes (`tests/fakes/`). Integration tests need
a real PostgreSQL + `pgvector` instance (`docker compose up -d db-test`).

## Known limitations

This is an MVP, not a production deployment. Explicitly not solved yet:

- **Concurrency guard is process-local.** `infra/concurrency.py`'s bounded
  paid-LLM-call guard works within one running `app` container/process
  only; it does not coordinate across multiple instances behind a load
  balancer. A multi-instance deployment needs this replaced with a
  cross-instance bound (e.g. a Postgres-backed counter, mirroring
  `infra/rate_limit.py`'s approach).
- **No production reverse-proxy configuration is included.**
  `docker-compose.yml` exposes the `app` service directly; TLS
  termination, a real reverse proxy, and its trusted-proxy wiring
  (`TRUSTED_PROXY_COUNT`) are deployment-environment concerns not covered
  here.
- **No production-grade distributed rate-limit/concurrency
  infrastructure.** Rate limiting is Postgres-backed and correct across
  multiple app processes; the concurrency guard, as above, is not — this
  is an intentional MVP tradeoff (Principle XIII: no Redis/Celery/K8s),
  not an oversight.
- **Hosting provider is undecided.** No cloud-specific deployment
  configuration exists; only Docker Compose.
- **Production secrets manager is undecided.** Secrets currently come
  from `.env`/environment variables; no AWS Secrets Manager/Vault/etc.
  integration exists.
- **Real Albertos RAG calibration is still required.** Retrieval
  defaults (`RETRIEVAL_TOP_K`, `RETRIEVAL_RELEVANCE_THRESHOLD`) were
  calibrated against a synthetic fixture set
  (`tests/fixtures/albertos_kb/`), not real Albertos content — re-tune
  once real knowledge-base documents are available.
- **The "related-but-unsupported" RAG-quality risk remains open and
  undocumented-as-solved by design.** The relevance threshold cannot
  reliably distinguish a genuinely answerable question from an
  Albertos-related question the knowledge base simply doesn't cover yet
  — both can score similarly. See `domain/retrieval.py`'s
  `select_sufficient_chunks` docstring. Deliberately not addressed by
  raising the threshold further, keyword heuristics, an LLM classifier, a
  reranker, or hybrid search — validate against real Albertos content
  first.
- **No frontend/chat widget yet.** `/api/v1/chat` is a JSON API only.

## Repository layout

```text
src/albercik_chatbot/
├── api/            # FastAPI routers, request/response schemas, error mapping
├── application/     # Use cases (ask_question, upload/list/delete document)
├── domain/          # Framework-free logic: chunking, scope, retrieval, prompting
├── persistence/      # SQLAlchemy models, session, repositories
├── providers/        # LLM/embedding Protocols + concrete implementations
├── infra/            # Cross-cutting: security, logging, audit, rate limit, budget, concurrency
├── cli.py            # `create-admin` out-of-band provisioning command
└── main.py           # FastAPI app factory

specs/001-albertos-rag-chatbot/   # spec, plan, research, data model, contracts, tasks
tests/{unit,integration,contract,fakes,fixtures}/
```
