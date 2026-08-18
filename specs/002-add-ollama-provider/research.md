# Research: Local Ollama LLM Provider

## 1. HTTP client for the Ollama provider

- **Decision**: Call Ollama's local REST API directly with `httpx` (already
  a project dependency, already used throughout the test suite) — no new
  `ollama` Python SDK dependency.
- **Rationale**: `AnthropicLLMProvider` wraps the official `anthropic` SDK
  because that SDK owns retry/timeout/auth semantics we'd otherwise have to
  reimplement. Ollama's local API has none of that complexity — no auth, a
  small JSON request/response shape — so a thin `httpx` client is the
  smallest thing that makes the provider replaceable and testable (Principle
  V/XIII), and keeps the dependency surface unchanged.
- **Alternatives considered**: The official `ollama` Python package — adds a
  dependency whose own retry/timeout handling we'd have to bypass anyway
  (Design Constraint 1: bounded retries live in exactly one layer, owned by
  this provider, not a wrapped SDK's internal loop); rejected as
  complexity without a corresponding win, mirroring how `AnthropicLLMProvider`
  itself never lets the `anthropic` SDK retry — this provider follows the same
  discipline one level earlier, before a wrapping SDK is even introduced.

## 2. Ollama wire contract

- **Decision**: `POST {OLLAMA_BASE_URL}/api/chat`, non-streaming
  (`"stream": false"`), with:
  ```json
  {
    "model": "<OLLAMA_MODEL>",
    "messages": [
      {"role": "system", "content": "<system_prompt>"},
      {"role": "user", "content": "<user_message>"}
    ],
    "stream": false,
    "options": {"num_predict": <max_tokens>}
  }
  ```
  Response fields consumed: `message.content` (answer text), `model`
  (echoed model name), `eval_count` (output tokens), `prompt_eval_count`
  (input tokens) — both optional/nullable in `UsageRecord`, matching spec
  FR-012 ("capture... when the backend itself reports them, without
  requiring them to be present when it doesn't"). `done_reason` /
  non-200 status / a response missing `message.content` is treated as a
  malformed response (spec FR-013).
- **Rationale**: `/api/chat` (vs. the older `/api/generate`) accepts
  system + user messages directly, mirroring the Anthropic Messages API
  shape this codebase already assembles in `domain/prompting.py` — no
  prompt-format translation needed. `options.num_predict` is the
  server-controlled output-token cap (never client-controlled, Principle
  X), populated from the same place `max_answer_tokens` already comes from
  today.
- **Alternatives considered**: `/api/generate` with a single concatenated
  prompt string — would require flattening system+user content ourselves,
  re-introducing exactly the "don't blend trusted instructions with
  untrusted content" risk `domain/prompting.py` was hardened against in
  Phase 6; rejected.

## 3. Retry and timeout policy

- **Decision**: `OllamaLLMProvider` owns its own bounded retry loop,
  structurally identical to `AnthropicLLMProvider`'s (same
  `PROVIDER_MAX_RETRIES` setting, reused rather than duplicated; connection
  errors and timeouts are retried, a non-2xx "client error"-shaped response
  is not). Timeout is a **separate** setting, `OLLAMA_TIMEOUT_SECONDS`,
  applied per attempt.
- **Rationale**: Reusing `PROVIDER_MAX_RETRIES` avoids a redundant config
  knob for a concept ("how many times do we retry a transient provider
  failure") that doesn't need a per-backend value — the feature description
  itself only introduced a new *timeout* setting for Ollama, not a new
  retry-count setting, implying retries share the existing policy. Timeout
  stays separate because local CPU-hosted inference of even a small model is
  expected to be meaningfully slower than a hosted API — reusing Anthropic's
  20s default would cause spurious timeouts under normal local operation.
- **Alternatives considered**: A dedicated `OLLAMA_MAX_RETRIES` — rejected
  as an unrequested extra config surface (Principle XIII) until a concrete
  need for independently-tunable retry counts per backend actually appears.

## 4. Distinguishing paid vs. local usage for budget enforcement

- **Decision**: Add a new, required `provider_name` column to
  `usage_records` (values: `anthropic` | `ollama` | `local_sentence_
  transformer`, the third covering the pre-existing local-embedding call
  so every row — LLM or embedding — has an unambiguous backend), populated
  on every insert alongside the existing `provider_kind` (`llm`/`embedding`)
  and `provider_model` (the model name string). `infra/budget.py`'s query
  becomes `WHERE provider_kind = 'llm' AND provider_name = 'anthropic'`.
  Existing rows are backfilled deterministically from `provider_kind` alone
  (never from `provider_model`) before the column is made `NOT NULL` — see
  data-model.md's Migration section for the exact ordered steps.
- **Rationale**: Principle X (Cost Safety, NON-NEGOTIABLE) requires that
  local-model usage can never count toward the paid budget. A dedicated
  column makes that guarantee structural — the budget query cannot
  accidentally include an Ollama row no matter what model name string it
  carries. This is strictly additive: every existing `ProviderKind.llm` /
  `ProviderKind.embedding` call site in `ask_question.py` and
  `upload_document.py` stays valid unchanged; only the row now also carries
  which backend served it.
- **Alternatives considered**:
  - Infer backend from `provider_model` (e.g., "does the model name look
    like a Claude model") — rejected: fragile, string-matching-based, and
    directly at odds with Principle X's fail-closed spirit; a renamed or
    newly-released Claude model could silently stop being recognized.
  - Split `ProviderKind` into per-backend values (`llm_anthropic`,
    `llm_ollama`, `embedding`) instead of adding a column — rejected:
    conflates two orthogonal dimensions (*what kind* of usage vs. *which
    backend*) into one enum, forces every existing `ProviderKind.llm`
    reference to be revisited, and makes "total LLM usage regardless of
    backend" queries (useful for operational visibility) awkward.

## 5. Provider selection / composition

- **Decision**: `main.py::create_app()` reads `settings.LLM_PROVIDER` once,
  at the same point it already constructs `AnthropicLLMProvider` today, and
  builds whichever concrete `LLMProvider` implementation is configured — an
  `if/else` at the composition boundary, not a registry or plugin
  mechanism. Test apps continue to inject a fake `LLMProvider` directly, as
  today, bypassing this branch entirely (Design Constraint 2, unchanged).
- **Rationale**: This mirrors exactly how the embedding provider is already
  constructed once at app-factory time; introducing a provider registry/
  factory class for two options would be unjustified complexity (Principle
  XIII).
- **Alternatives considered**: A provider-factory abstraction/registry
  pattern — rejected as premature generality for exactly two
  implementations chosen by one config value.

## 6. Docker Compose: Ollama as a default-but-removable service

- **Decision**: Add an `ollama` service to `docker-compose.yml` using the
  official `ollama/ollama` image, **no `ports:` mapping at all** (reachable
  only via the internal Compose network at `http://ollama:11434`, matching
  `OLLAMA_BASE_URL`'s documented default), started as part of the normal
  `docker compose up -d` set (**not** gated behind a Compose profile).
  Model weights are made available automatically by a separate one-shot
  step (§6a below) rather than a documented manual command.
  `quickstart.md` additionally documents pointing `OLLAMA_BASE_URL` at a
  host-run Ollama instance instead (`http://host.docker.internal:11434` on
  Docker Desktop/WSL2), for anyone who already runs Ollama natively.
- **Rationale**: This is a direct consequence of the Clarifications
  session's answer that `ollama` is now the **default** active backend —
  the original feature description asked for Ollama as an "optional"
  Compose service, written before that default was decided. If the
  `ollama` service were profile-gated (started only on request) while
  `LLM_PROVIDER` defaults to `ollama`, a plain `docker compose up -d` would
  boot a chatbot whose default backend is never running — every grounded
  question would silently resolve to `unavailable`. Making the service part
  of the default `up` set keeps "optional" meaning "removable/replaceable
  by a host-run instance," not "off by default while also being the
  default provider." No published port keeps spec FR-008 (never publicly
  reachable) true regardless.
- **Alternatives considered**: Compose profile gating (`profiles:
  ["ollama"]`) — the literal reading of the original request, but rejected
  once the default-provider clarification landed, for the reason above.

## 6a. Automatic model provisioning (spec addendum, User Story 4)

- **Decision**: Add a second, one-shot Compose service, `ollama-init`,
  reusing the **same** `ollama/ollama` image (no new image/Dockerfile to
  build or maintain), with its entrypoint overridden to run the `ollama`
  CLI already baked into that image rather than starting the server
  process:
  ```yaml
  ollama-init:
    image: ollama/ollama:latest
    restart: "no"
    environment:
      OLLAMA_HOST: http://ollama:11434
      OLLAMA_MODEL: ${OLLAMA_MODEL:-qwen3:4b}
      LLM_PROVIDER: ${LLM_PROVIDER:-ollama}
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        if [ "$$LLM_PROVIDER" != "ollama" ]; then
          echo "LLM_PROVIDER=$$LLM_PROVIDER — skipping Ollama model provisioning."
          exit 0
        fi
        echo "Ensuring Ollama model '$$OLLAMA_MODEL' is available..."
        exec ollama pull "$$OLLAMA_MODEL"
  ```
  The `ollama` service itself gains a healthcheck (`ollama list`, run
  in-container against its own server — no `curl`/extra tooling needed,
  already present in the image) so `condition: service_healthy` has
  something to wait on. The `app` service adds `ollama-init: condition:
  service_completed_successfully` to its existing `depends_on`, alongside
  the unchanged `db: condition: service_healthy`.
- **Rationale**, requirement by requirement:
  - *Wait for Ollama to be healthy first* (spec FR-020): Compose's own
    `condition: service_healthy` dependency mechanism already does this —
    no custom polling/retry loop needed in the init step itself.
  - *Same configured value as `OllamaLLMProvider`* (spec FR-021): both
    read `OLLAMA_MODEL` from the same `.env`/environment — the Compose
    variable substitution `${OLLAMA_MODEL:-qwen3:4b}` mirrors
    `config.py`'s own default exactly (single source of truth in the
    environment, not duplicated logic), so `OLLAMA_MODEL=qwen3:8b` changes
    what `ollama-init` provisions with zero code or Compose-file edits.
  - *Skip re-download if already present* (spec FR-022): `ollama pull` is
    natively idempotent — it diffs local content-addressed layers against
    the registry manifest and skips any already present, printing "already
    exists" and returning almost immediately. No separate
    check-then-pull scripting is needed; the underlying tool already
    provides exactly the behavior required (Principle XIII).
  - *App doesn't start until provisioning succeeds* (spec FR-023):
    `depends_on: ollama-init: condition: service_completed_successfully`
    means Compose will not start `app` at all until `ollama-init` exits
    `0`; if it exits non-zero, `app` never starts (spec FR-028 — visible
    failure, no silent continuation).
  - *`LLM_PROVIDER != ollama` must not block an Anthropic-only deployment*
    (spec FR-019's "when a deployment's local backend is configured"
    qualifier, and Assumptions): since the `ollama` service is
    unconditionally part of the default `up` set (§6, unchanged by this
    addendum) but the *app* must not be forced to wait on a real ~GB model
    download when it isn't even using Ollama, the conditional lives inside
    `ollama-init`'s own one-line shell check on `LLM_PROVIDER` — the only
    piece of "is Ollama actually the active backend" branching this
    feature introduces, and it is deployment/Compose-level, never
    application/domain code (spec FR-025, and consistent with the
    composition-boundary-only branching rule already established for
    `main.py`). When skipped, `ollama-init` still exits `0` quickly (no
    network call to a model registry), so it never blocks or fails an
    Anthropic-configured `app` startup.
  - *One-shot, not application code* (spec FR-025): `restart: "no"` plus a
    `service_completed_successfully` dependency is exactly Compose's
    built-in shape for "run once to completion, then never again unless
    explicitly re-run" — no custom orchestration needed.
  - *Internal network only, no new credentials* (spec FR-026/FR-027):
    `ollama-init` talks to `ollama` purely over the existing internal
    Compose network via `OLLAMA_HOST`; no port is published for this
    service, and Ollama's local API needs no credential by default —
    unchanged from §1's existing "no auth" finding.
  - *Persistent storage survives `down`/`up`, lost only on `down -v`*
    (spec FR-024): unchanged from the existing `ollama-data` named volume
    already mounted at `/root/.ollama` on the `ollama` service (§6,
    predates this addendum) — `ollama-init` writes into that same volume
    indirectly (via the `ollama` server it talks to), introducing no new
    volume.
  - *GPU compatibility, no duplicated GPU config* (spec FR-029):
    `ollama-init` never runs inference and therefore never needs GPU
    access; any GPU passthrough an operator adds (e.g. an NVIDIA `deploy.
    resources.reservations.devices` block) belongs solely on the `ollama`
    service definition. `ollama-init` and `app` carry no GPU stanza, now
    or if GPU support is added later — there is exactly one place in the
    Compose file GPU configuration would ever go.
- **Alternatives considered**:
  - Auto-pulling the model via a custom entrypoint baked into the `ollama`
    service's own container start, instead of a separate service —
    rejected: would re-run (or need extra logic to skip re-running) the
    pull check on every restart of the long-lived `ollama` service, and
    conflates "start the inference server" with "ensure a model exists" as
    one lifecycle instead of two, making the "app waits for model, not for
    server" ordering (FR-023) harder to express cleanly in Compose than
    two services with a `depends_on` chain.
  - Provisioning logic inside the FastAPI application (e.g. on startup,
    before serving traffic) — explicitly rejected by the spec itself
    (requirement 4: "Prefer a simple one-shot Docker Compose
    initialization service... instead of adding model-download logic to
    the FastAPI application"; FR-025's "never becomes part of core
    application/domain logic"). Also would need the app process itself to
    hold retry/backoff logic for a multi-gigabyte download before it could
    ever answer a health check — poor separation of concerns versus
    Compose's own dependency-ordering primitives already doing this job.
  - A custom Dockerfile/image just for `ollama-init` — rejected: the
    stock `ollama/ollama` image already contains the `ollama` CLI binary
    (it's the same binary as the server), so overriding `entrypoint`/
    `command` on the existing image is strictly simpler than building and
    maintaining a second image (Principle XIII).
  - Always running `ollama pull` unconditionally (no `LLM_PROVIDER` check)
    — rejected: would force every Anthropic-only deployment to
    successfully download a several-gigabyte model (and have outbound
    network access to Ollama's registry) just to start the application at
    all, directly contradicting FR-019's "when a deployment's local
    backend is configured" scoping and turning an unrelated backend choice
    into a hard startup dependency.

## 7. Evaluation across both backends

- **Decision**: `scripts/run_eval.py` gains no new HTTP-facing behavior —
  running it once per backend already works today by restarting the app
  with a different `LLM_PROVIDER` between runs (exactly User Story 2's
  "switch backends with configuration only" pattern). The only change is
  cosmetic: the script reads `LLM_PROVIDER` from the same configuration the
  app uses and labels its printed report with the active backend, so two
  runs' output is unambiguously comparable (spec FR-016).
- **Rationale**: Satisfies "runnable against either backend, producing
  backend-labeled results" (FR-016) with the smallest possible change —
  no new comparison tooling, no second HTTP client, no new script.
- **Alternatives considered**: A dedicated dual-provider comparison runner
  that queries both backends in a single process/run — rejected as
  unrequested scope (User Story 3 explicitly only requires that results be
  comparable, not that a single run produce both).

## 8. Startup logging of the active provider/model

- **Decision**: `main.py::create_app()` logs one INFO-level line, once, at
  the same point it already constructs the configured `LLMProvider`
  (research.md §5) — containing only `LLM_PROVIDER`'s value and the
  configured model name (`ANTHROPIC_MODEL` or `OLLAMA_MODEL`, whichever is
  active). It never includes `OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY`, or any
  other configuration value.
- **Rationale**: Spec FR-018/SC-007 — an operator restarting the app after
  changing `LLM_PROVIDER` needs a cheap way to confirm which backend
  actually took effect (a plain env-var typo would otherwise fail silently
  until the first chat request). Excluding the base URL is a deliberate,
  narrower rule than the general "no secrets in logs" principle already
  followed elsewhere (`infra/audit.py`, the Phase 5 provider-failure
  logging added this session): a URL isn't a credential, but internal
  network topology is still exactly the kind of internal detail Principle
  VIII/IX already say must never reach a log an operator might paste into
  a support channel or ticket.
- **Alternatives considered**: Logging the full resolved `Settings` object
  or the full provider configuration — rejected outright, since that would
  include `ANTHROPIC_API_KEY` and `AUTH_JWT_SECRET`; logging nothing at
  startup and relying on the first request's behavior to reveal the active
  backend — rejected as failing FR-018/SC-007's explicit requirement to
  confirm configuration without waiting for traffic.

## Summary of resolved decisions

| Item | Resolution |
|---|---|
| HTTP client | `httpx` directly (existing dependency); no new SDK |
| Ollama endpoint | `POST /api/chat`, `stream: false`, `options.num_predict` for output cap |
| Retry policy | Own bounded loop, reuses `PROVIDER_MAX_RETRIES` |
| Timeout | Separate `OLLAMA_TIMEOUT_SECONDS` setting |
| Budget isolation | New `usage_records.provider_name` column, structural (not inferred), safe 4-step backfill migration keyed only on `provider_kind` |
| Provider selection | `if/else` at the existing `main.py` composition boundary |
| Docker Compose | `ollama` service, no published port, part of default `up` set (not profile-gated) — reflects default-provider=ollama |
| Model pull | Automatic — one-shot `ollama-init` service (reuses the `ollama/ollama` image), `depends_on: ollama: condition: service_healthy`, `app` waits on `ollama-init: condition: service_completed_successfully`; skips itself (exit 0, no download) when `LLM_PROVIDER != ollama` |
| Eval comparison | Existing script + restart-between-runs; report labeled with active backend |
| Startup logging | One INFO line: provider + model only — never base URL, never credentials |
