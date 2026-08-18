"""FastAPI app factory (research.md §4a).

`create_app()` constructs the LLM and embedding providers exactly once —
at factory-call time, not per request, and not merely on module import.
Production uses the real providers; tests call `create_app(llm_provider=...,
embedding_provider=...)` with fakes and so never construct
`AnthropicLLMProvider` or `LocalSentenceTransformerEmbeddingProvider` at all
(Design Constraint 2, tasks.md) — no test triggers a real model load or a
real Anthropic call merely by building a test app.

There is deliberately no module-level `app = create_app()`: uvicorn is run
in factory mode (`uvicorn albercik_chatbot.main:create_app --factory`, see
Dockerfile) so importing this module — e.g. `from albercik_chatbot.main
import create_app` in conftest.py — never has the side effect of
constructing real providers.
"""

from fastapi import FastAPI

from albercik_chatbot.api.errors import register_exception_handlers
from albercik_chatbot.api.routers import auth, chat, documents, health
from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.concurrency import ChatConcurrencyGuard
from albercik_chatbot.infra.logging import configure_logging
from albercik_chatbot.providers.embedding.local_sentence_transformer_provider import (
    LocalSentenceTransformerEmbeddingProvider,
)
from albercik_chatbot.providers.embedding.protocol import EmbeddingProvider
from albercik_chatbot.providers.llm.anthropic_provider import AnthropicLLMProvider
from albercik_chatbot.providers.llm.protocol import LLMProvider


def create_app(
    *,
    llm_provider: LLMProvider | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title="Albercik Chatbot API", version="0.1.0")
    register_exception_handlers(app)

    # Constructed once, here, at factory-call time — never per request.
    # Real providers are only ever built on the production path (no
    # override passed in); every automated test passes fakes instead.
    app.state.llm_provider = llm_provider or AnthropicLLMProvider(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        max_retries=settings.PROVIDER_MAX_RETRIES,
        timeout_seconds=settings.PROVIDER_TIMEOUT_SECONDS,
    )
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

    return app
