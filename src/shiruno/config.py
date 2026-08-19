from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration (research.md §2-7).

    Every value here is a configuration knob, not a hardcoded constant, per
    FR-019/FR-025/FR-026/FR-036/FR-038/FR-044 — thresholds are tunable
    without a code change.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg://albercik:albercik@localhost:5432/albercik"

    # --- LLM provider (Claude via Anthropic API — Principle V) ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    LLM_ENABLED: bool = True

    # --- LLM provider selection (feature 002-add-ollama-provider) ---
    # Server-side only — never derived from request content (Clarifications
    # session, 2026-08-18; spec FR-002). Defaults to `ollama` so a fresh
    # deployment works with zero paid-API setup; anyone who wants the paid
    # provider (including an existing Anthropic-only deployment upgrading
    # into this feature) must set this explicitly (spec FR-003).
    LLM_PROVIDER: Literal["anthropic", "ollama"] = "ollama"

    # --- Ollama provider (research.md §2, §3, §6) ---
    # Internal Docker network address by default — this deployment's
    # `docker-compose.yml` never publishes Ollama's port; only the `app`
    # service can reach it (spec FR-008).
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    # Never hardcoded in application/domain logic (spec FR-006). Changed
    # from `qwen3:4b` to `qwen3:8b` (2026-08-19, feature
    # 004-rag-answerability-and-ollama-performance research.md §17):
    # measured, deterministic (OLLAMA_TEMPERATURE=0/OLLAMA_SEED=42) grounded
    # accuracy 19/20 vs. 4B's 17/20, with insufficient-information rejection
    # (7/7), false-grounded (0/7), and out-of-scope (3/3) all unchanged, and
    # latency/VRAM (~6.0 GB) remaining acceptable on the RTX 3070 reference
    # host — see eval/README.md's "Model selection: qwen3:8b adopted as
    # default" section for the full comparison. `qwen3:4b` remains a valid
    # lower-resource manual override (`OLLAMA_MODEL=qwen3:4b`); SC-001
    # (20/20) is still not met on either model (question #6 fails on both).
    OLLAMA_MODEL: str = "qwen3:8b"
    # Independent from PROVIDER_TIMEOUT_SECONDS (Anthropic's) — local
    # CPU-hosted inference of even a small model is expected to be slower
    # than the hosted API, so this defaults more generously.
    OLLAMA_TIMEOUT_SECONDS: float = 60.0
    # Server-side only (feature 004-rag-answerability-and-ollama-performance,
    # research.md §6) — controls Qwen3's hybrid-reasoning "thinking" step
    # before it answers. Owned entirely by `OllamaLLMProvider`, never part
    # of the shared `LLMProvider.complete()` signature and never derived
    # from request content (FR-013); the Anthropic backend is unaffected
    # regardless of this value (FR-015). Defaults to `False` — thinking
    # mode is a documented, measured latency cost (spec Story 3, ~4-19s
    # grounded calls), so the safer MVP default is off until an A/B
    # comparison (SC-004) justifies changing it.
    OLLAMA_THINK: bool = False

    # --- Ollama generation determinism (research.md §14 — reproducibility
    # experiment) ---
    # A same prompt+context+model call was observed to yield a different
    # `supported` decision across separate invocations at Ollama's default
    # (nonzero) sampling temperature — this made single-run eval deltas an
    # unreliable signal for judging prompt changes. Both knobs are
    # Ollama-provider-only configuration (like OLLAMA_THINK above): owned
    # entirely by `OllamaLLMProvider`, never part of the shared
    # `LLMProvider.complete()` signature, and never derived from request
    # content — a public request can never override them. The Anthropic
    # backend is unaffected regardless of these values.
    OLLAMA_TEMPERATURE: float = 0.0
    OLLAMA_SEED: int = 42

    # --- Embedding provider (local, sentence-transformers — research.md §4/§4a) ---
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-small"
    EMBEDDING_DIMENSIONS: int = 384

    # --- Auth (research.md §1) ---
    # No default (pre-Phase-5 security checkpoint, 2026-08-17): an
    # insecure-but-present default here would mean a deployment that
    # forgets to set this env var silently starts up and signs/verifies
    # admin JWTs with a secret visible in this repository's own source
    # history — required to be explicitly configured instead; Settings()
    # construction fails loudly if it's absent. Local dev/tests get a
    # value from `.env` (see `.env.example`) or, for the test suite
    # specifically, tests/conftest.py's env default — never from here.
    AUTH_JWT_SECRET: str
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_JWT_EXPIRE_MINUTES: int = 60

    # RFC 7518 §3.2 recommends an HMAC key at least as long as the hash
    # output it's paired with — 32 bytes (256 bits) for HS256, the
    # configured default algorithm; PyJWT itself warns below this length.
    # Simple length-only check, not a full entropy/strength estimator —
    # "reasonable minimum," not a password-strength meter (pre-Phase-5
    # security checkpoint, 2026-08-17).
    _MIN_JWT_SECRET_LENGTH: ClassVar[int] = 32

    @field_validator("AUTH_JWT_SECRET")
    @classmethod
    def _require_strong_jwt_secret(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "AUTH_JWT_SECRET must be a non-empty value — no default is provided "
                "(research.md §1, pre-Phase-5 security checkpoint)."
            )
        if len(value) < cls._MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"AUTH_JWT_SECRET must be at least {cls._MIN_JWT_SECRET_LENGTH} characters "
                "(RFC 7518 §3.2 minimum for HMAC-SHA256) — generate one with, e.g., "
                "`openssl rand -hex 32`."
            )
        return value

    # --- Chunking (research.md §5) ---
    CHUNK_SIZE_CHARS: int = 1000
    CHUNK_OVERLAP_CHARS: int = 150

    # --- Retrieval (research.md §6) ---
    RETRIEVAL_TOP_K: int = 5
    # Interim MVP default, raised from 0.75 to 0.80 by the Phase 3 RAG
    # calibration checkpoint (2026-08-17, research.md §6 addendum). This is
    # a retrieval-quality / defense-in-depth filter only — it separates
    # "clearly unrelated to Albertos" from "Albertos-flavored" reasonably
    # well, but the calibration demonstrated it CANNOT reliably distinguish
    # a genuinely answerable question from an Albertos-related question the
    # knowledge base simply doesn't cover: both scored in the same 0.83-0.91
    # range against the calibration fixture set. Do NOT treat a chunk
    # clearing this threshold as proof it actually answers the question —
    # that determination still ultimately rests on the LLM reading the
    # retrieved content, grounded per domain/prompting.py. Re-tune only
    # against real Albertos content once Phase 4 upload exists.
    RETRIEVAL_RELEVANCE_THRESHOLD: float = 0.80

    # --- Provider retries (research.md §7; Design Constraint 1 — the only
    # place this ceiling is enforced is AnthropicLLMProvider) ---
    PROVIDER_MAX_RETRIES: int = 2

    # --- Answer generation (FR-035: fixed by server config, never
    # client-influenced) ---
    LLM_MAX_ANSWER_TOKENS: int = 1024

    # --- Abuse / cost protection (Principle X, research.md §2-3) ---
    MAX_QUESTION_LENGTH_CHARS: int = 2000
    MAX_UPLOAD_SIZE_BYTES: int = 5_000_000
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 20
    BUDGET_MAX_LLM_REQUESTS_PER_HOUR: int = 200

    # --- Phase 5 (User Story 3) cost/abuse controls ---

    # Declared request-body byte size above which /chat is rejected before
    # Pydantic even parses JSON out of it (tasks.md T057). A generous bound
    # relative to MAX_QUESTION_LENGTH_CHARS — 2000 UTF-8 characters is at
    # most ~8000 bytes (4 bytes/char worst case) plus JSON framing — chosen
    # so legitimate requests are never affected; this exists only to stop a
    # client from forcing the server to buffer a wildly oversized body.
    MAX_CHAT_REQUEST_BODY_BYTES: int = 16_000

    # Total characters of retrieved chunk content allowed into a single LLM
    # prompt (domain/retrieval.py::limit_context_chars), enforced *after*
    # relevance filtering and *before* prompt assembly/the LLM call. Default
    # comfortably covers RETRIEVAL_TOP_K=5 chunks at the CHUNK_SIZE_CHARS=
    # 1000 default with slack for a modestly oversized chunk.
    MAX_CONTEXT_CHARS: int = 6000

    # Bounded concurrent paid-LLM calls in flight at once (tasks.md T066).
    # Process-local (a `threading.Semaphore`, infra/concurrency.py) — this
    # deployment is a single `app` container (docker-compose.yml); a future
    # multi-instance deployment would need this replaced with a
    # cross-instance bound (e.g. a Postgres-backed counter mirroring
    # infra/rate_limit.py's approach), not this in-process primitive.
    CHAT_CONCURRENCY_LIMIT: int = 4

    # Per-call timeout (seconds) passed to the Anthropic client so a public
    # request can never hang indefinitely on a stalled provider connection
    # (tasks.md T067). Applies to each individual attempt inside
    # AnthropicLLMProvider's own bounded-retry loop (Design Constraint 1) —
    # a timed-out attempt is retried like any other transient failure, up to
    # PROVIDER_MAX_RETRIES, never retried again by any other layer.
    PROVIDER_TIMEOUT_SECONDS: float = 20.0

    # Number of trusted reverse proxies in front of this app, for
    # X-Forwarded-For-based client-IP resolution in the rate limiter
    # (infra/rate_limit.py, research.md §2). Default 0: this deployment's
    # docker-compose.yml exposes the `app` service directly with no reverse
    # proxy in between, so the only safe default is to trust nothing from
    # the header and always use the direct TCP peer address — an
    # unauthenticated client cannot get a bogus X-Forwarded-For value
    # trusted as its rate-limit identity. Set to N only once this app is
    # actually deployed behind N trusted reverse proxies.
    TRUSTED_PROXY_COUNT: int = 0


@lru_cache
def get_settings() -> Settings:
    # AUTH_JWT_SECRET has no default and is populated from the
    # environment/`.env` by pydantic-settings at construction time, not by
    # this call site — mypy can't see that, hence the ignore (a documented
    # pydantic-settings/mypy friction point, not a real missing argument).
    return Settings()  # type: ignore[call-arg]
