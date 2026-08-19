"""Shared test helper for feature 002-add-ollama-provider's User Story 2
parity tests: builds a `/chat`-ready app with an explicit `LLM_PROVIDER`-
driven backend selection and injected fakes, `get_session` overridden to
the shared `db_session` — mirrors `test_chat_ollama_default.py`'s pattern
(US1), factored out here since every US2 parity test needs the same setup
across at least two configurations.

`LLM_PROVIDER` (and any other env var a caller wants to vary) MUST be
monkeypatched by the caller *before* calling `build_app`, since
`create_app()` reads `get_settings()` at factory-call time — this helper
does not do any environment setup itself.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from shiruno.main import create_app
from shiruno.persistence.database import get_session
from shiruno.providers.embedding.protocol import EmbeddingProvider
from shiruno.providers.llm.protocol import LLMProvider


def build_app(
    *, llm_provider: LLMProvider, embedding_provider: EmbeddingProvider, db_session
) -> FastAPI:
    app = create_app(llm_provider=llm_provider, embedding_provider=embedding_provider)
    app.dependency_overrides[get_session] = lambda: db_session
    return app


@asynccontextmanager
async def client_for(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
