"""FastAPI app factory (research.md §4a).

`create_app()` constructs the LLM and embedding providers exactly once —
at factory-call time, not per request, and not merely on module import.
Production uses the real providers; tests call `create_app(llm_provider=...,
embedding_provider=...)` with fakes and so never construct
`AnthropicLLMProvider`/`OllamaLLMProvider` or
`LocalSentenceTransformerEmbeddingProvider` at all (Design Constraint 2,
tasks.md) — no test triggers a real model load or a real Anthropic/Ollama
call merely by building a test app.

Which concrete `LLMProvider` gets built — `AnthropicLLMProvider` or
`OllamaLLMProvider` — is decided by `settings.LLM_PROVIDER` right here, and
ONLY here (feature 002-add-ollama-provider, research.md §5): this is the
one `if/else` in the whole codebase that branches on which LLM backend is
active. `application/ask_question.py` and every other layer downstream
only ever sees the `LLMProvider` Protocol.

There is deliberately no module-level `app = create_app()`: uvicorn is run
in factory mode (`uvicorn shiruno.main:create_app --factory`, see
Dockerfile) so importing this module — e.g. `from shiruno.main
import create_app` in conftest.py — never has the side effect of
constructing real providers.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from shiruno.api.errors import register_exception_handlers
from shiruno.api.routers import auth, chat, documents, health
from shiruno.config import Settings, get_settings
from shiruno.infra.concurrency import ChatConcurrencyGuard
from shiruno.infra.logging import configure_logging, get_logger
from shiruno.providers.embedding.local_sentence_transformer_provider import (
    LocalSentenceTransformerEmbeddingProvider,
)
from shiruno.providers.embedding.protocol import EmbeddingProvider
from shiruno.providers.llm.anthropic_provider import AnthropicLLMProvider
from shiruno.providers.llm.ollama_provider import OllamaLLMProvider
from shiruno.providers.llm.protocol import LLMProvider
from shiruno.public_site.router import router as public_site_router

_PUBLIC_SITE_STATIC_DIR = Path(__file__).resolve().parent / "public_site" / "static"

logger = get_logger(__name__)


def _build_configured_llm_provider(settings: Settings) -> LLMProvider:
    if settings.LLM_PROVIDER == "ollama":
        return OllamaLLMProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            max_retries=settings.PROVIDER_MAX_RETRIES,
            timeout_seconds=settings.OLLAMA_TIMEOUT_SECONDS,
            think=settings.OLLAMA_THINK,
            temperature=settings.OLLAMA_TEMPERATURE,
            seed=settings.OLLAMA_SEED,
        )
    return AnthropicLLMProvider(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        max_retries=settings.PROVIDER_MAX_RETRIES,
        timeout_seconds=settings.PROVIDER_TIMEOUT_SECONDS,
    )


def create_app(
    *,
    llm_provider: LLMProvider | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title="Shiruno API", version="0.1.0")
    register_exception_handlers(app)

    # The active model name, computed once here regardless of whether the
    # actual provider object below is real or (in every test) injected —
    # `application/ask_question.py` needs this plain string for usage
    # accounting (T012) without knowing or branching on which backend it
    # names (spec FR-011).
    active_model_name = (
        settings.OLLAMA_MODEL if settings.LLM_PROVIDER == "ollama" else settings.ANTHROPIC_MODEL
    )
    app.state.llm_provider_name = settings.LLM_PROVIDER
    app.state.llm_model_name = active_model_name

    # Startup visibility (spec FR-018/SC-007): names the active provider
    # and model only. Deliberately never includes OLLAMA_BASE_URL,
    # ANTHROPIC_API_KEY, or any other setting — an operator confirming
    # "which backend actually took effect" doesn't need, and must never
    # see, internal network addresses or credentials in a log line
    # (research.md §8).
    logger.info("LLM provider selected: %s (model=%s)", settings.LLM_PROVIDER, active_model_name)

    # Constructed once, here, at factory-call time — never per request.
    # Real providers are only ever built on the production path (no
    # override passed in); every automated test passes fakes instead.
    app.state.llm_provider = llm_provider or _build_configured_llm_provider(settings)
    app.state.embedding_provider = embedding_provider or LocalSentenceTransformerEmbeddingProvider(
        model_name=settings.EMBEDDING_MODEL_NAME,
    )

    # Process-local bounded concurrency guard for paid LLM calls (T066) —
    # always constructed, for both the real app and every test app, since
    # every `/chat` request needs a working guard regardless of which
    # providers are behind it (infra/concurrency.py).
    app.state.chat_concurrency_guard = ChatConcurrencyGuard(limit=settings.CHAT_CONCURRENCY_LIMIT)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(auth.router)
    app.include_router(documents.router)

    # Public, unauthenticated website (feature 005-public-club-website) —
    # purely additive: no existing route, contract, or behavior above this
    # line is touched. Registered last so it can never shadow an existing
    # route (Starlette matches in registration order).
    app.include_router(public_site_router)
    app.mount(
        "/static/site",
        StaticFiles(directory=str(_PUBLIC_SITE_STATIC_DIR)),
        name="public_site_static",
    )

    return app
