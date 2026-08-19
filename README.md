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

specs/001-albertos-rag-chatbot/                       # spec, plan, research, data model, contracts, tasks
specs/002-add-ollama-provider/                         # local Ollama backend + automatic provisioning
specs/003-ollama-gpu-acceleration/                     # NVIDIA GPU passthrough for the ollama service
specs/004-rag-answerability-and-ollama-performance/    # structured answerability, OLLAMA_THINK, eval tooling
tests/{unit,integration,contract,fakes,fixtures}/
```
