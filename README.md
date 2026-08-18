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
- **LLM**: two interchangeable backends behind the same `Protocol`
  (`LLMProvider`), selected exclusively by the server-side `LLM_PROVIDER`
  setting — never by the client, and never by request content:
  - `ollama` (**default**) — a locally-hosted open-source model via
    [Ollama](https://ollama.com), model name configurable via
    `OLLAMA_MODEL` (default `qwen3:4b`). No API key, no per-question cost.
  - `anthropic` — Claude via the Anthropic API, model name configurable
    via `ANTHROPIC_MODEL`. Requires a real `ANTHROPIC_API_KEY`.

  Switching backends is a configuration change only — no code change, and
  every existing abuse/cost control (rate limiting, the kill switch,
  concurrency limits, request/context/output size limits, prompt-injection
  defenses, scope control) applies identically regardless of which backend
  is active. The one control that is backend-specific by design is the
  monetary budget (`BUDGET_MAX_LLM_REQUESTS_PER_HOUR`): it gates only
  Anthropic usage — local Ollama usage is recorded (for observability) but
  never consumes or is capped by that budget. See
  `specs/002-add-ollama-provider/` for the full design.
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

### Local Ollama backend

- Runs as its own `ollama` service on the internal Docker Compose network
  only — its API (port `11434`) is never published to the host or the
  public internet; the application is the only thing that can reach it.
- The configured model (`OLLAMA_MODEL`) is provisioned **automatically**
  by a one-shot `ollama-init` service on `docker compose up -d` — no
  manual `ollama pull` command is needed for a normal local workflow. The
  `app` service will not start until provisioning has completed
  successfully.
- Downloaded model data is stored in the persistent `ollama-data` Docker
  volume: it survives `docker compose down` / `docker compose up -d` and
  is only lost if that volume is explicitly removed (`docker compose down
  -v`), at which point the model is downloaded again automatically on the
  next startup.
- GPU acceleration for the `ollama` service is supported by Ollama itself,
  but **no GPU passthrough is configured in `docker-compose.yml` by
  default** — the container runs CPU-only unless an operator adds the
  relevant `deploy.resources.reservations.devices` block to the `ollama`
  service themselves (never to `ollama-init` or `app`, which do not run
  inference).

## Quickstart

See [`specs/001-albertos-rag-chatbot/quickstart.md`](specs/001-albertos-rag-chatbot/quickstart.md)
for the full base walkthrough (setup, admin provisioning, upload, chat,
deletion, abuse-control, and prompt-injection scenarios), and
[`specs/002-add-ollama-provider/quickstart.md`](specs/002-add-ollama-provider/quickstart.md)
for the dual-provider/automatic-provisioning scenarios (switching
backends, model persistence, provisioning-failure behavior, cross-backend
evaluation). Short version — brings up the full stack, including
automatic local-model provisioning, with a single command:

```bash
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run python -m albercik_chatbot.cli create-admin --username admin
docker compose up -d          # brings up ollama + ollama-init (auto model
                               #   provisioning) + app in dependency order
curl localhost:8000/health
```

The default `LLM_PROVIDER=ollama` needs no API key. To use Anthropic
instead, set `LLM_PROVIDER=anthropic` and a real `ANTHROPIC_API_KEY` in
`.env`, then `docker compose up -d app` to restart with it — no code
change required either way.

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
- **No GPU passthrough configured for the local Ollama backend by
  default.** `docker-compose.yml`'s `ollama` service runs CPU-only unless
  an operator adds GPU device reservation themselves — see "Local Ollama
  backend" above.

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
specs/002-add-ollama-provider/    # local Ollama backend + automatic provisioning
tests/{unit,integration,contract,fakes,fixtures}/
```
