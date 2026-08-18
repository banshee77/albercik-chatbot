# Phase 0 Research: Albertos RAG Support Chatbot (MVP)

This document resolves every technical unknown the spec deliberately deferred to
planning (chunking strategy, embedding model, retrieval parameters, rate-limiting
and budget mechanism without Redis, auth mechanism, retry limits, and test
infrastructure), each constrained by the project constitution — in particular
Principle X (Cost Safety), Principle XII/XIII (Engineering Quality / Simplicity),
and Principles V–VII (provider/cloud neutrality).

## 1. Administrator authentication mechanism

- **Decision**: JWT bearer tokens issued via an OAuth2-password-style login
  endpoint (`OAuth2PasswordBearer` in FastAPI terms), signed with a server-side
  secret (`AUTH_JWT_SECRET`), short expiry (e.g., 60 minutes, configurable).
  Passwords hashed with `bcrypt`. Administrator accounts live in a Postgres
  table, provisioned via a CLI seed command — no self-service registration
  endpoint exists.
- **Rationale**: Stateless (no session store, so no new infra beyond Postgres,
  which is already mandatory), well-supported directly by FastAPI's own docs
  and dependency-injection model, trivially mockable/testable, and swappable
  later for an external identity provider (OIDC) without changing the shape of
  the `get_current_administrator` dependency other endpoints rely on — the
  route-level contract (a validated `Administrator` in the request context)
  stays the same regardless of what issues the token.
- **Alternatives considered**:
  - Server-side session cookies + a `sessions` table — equally simple, but adds
    a table and an explicit cleanup/expiry job for no material benefit over
    stateless JWTs at this scale; rejected on YAGNI grounds.
  - An external identity provider (Auth0/Cognito/etc.) — explicitly against
    "avoid a complex identity platform" in the spec and Principle XIII
    (Simplicity); deferred entirely, the JWT design leaves room for it later.

## 2. Rate limiting without Redis

- **Decision**: Postgres-backed fixed-window counters. A single table
  (`rate_limit_windows`) keyed by `(source_key, window_start)`, incremented via
  an atomic `INSERT ... ON CONFLICT DO UPDATE` per request; a request is
  rejected once the counter for the current window exceeds the configured
  limit. `source_key` is the client IP as resolved from the trusted-proxy
  configuration (never a raw, unvalidated `X-Forwarded-For`). Stale windows are
  pruned lazily (a cheap `DELETE WHERE window_start < cutoff` on a small
  fraction of requests, or a periodic task) rather than via a background
  service.
- **Rationale**: Postgres is already the mandatory, always-present dependency
  (Principle XIV); a DB-backed counter is correct across multiple app
  processes/instances, which an in-process in-memory counter is not — and
  correctness here is a Principle X (Cost Safety, NON-NEGOTIABLE) concern, not
  a nice-to-have. This avoids adding Redis purely for rate limiting, matching
  Principle XIII and the constitution's explicit MVP Scope Boundaries guidance.
- **Alternatives considered**:
  - In-process in-memory limiter (e.g., a token-bucket dict) — simplest, but
    silently incorrect the moment there is more than one worker process or
    container instance; rejected because a rate limiter that can be trivially
    bypassed by hitting a different worker fails Principle X outright.
  - Redis-backed limiter (`slowapi`, `limits` with a Redis backend) — the
    canonical production answer, but introduces new infrastructure the
    constitution explicitly says to avoid "unless the technical plan
    demonstrates it's necessary"; Postgres is sufficient at MVP request volume,
    so it isn't.

## 3. Usage budgets and the LLM kill switch

- **Decision**: Budgets are enforced by querying the same `usage_records` table
  required for accounting (FR-047) — e.g., `COUNT(*)` or `SUM(total_tokens)`
  over a rolling or fixed window — compared against a configured limit
  (`LLM_MAX_REQUESTS_PER_HOUR`, `LLM_MAX_TOKENS_PER_DAY`, etc.). No separate
  aggregate/counter table for MVP volume. The kill switch is a single
  configuration flag (`LLM_ENABLED`, matching the spec's own example) read from
  process settings; toggling it requires a configuration change and process
  restart, not a code deployment/rebuild, which satisfies FR-043 as written.
  If the budget query itself fails (DB unavailable), the request is declined
  (fail closed), per Principle X.
- **Rationale**: Reusing `usage_records` avoids a second source of truth for
  usage state (YAGNI/DRY per Principle XII). A single settings flag is the
  simplest mechanism that satisfies "disable without a code deployment";
  anything fancier (a DB-backed toggle with cache invalidation, an admin UI to
  flip it) is explicitly out of scope for the MVP and not justified by a
  concrete current requirement.
- **Alternatives considered**: A dedicated `budget_counters` table updated
  incrementally on every request — faster to query at very high volume, but
  adds a second place usage state can drift from `usage_records`; rejected as
  premature optimization for MVP traffic levels.

## 4. Embedding provider and model

- **Decision**: A locally-run `sentence-transformers` model,
  `intfloat/multilingual-e5-small` (384 dimensions), as the initial
  `EmbeddingProvider` implementation — `LocalSentenceTransformerEmbeddingProvider`,
  behind the Principle VI `Protocol` interface. No external embedding API is
  called and no embedding-provider API key is required or read from
  configuration.
- **Rationale**: The knowledge base and all questions are Polish-only (per the
  spec's language-scope clarification); `multilingual-e5-small` is trained
  and benchmarked for multilingual (including Polish) retrieval and is small
  enough (~470 MB) to run comfortably on CPU with no GPU requirement, which
  matches Principle XIII (Simplicity) and the constitution's explicit
  allowance for "self-hosted/open-source embedding models" under Principle
  VI. Running embeddings in-process also removes an entire class of failure
  mode the cost-safety design (Principle X) otherwise has to defend against:
  there is no per-call embedding cost, no embedding-provider rate limit, and
  no embedding-provider outage to retry against or fail closed on — only the
  Claude/Anthropic LLM call remains a metered, budget-tracked external
  dependency. The `sentence-transformers` package is a single well-maintained
  dependency (CPU build of `torch` as its backend) rather than a hand-rolled
  inference stack, keeping this a one-dependency addition, not new
  infrastructure.
- **Alternatives considered**:
  - Voyage AI `voyage-multilingual-2` (hosted API, 1024 dimensions) — good
    multilingual quality and no local ML runtime to manage, but rejected per
    updated project direction: it's a per-call paid external dependency and
    requires an API key, both of which this MVP now explicitly avoids for
    the embedding path. (Originally selected in an earlier revision of this
    document; superseded by this decision.)
  - OpenAI `text-embedding-3-small` — same objection as Voyage: a paid,
    keyed, external API call per chunk/query, which the project now avoids
    entirely for embeddings.
  - Larger local models (e.g., `intfloat/multilingual-e5-base` or
    `-large`) — somewhat higher retrieval quality, but bigger download,
    slower CPU inference, and more RAM per worker process; `-small` is the
    better MVP starting point and the model is swappable later behind the
    `Protocol` (and via the configurable model-name setting, §4a below)
    without any core-logic change if quality proves insufficient.
- **Schema consequence**: `pgvector` embedding columns are dimension `384` to
  match this model (Principle Data consequence recorded in `data-model.md`).
  Changing the configured model to one with a different output dimension
  requires a schema migration — this coupling is inherent to `pgvector` and
  not specific to running the model locally.

## 4a. Local embedding runtime: loading, configuration, and operational tradeoff

- **Decision**: `sentence-transformers` is used only inside
  `providers/embedding/local_sentence_transformer_provider.py`
  (`LocalSentenceTransformerEmbeddingProvider`), the sole implementation of
  the `EmbeddingProvider` Protocol for this MVP. Core RAG logic
  (`domain/`, `application/`) imports only the Protocol, never
  `sentence_transformers` directly. The model name is a configuration value
  (`EMBEDDING_MODEL_NAME`, default `intfloat/multilingual-e5-small`) read via
  Pydantic Settings, not hardcoded, so it can be changed without a code
  change (a dimension change still requires the migration noted above). The
  `SentenceTransformer` instance is constructed once at application startup
  (e.g., in the FastAPI app factory / a process-wide singleton / dependency
  with `lru_cache`) and reused for every request's embedding calls — it is
  never re-instantiated per request, since model loading (reading weights
  from disk into memory) is measurably expensive relative to a single
  embedding call. The same provider instance, and therefore the same model,
  is used to embed both document chunks at ingestion time and visitor
  questions at query time (FR-024's dimensional-compatibility requirement
  reduces to "the same model" rather than something that must be
  independently verified).
- **Rationale**: This satisfies "embeddings must be generated locally," "no
  embedding-provider API key," and "model loading happens once per process"
  as hard requirements, while keeping the Protocol boundary (Principle VI)
  intact so a future swap back to a hosted provider — or to a different
  local model — stays a single new file plus a settings change, never a
  `domain/`/`application/` change.
- **Operational tradeoff (explicitly accepted for this MVP)**: local
  embeddings eliminate per-request embedding API cost and remove an external
  provider dependency/outage class entirely, but they move that cost onto
  the application's own infrastructure: the model (~470 MB of weights) must
  be present in the container image or downloaded on first startup, it
  consumes CPU during every embedding call (chunk ingestion and every chat
  query) and holds its weights resident in RAM for the life of the process,
  and it measurably increases container image size and cold-start time
  versus an HTTP-only embedding client. This is judged acceptable for MVP
  scale (Scale/Scope in `plan.md`) and is explicitly the tradeoff being
  made; if per-instance CPU/RAM pressure or image size becomes a concrete
  problem at higher scale, the `Protocol` boundary keeps a hosted-provider
  swap-back cheap.
- **Testing consequence**: unit/contract tests use a fake, deterministic
  `EmbeddingProvider` (research.md §8) and MUST NOT import
  `sentence_transformers` or load `intfloat/multilingual-e5-small` — that
  would make the test suite slow and dependent on model weights being
  present. The real `LocalSentenceTransformerEmbeddingProvider` is exercised
  only in integration/runtime scenarios where it is actually required.

## 5. Chunking strategy

- **Decision**: Deterministic, paragraph-aware character-based chunking: split
  document text on blank-line paragraph boundaries, then greedily pack
  paragraphs into chunks up to a configurable character budget
  (`CHUNK_SIZE_CHARS`, default 1000) with a configurable character overlap
  (`CHUNK_OVERLAP_CHARS`, default 150, ~15%) carried from the end of one chunk
  into the start of the next. Empty/whitespace-only chunks are dropped before
  storage.
- **Rationale**: Plain Python string splitting has no dependency, is trivially
  unit-testable and fully deterministic (same input → same chunks, per spec
  FR-018), and respects Principle XIII's explicit instruction to prefer simple
  explicit code "over introducing a large framework only for chunking" (i.e.,
  no LangChain/LlamaIndex text splitters). Character count is used instead of
  a token-counting library as a simple, dependency-free proxy for chunk size;
  it's an approximation, not an exact token budget, which is acceptable since
  the hard token ceiling sent to Claude is separately enforced (Principle X)
  regardless of how chunks were produced.
- **Alternatives considered**: A tokenizer-based splitter (`tiktoken`) — more
  precise chunk sizing relative to LLM tokens, but adds a dependency whose
  tokenizer doesn't even match Claude's own tokenization; rejected as
  complexity without a corresponding accuracy win for MVP purposes.

## 6. Retrieval: similarity metric, threshold, Top-K, index

- **Decision**: Cosine similarity (`pgvector`'s `<=>` operator), Top-K default
  of 5 chunks, a relevance threshold default of cosine similarity ≥ 0.75 (both
  configurable), and an `HNSW` `pgvector` index on the embedding column.
- **Rationale**: Cosine similarity is the standard choice for normalized
  sentence/paragraph embeddings and is what `intfloat/multilingual-e5-small`
  (like most modern sentence-embedding models) is tuned against. `HNSW`
  needs no data-size-dependent
  tuning parameter (unlike `ivfflat`'s `lists`), which matters for a fresh,
  small MVP knowledge base whose eventual size isn't known yet — one less
  thing to get wrong. Top-K=5 and threshold=0.75 are reasonable, clearly
  documented MVP starting points, deliberately made configuration values (not
  hardcoded) so they can be tuned against real Albertos content without a code
  change, per FR-025/FR-026.
- **Alternatives considered**: `ivfflat` index — comparable query performance
  once tuned, but requires choosing `lists` based on row count, which is an
  extra moving part with no benefit at MVP scale; deferred as a later
  optimization if the knowledge base grows large enough to matter.

**Addendum (2026-08-17, Phase 3 RAG calibration checkpoint)**: Calibrated
the real `intfloat/multilingual-e5-small` model against a synthetic
Albertos-shaped fixture set (`tests/fixtures/albertos_kb/`,
`scripts/rag_calibration.py`) across seven question categories. Two
findings changed defaults or design; a third is deliberately **not**
addressed yet:

1. **Threshold raised 0.75 → 0.80.** At 0.75, 2 of 3 "clearly unrelated"
   calibration questions scored *above* threshold and were only rejected
   because the scope classifier (domain/scope.py) caught them first — the
   threshold provided no real defense-in-depth backstop. At 0.80, all
   unrelated test cases were correctly rejected while every answerable
   case in the fixture set (min 0.834) was still accepted. This is
   reported as a defensible interim default from a qualitative separation
   pattern, not a value fit exactly to this fixture set.
2. **E5 query/passage prefixing fixed.** The embedding provider was
   sending raw, unprefixed text for both questions and chunks, contrary to
   `multilingual-e5-small`'s documented asymmetric training convention
   (`"query: "` / `"passage: "`). Fixed in
   `LocalSentenceTransformerEmbeddingProvider` only, behind a new
   `embed_query`/`embed_passages` `EmbeddingProvider` Protocol split (no
   other layer knows the concrete model is E5 — Principle VI). Empirically
   the prefix fix shifted scores only slightly (±0.01–0.03) and did not
   materially change rankings in this calibration run — it was fixed for
   documented-usage correctness, not because it was the dominant driver of
   finding 1.
3. **KNOWN, DEFERRED RISK — not solved**: raw cosine similarity, even at
   the new threshold, **cannot reliably distinguish a genuinely answerable
   question from an Albertos-related question the knowledge base simply
   doesn't cover**. In the calibration set, both categories scored in the
   same ~0.83-0.91 range; no threshold value in that range separates them.
   Per explicit instruction, this was **not** "fixed" by raising the
   threshold further, keyword heuristics, more scope regexes, an
   LLM-based classifier, a reranker/cross-encoder, or hybrid search — all
   of those are deferred past this checkpoint. `domain/retrieval.py`'s
   `select_sufficient_chunks` docstring carries the same warning at the
   point the threshold is actually applied. Re-evaluate once Phase 4
   allows real Albertos content to be uploaded and calibrated against —
   a small, synthetic, single-fact-per-topic fixture set is not a
   sufficient basis to design a permanent mitigation.

## 7. Provider retry policy

- **Decision**: Bounded retries for transient LLM/embedding provider failures
  (timeouts, 5xx, connection errors) only: max 2 retries (3 attempts total),
  exponential backoff (0.5s, 1s), no retry on 4xx/authentication errors.
  Configurable via `PROVIDER_MAX_RETRIES`.
- **Rationale**: Directly satisfies FR-036/Principle X's "retries MUST be
  capped at a bounded, configured maximum" and the constitution's explicit
  "never implement unlimited automatic retries." Two retries is enough to ride
  out a transient blip without meaningfully multiplying cost or latency on a
  hard failure.
- **Alternatives considered**: No retries at all — simpler, but sacrifices
  resilience to a single transient network blip for no real simplicity gain;
  a small bounded retry is cheap. Unbounded/backoff-until-success — explicitly
  forbidden by the constitution.

## 8. Test infrastructure for `pgvector`-backed persistence

- **Decision**: Integration tests run against a real PostgreSQL + `pgvector`
  instance started via Docker Compose (a dedicated `db-test` service /
  ephemeral test database), since there is no in-memory substitute for
  `pgvector`'s vector operators. Unit tests for domain/RAG logic (chunking,
  scope classification, relevance evaluation, prompt assembly) run with no
  database at all. Contract/API tests use FastAPI's `TestClient`/
  `httpx.AsyncClient` with the `LLMProvider` and `EmbeddingProvider`
  `Protocol` implementations swapped for deterministic in-memory fakes — a
  fake `EmbeddingProvider` returns fixed-dimension vectors deterministically
  from input text (e.g., a hash-based or seeded-random generator, dimension
  384 to match the real model) with no I/O — so no test run ever performs a
  paid LLM provider call (Principle XI) or loads the real
  `sentence-transformers` model / `intfloat/multilingual-e5-small` weights.
  The real `LocalSentenceTransformerEmbeddingProvider` (research.md §4a) is
  exercised only in a narrow integration/runtime scope where actually
  generating a real embedding is the point.
- **Rationale**: This is the only way to actually exercise real vector
  similarity search behavior (top-K ordering, threshold behavior) rather than
  mocking it into meaninglessness, while keeping the bulk of the test suite
  (domain logic, API contracts) fast, network-free, and free of any
  dependency on multi-hundred-MB model weights being present on disk.
- **Alternatives considered**: SQLite for tests — impossible, SQLite has no
  `pgvector` equivalent extension; a hand-rolled Python cosine-similarity
  stand-in — rejected because it wouldn't actually validate the real SQL/index
  behavior the production code depends on.

## 9. Phase 5/6 implementation additions not in the original design

Concrete additions made while implementing User Stories 3 and 4 that this
document didn't originally call out:

- **Bounded concurrency guard** (`infra/concurrency.py`): a process-local
  `threading.Semaphore` (not `asyncio.Semaphore` — FastAPI runs sync
  routes in a real OS thread pool) bounding concurrent paid LLM calls,
  non-blocking acquire so an over-capacity request fails fast
  (`unavailable`) instead of queuing. Explicitly does not coordinate
  across multiple `app` instances — see README.md "Known limitations".
- **Request-body-size guard** (`api/deps.py::require_bounded_request_body`):
  a `Content-Length`-based check on `/chat`, run before Pydantic parses
  the body, backstopping the question's own character-length limit
  against a client sending a wildly oversized JSON payload.
- **Context-character limit** (`domain/retrieval.py::limit_context_chars`):
  caps total retrieved-chunk characters passed into the LLM prompt,
  applied after relevance filtering and before prompt assembly —
  `RETRIEVAL_TOP_K` already caps chunk *count*, this caps total *size*.
- **Provider timeout** (`PROVIDER_TIMEOUT_SECONDS`, passed to the
  `Anthropic` client): bounds each individual attempt inside
  `AnthropicLLMProvider`'s existing retry loop so a public request can
  never hang indefinitely on a stalled provider connection.
- **Trusted-proxy client-IP resolution** (`TRUSTED_PROXY_COUNT`,
  `infra/rate_limit.py::resolve_client_ip`): §2 below already specified
  "never a raw, unvalidated `X-Forwarded-For`"; the concrete mechanism
  implemented is a configurable trusted-hop count, defaulting to 0 (never
  trust the header) since `docker-compose.yml` has no reverse proxy today.
- **Prompt delimiter neutralization** (`domain/prompting.py`, Phase 6):
  literal occurrences of the `<<<KONTEKST_START>>>`/`<<<KONTEKST_END>>>`
  tokens inside untrusted text (chunk content, chunk labels, the
  visitor's question) are replaced with lookalike Unicode brackets before
  insertion, so untrusted content can never forge a second block boundary
  — found and fixed during Phase 6's prompt-injection hardening pass.

## Summary of resolved Technical Context

| Item | Resolution |
|---|---|
| Language/Version | Python 3.14 |
| Web framework | FastAPI |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Storage | PostgreSQL + `pgvector` |
| Auth | JWT bearer tokens, `bcrypt` password hashing, Postgres-backed admin accounts |
| Rate limiting | Postgres-backed fixed-window counters (no Redis) |
| Budget / kill switch | Query over `usage_records` + `LLM_ENABLED` config flag |
| Embedding provider | Local `sentence-transformers`, `intfloat/multilingual-e5-small` (384-dim, CPU, no API key), behind a `Protocol` |
| LLM provider | Claude via the Anthropic API, behind a `Protocol` |
| Chunking | Deterministic paragraph-aware character chunking, no framework |
| Retrieval | Cosine similarity, Top-K=5 default, threshold=0.80 default (raised from an initial 0.75 — §6 addendum), HNSW index |
| Retries | Max 2 retries, bounded, exponential backoff, no retry on 4xx |
| Testing | pytest; unit tests provider-free; integration tests against real Postgres+pgvector via Docker Compose; contract tests with fake providers |
| Target platform | Linux container (Docker / Docker Compose), no fixed cloud host |
| Project type | Single backend web service (no frontend in this MVP) |
| Language scope | Polish only (chat, scope classification, responses) |
