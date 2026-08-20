# Shiruno

**Knowledge that answers.**

Turn your organization's knowledge into an assistant your customers can
simply ask.

**Shiruno** is a reusable, security-first RAG (Retrieval-Augmented
Generation) chatbot platform: a public, unauthenticated `/api/v1/chat`
endpoint answers a visitor's questions, grounded exclusively in a
customer's own knowledge base, while an Administrator signs in separately
to manage that knowledge base. The chatbot declines off-topic questions
and says so plainly when it doesn't have enough information, rather than
guessing.

**Albertos**, a karate club, is Shiruno's first customer — the public
website, chat widget, and knowledge base you'll find running this
codebase today are the **Albertos reference implementation**, built on
top of the reusable Shiruno platform (`src/shiruno/` minus
`public_site/`). See [`docs/architecture.md`](docs/architecture.md) for
the full product/customer boundary, current architecture diagram, and
documented (not-yet-built) future direction — a standalone Shiruno
Widget and a Shiruno Platform / Customer Admin.

This is an MVP, currently serving one customer. See
[Known limitations](#known-limitations) before treating it as
production-ready.

## Architecture

- **API**: FastAPI (Python), single backend service. A public chat widget
  (feature 006/007) is embedded in the Albertos website; there is no
  standalone, site-independent widget distribution yet (see "Future:
  Shiruno Widget" in [`docs/architecture.md`](docs/architecture.md)).
- **Database**: PostgreSQL + `pgvector`. Multi-tenant as of Feature 009
  (Admin Platform Foundation & Tenant Boundary): a first-class `Tenant`
  table, with `Administrator` and `KnowledgeDocument` each owned by
  exactly one tenant. Albertos is tenant #1 and, today, the only tenant
  with real production data — see
  [`docs/architecture.md`](docs/architecture.md#current-admin-platform-foundation)
  for the full current-vs-future admin platform picture.
- **Embeddings**: local `sentence-transformers`
  (`intfloat/multilingual-e5-small`, 384-dim, CPU-only), pre-baked into
  the Docker image at build time — no embedding-provider API key, no
  per-request embedding cost.
- **LLM**: two interchangeable backends behind the same `Protocol`
  (`LLMProvider`), selected exclusively by the server-side `LLM_PROVIDER`
  setting — never by the client, and never by request content:
  - `ollama` (**default**) — a locally-hosted open-source model via
    [Ollama](https://ollama.com), model name configurable via
    `OLLAMA_MODEL` (default `qwen3:8b`, changed from `qwen3:4b`
    2026-08-19 — see `eval/README.md`'s "Model selection: qwen3:8b
    adopted as default"; `qwen3:4b` remains a valid lower-resource manual
    override). No API key, no per-question cost.
  - `anthropic` — Claude via the Anthropic API, model name configurable
    via `ANTHROPIC_MODEL`. Requires a real `ANTHROPIC_API_KEY`.

  Every grounded answer is produced together with an explicit, structured
  `supported: bool` decision from that same LLM call (feature
  004-rag-answerability-and-ollama-performance) — the application decides
  `grounded` vs. `insufficient_information` from that field, never from
  merely "the model returned some text". A malformed or unparseable
  structured response is treated as a provider failure (`unavailable`),
  never silently reported as `insufficient_information`. Both backends
  share one JSON-schema contract; see
  `specs/004-rag-answerability-and-ollama-performance/`.

  `OLLAMA_THINK` (default `false`, Ollama backend only, ignored on
  Anthropic) is a server-only setting controlling Qwen3's extended
  reasoning ("thinking") step before it answers — never client-
  controllable, and not part of the shared `LLMProvider` interface.
  **Measured, not assumed** (`qwen3:4b`, real GPU-accelerated Ollama,
  2026-08-18 — see `eval/README.md`'s `OLLAMA_THINK` A/B comparison
  section): `think=true` was ~3.6x slower on average (8948ms vs 2467ms)
  and introduced 6/30 new `unavailable` outcomes (the model exhausted its
  answer-token budget on reasoning before producing valid structured
  output) that `think=false` never hit — `false` is the default for both
  reasons, not just latency.

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
  tier (no roles). Every administrator belongs to exactly one tenant
  (feature 009); tenant context is always derived server-side from the
  authenticated administrator, never from client input. Tenants and
  administrators are both provisioned out-of-band via CLI commands
  (`create-tenant`, `create-admin --tenant`) — there is no self-registration
  endpoint for either.
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
- **NVIDIA GPU acceleration is optional for deployment, but is enabled in
  this repo's `docker-compose.yml` by default** for the `ollama` service
  only (feature 003-ollama-gpu-acceleration) — a
  `deploy.resources.reservations.devices` block requesting one `nvidia`
  GPU. `ollama-init` and `app` never receive GPU access; they don't run
  inference. **Host requirements** (WSL2 or native Linux): a supported
  NVIDIA GPU, an installed NVIDIA driver, and the NVIDIA Container Toolkit
  configured for Docker. On WSL2 specifically, the NVIDIA driver is
  installed on the *Windows* host only — do not install a Linux NVIDIA
  driver inside the WSL2 distro; install the NVIDIA Container Toolkit
  inside the distro as usual. **Before assuming GPU acceleration is
  available, verify it — don't take it on faith:**
  1. `nvidia-smi` on the host must succeed and list your GPU.
  2. `docker compose up -d ollama` must report the container healthy
     (`docker compose ps ollama`) — if the host doesn't meet the
     prerequisites above, this step fails instead, which is expected
     (see CPU-only fallback below).
  3. `docker exec <ollama-container> nvidia-smi` must succeed *inside* the
     container — this is the actual proof the container received the
     device, not just that the host has one.
  4. While a real chat request is in flight, `nvidia-smi` on the host
     should show GPU utilization/VRAM usage attributable to the `ollama`
     process. Only report GPU acceleration as working once you've seen
     this — don't claim it from configuration alone.

  Originally validated against an NVIDIA RTX 3070 (8 GB VRAM) with
  `qwen3:4b`, the default at the time (feature 003-ollama-gpu-
  acceleration). `qwen3:8b` (the current default, adopted 2026-08-19) was
  subsequently confirmed on the same host with no OOM/timeout/provider
  failures, using ~6.0 GB VRAM — see `eval/README.md`'s "Model selection:
  qwen3:8b adopted as default" section.
  **CPU-only fallback**: on a host without those prerequisites,
  `docker compose up` fails to start `ollama` until you comment out or
  remove the `deploy:` block under the `ollama` service in
  `docker-compose.yml` — this is a manual edit; nothing auto-detects GPU
  presence. `docker compose config` itself always succeeds regardless of
  GPU presence, since it only validates syntax, not hardware.
  **Stale cached image**: if your locally cached `ollama/ollama:latest`
  image predates support for the configured model (symptom: `ollama-init`
  logs an error like "pull model manifest: ... requires a newer version of
  Ollama"), refresh it and recreate the container —
  `docker pull ollama/ollama:latest` followed by
  `docker compose up -d ollama --force-recreate` — then retry. This is an
  operational/documentation note only; the project does not add any
  automatic image-pulling logic. See
  `specs/003-ollama-gpu-acceleration/quickstart.md` for step-by-step
  verification.

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
uv run alembic upgrade head    # also bootstraps the Albertos tenant (feature 009)
uv run python -m shiruno.cli create-admin --tenant albertos --username admin
docker compose up -d          # brings up ollama + ollama-init (auto model
                               #   provisioning) + app in dependency order
curl localhost:8000/health
```

The default `LLM_PROVIDER=ollama` needs no API key. To use Anthropic
instead, set `LLM_PROVIDER=anthropic` and a real `ANTHROPIC_API_KEY` in
`.env`, then `docker compose up -d app` to restart with it — no code
change required either way.

### Observability (RAG tracing)

Optional and disabled by default — a plain `docker compose up -d` above is
completely unaffected by any of this (feature 012-rag-observability). See
[`specs/012-rag-observability/quickstart.md`](specs/012-rag-observability/quickstart.md)
for the full walkthrough; short version:

```bash
# 1. Start the optional local trace-visualization backend (Phoenix):
docker compose --profile observability up -d phoenix
# UI: http://localhost:6006

# 2. Enable tracing in .env, then restart app:
#   OBSERVABILITY_ENABLED=true
#   OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006/v1/traces
docker compose up -d app

# 3. Send a request, then find its trace in Phoenix by request_id:
curl -s -X POST localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Jakie są godziny treningów?"}' | jq -r .request_id
```

Open the Phoenix UI, browse the `shiruno` project's traces, and filter by
the `shiruno.request_id` attribute using the id printed above — its root
`shiruno.chat` span shows every pipeline stage that actually ran (gates,
classification, retrieval, generation, recording), each with timing; the
`shiruno.retrieval` span shows candidate/selected chunk counts, similarity
scores, and safe source labels; the `shiruno.llm_generation` span shows
provider/model/token counts. Full visitor question/answer text and full
retrieved document/prompt content are never exported by default — enable
`OBSERVABILITY_CAPTURE_QUESTION_ANSWER_CONTENT`/
`OBSERVABILITY_CAPTURE_DOCUMENT_PROMPT_CONTENT` (independently) in `.env`
only for controlled local debugging. `docker compose --profile
observability down` removes Phoenix without touching the normal stack.

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

## Admin frontend

`apps/admin/` (feature 013-admin-platform-shell) is the Shiruno Admin
Platform — a standalone React/TypeScript/Vite single-page app, independent
of the backend above and run as its own process in local development.
`/app/knowledge` (feature 014-knowledge-base-ui) is a functional
knowledge-management screen — health summary, document list, upload,
detail, re-index, replace, and delete — consuming the existing Feature 010
Knowledge API with zero backend changes.

```bash
# 1. Backend: allow the frontend's origin to call it cross-origin.
#    In the root .env:
#      CORS_ALLOWED_ORIGINS=http://localhost:5173
docker compose up -d

# 2. Frontend
cd apps/admin
cp .env.example .env   # first time only; VITE_SHIRUNO_API_URL=http://localhost:8000 by default
npm install             # first time only
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`). The
bearer token issued by `POST /api/v1/auth/login` is kept in memory only
(never `localStorage`/`sessionStorage`) — a full page reload requires
logging in again by design (research.md R1).

```bash
cd apps/admin
npm test      # Vitest + Testing Library, no real backend/network
npm run lint  # ESLint
npx tsc -b    # type check (also run by `npm run build`)
npm run build # production static build (dist/)
```

See [`specs/013-admin-platform-shell/quickstart.md`](specs/013-admin-platform-shell/quickstart.md)
for a full manual walkthrough (login, organization identity, placeholder
navigation, session expiration, logout).

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
- **No standalone widget distribution yet.** The chat widget (feature
  006/007) is embedded in the Albertos website only; `/api/v1/chat` is a
  JSON API any site could call, but there's no packaged, site-independent
  "Shiruno Widget" script yet — see `docs/architecture.md`.
- **The ≥85% insufficient-information rejection target (spec SC-002) is an
  MVP acceptance gate, not a statistical production guarantee.** It's
  phrased as "at least 6 of the 7 `insufficient_information`-expected
  questions" on the current 30-question frozen benchmark
  (`eval/questions.jsonl`) — enough to catch a regression back toward the
  pre-fix 0/7 failure mode, but 7 items is too small a sample for a tight
  confidence interval on real-world accuracy. See
  `specs/004-rag-answerability-and-ollama-performance/spec.md`.
- **Grounded accuracy (spec SC-001) — resolved 2026-08-19 via an amended
  acceptance criterion; one known accepted limitation remains (question
  #6).** History: measured deterministically at 17/20 (85%) against the
  original 20/20 target on `qwen3:4b`. The structured-
  answerability fix (feature 004) correctly eliminated the pre-fix 0/7
  insufficient-information rejection failure. A diagnosed, targeted fix
  (`domain/prompting.py::SYSTEM_PROMPT` rule 7 — clarifying that
  `supported=true` is fine when explicit context answers a question via
  paraphrase, fact-combination, or multiple chunks) was applied on
  2026-08-18 and re-measured, but the model's decoding was non-
  deterministic at the time (Ollama's default nonzero sampling
  temperature) — the same prompt+context could return a different
  `supported` decision across separate calls, making that single-run
  delta unreliable. **Fixed 2026-08-19**: `OLLAMA_TEMPERATURE=0` /
  `OLLAMA_SEED=42` (server-only Ollama provider config, same
  never-client-overridable pattern as `OLLAMA_THINK`) were added and the
  frozen 30-question benchmark was run 3 times back to back — **100%
  (30/30) per-question outcome agreement across all 3 runs, zero unstable
  questions**, confirming the deterministic baseline: grounded accuracy
  85% (17/20), insufficient-information rejection 100% (7/7),
  false-grounded 0/7, out-of-scope 100% (3/3), identical every run. No
  safety regression at any point (rule 6 — no inference from silence —
  held throughout). Retrieval, chunking, embeddings, and the benchmark's
  expected outcomes were never touched. See "Reproducibility experiment"
  in `eval/README.md` for the full diagnosis, all eval reports, and the
  3 remaining failing questions (#3, #6, #22) — further prompt
  calibration is scientifically meaningful now (no repeated-run
  methodology needed to trust a single re-run's delta), which was put to
  the test the same day: **a targeted rule-8 clarification aimed at
  exactly these 3 questions was tried and measured a severe regression —
  35% (7/20) grounded, down from the 85% baseline, 13 failures instead of
  3.** No safety property regressed (false-grounded stayed 0/7). **Rule 8
  was reverted the same day** (`domain/prompting.py::SYSTEM_PROMPT`
  restored to rules 1–7 exactly, its 3 regression tests removed), and a
  confirming re-run measured the restored deterministic baseline exactly:
  85% (17/20) grounded, 100% (7/7) insufficient-information rejection,
  0/7 false-grounded, 100% (3/3) out-of-scope, same failing questions
  (#3, #6, #22) — see `eval/README.md`'s "Deterministic baseline
  restored" section and `eval/results/qwen3-4b-think-false-post-revert.json`.

  **Model switched 2026-08-19**: with the prompt fixed at this rules-1–7
  baseline (no further prompt/RAG changes), a controlled evaluation of
  `qwen3:8b` (same deterministic config: `OLLAMA_THINK=false`,
  `OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`) measured grounded accuracy
  **19/20 (95%)**, up from 4B's 17/20 — insufficient-information
  rejection stayed 100% (7/7), false-grounded stayed 0/7, out-of-scope
  stayed 100% (3/3), no OOM/timeout/provider failures, ~6.0 GB VRAM on
  the RTX 3070 (8 GB budget), latency avg 2.57s/p50 2.03s/p95 4.18s
  (slower than 4B's ~1.9s avg but still well within interactive bounds).
  **`qwen3:8b` is now the default** (`config.py`, `.env.example`,
  `docker-compose.yml`); `qwen3:4b` remains available as a lower-resource
  manual override (`OLLAMA_MODEL=qwen3:4b`). See `eval/README.md`'s
  "Model selection: qwen3:8b adopted as default" section and
  `eval/results/qwen3-8b-think-false.json` for the full comparison.
  Question #6 ("Czy na treningach ćwiczy się w butach?") deterministically
  fails on both models and was deliberately not investigated or fixed —
  a prior targeted prompt experiment aimed at this same class of case
  (rule 8) caused a severe measured regression elsewhere (research.md
  §16), so further global prompt tuning to close one remaining edge case
  was judged not worth the demonstrated risk.

  **SC-001 amended 2026-08-19**: rather than continue chasing 20/20,
  SC-001 was deliberately changed to **grounded accuracy ≥19/20 (≥95%)**
  — a documented product decision (`spec.md`'s "SC-001
  acceptance-criterion amendment", `research.md` §18), not a claim that
  the original 20/20 target was met. Against the amended criterion, the
  measured 19/20 **meets SC-001**, and with SC-002 (insufficient-info
  ≥6/7, measured 7/7), SC-003 (false-grounded ≤1/7, measured 0/7), and
  SC-004 (documented `OLLAMA_THINK` A/B) all already met, **feature 004
  is complete**. Question #6 is retained in `eval/questions.jsonl` with
  its original expected outcome and documented as a known, accepted MVP
  limitation — see `eval/README.md` for the full history.
- **GPU passthrough requires host prerequisites the project doesn't
  install for you.** `docker-compose.yml`'s `ollama` service requests an
  NVIDIA GPU by default (feature 003-ollama-gpu-acceleration); on a host
  without a working NVIDIA driver + Container Toolkit, `ollama` (and, by
  the existing `depends_on` chain, `ollama-init`/`app` too) will fail to
  start until you manually remove that service's `deploy:` block — see
  "Local Ollama backend" above.

## Repository layout

**Current structure** — one Python package, `shiruno`, containing both
the reusable platform and the one customer reference implementation built
on it. See [`docs/architecture.md`](docs/architecture.md) for the
product/customer boundary explanation and the aspirational target
monorepo layout (`apps/`, `packages/`, `examples/`) this may grow toward.

```text
apps/admin/                 # Shiruno Admin Platform frontend (React/TypeScript/Vite, feature 013) — independent of src/shiruno/

src/shiruno/                # Shiruno Platform (reusable) + Albertos reference implementation
├── api/            # FastAPI routers, request/response schemas, error mapping   — platform
├── application/     # Use cases (ask_question, upload/list/delete document)      — platform
├── domain/          # Framework-free logic: chunking, scope, retrieval, prompting — platform
├── persistence/      # SQLAlchemy models, session, repositories                   — platform
├── providers/        # LLM/embedding Protocols + concrete implementations         — platform
├── infra/            # Cross-cutting: security, logging, audit, rate limit, budget, concurrency — platform
├── public_site/       # Albertos public website, templates, static assets, chat widget front-end
│                       #   — Albertos reference implementation, NOT part of the reusable platform
├── cli.py            # `create-tenant`/`create-admin` out-of-band provisioning     — platform
└── main.py           # FastAPI app factory (composition root)                     — platform

docs/architecture.md    # current + target architecture, future Widget/Admin boundaries

specs/001-albertos-rag-chatbot/                       # spec, plan, research, data model, contracts, tasks
specs/002-add-ollama-provider/                         # local Ollama backend + automatic provisioning
specs/003-ollama-gpu-acceleration/                     # NVIDIA GPU passthrough for the ollama service
specs/004-rag-answerability-and-ollama-performance/    # structured answerability, OLLAMA_THINK, eval tooling
specs/005-public-club-website/                         # Albertos public website (public_site/)
specs/006-public-chat-widget/                          # public chat widget
specs/007-conversational-chat-ux/                      # small talk, assistant identity, avatar
specs/008-shiruno-repository-architecture/             # this rebrand/architecture refactor
specs/013-admin-platform-shell/                        # apps/admin/ — authenticated shell, placeholder nav
specs/014-knowledge-base-ui/                           # /app/knowledge — functional knowledge management
tests/{unit,integration,contract,fakes,fixtures}/
```
