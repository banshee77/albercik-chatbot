"""Unit tests for CORS wiring (feature 013-admin-platform-shell,
research.md R8; FR-024). `CORSMiddleware` must never be registered unless
an operator explicitly sets `CORS_ALLOWED_ORIGINS`, and the configured
origin list must never be a wildcard.
"""

from fastapi.middleware.cors import CORSMiddleware

from shiruno.config import get_settings
from shiruno.main import create_app
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider
from tests.fakes.fake_llm_provider import FakeLLMProvider


def _cors_middleware(app):
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            return middleware
    return None


def test_cors_middleware_absent_by_default(monkeypatch) -> None:
    # Explicitly set to empty rather than delenv: a developer's local
    # .env may itself set CORS_ALLOWED_ORIGINS (e.g. for apps/admin/
    # local development), and pydantic-settings reads that dotenv file
    # directly — delenv only removes the process env var, not the
    # dotenv-sourced value, so this test must not depend on the local
    # .env being empty.
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    get_settings.cache_clear()

    app = create_app(llm_provider=FakeLLMProvider(), embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    assert _cors_middleware(app) is None


def test_cors_middleware_allows_only_configured_origins(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    get_settings.cache_clear()

    app = create_app(llm_provider=FakeLLMProvider(), embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    middleware = _cors_middleware(app)
    assert middleware is not None
    assert middleware.kwargs["allow_origins"] == ["http://localhost:5173"]
    assert middleware.kwargs["allow_origins"] != ["*"]


def test_cors_middleware_never_wildcard_with_multiple_origins(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,https://admin.example.com"
    )
    get_settings.cache_clear()

    app = create_app(llm_provider=FakeLLMProvider(), embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    middleware = _cors_middleware(app)
    assert middleware is not None
    assert middleware.kwargs["allow_origins"] == [
        "http://localhost:5173",
        "https://admin.example.com",
    ]
    assert "*" not in middleware.kwargs["allow_origins"]
