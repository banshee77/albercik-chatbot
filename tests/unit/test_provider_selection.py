"""T010 — unit tests for LLM-provider selection and safe startup logging
at the composition boundary (feature 002-add-ollama-provider,
research.md §5, §8; spec FR-002, FR-018/SC-007). `create_app()` is the
ONLY place `LLM_PROVIDER` is branched on — these tests exercise that
construction directly (never through a fake), which is safe: both
`AnthropicLLMProvider.__init__`/`OllamaLLMProvider.__init__` only build a
client object — no I/O, no real network call, mirroring
`test_anthropic_provider_retries.py::test_configured_timeout_is_passed_
to_the_anthropic_client`'s existing precedent for constructing a real
provider object in a test.

`embedding_provider=` is always overridden with a fake, so no test here
loads the real `sentence-transformers` model (Design Constraint 2,
unchanged) — only the LLM-provider-selection branch is under test.
"""

import logging

from shiruno.config import get_settings
from shiruno.main import create_app
from shiruno.providers.llm.anthropic_provider import AnthropicLLMProvider
from shiruno.providers.llm.ollama_provider import OllamaLLMProvider
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider
from tests.fakes.fake_llm_provider import FakeLLMProvider


def test_ollama_provider_is_selected_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    get_settings.cache_clear()

    app = create_app(embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    assert isinstance(app.state.llm_provider, OllamaLLMProvider)


def test_ollama_provider_is_selected_when_explicitly_configured(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    app = create_app(embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    assert isinstance(app.state.llm_provider, OllamaLLMProvider)


def test_anthropic_provider_is_selected_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()

    app = create_app(embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    assert isinstance(app.state.llm_provider, AnthropicLLMProvider)


def test_an_explicitly_injected_provider_bypasses_selection(monkeypatch) -> None:
    """Design Constraint 2, unchanged: passing llm_provider= (as every
    other test in the suite already does via conftest.py's `test_app`
    fixture) must still bypass LLM_PROVIDER-based construction entirely,
    regardless of what LLM_PROVIDER is set to."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    fake = FakeLLMProvider()
    app = create_app(llm_provider=fake, embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    assert app.state.llm_provider is fake


def test_startup_log_names_ollama_provider_and_model_but_never_secrets_or_url(
    caplog, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-super-secret-value")
    get_settings.cache_clear()

    with caplog.at_level(logging.INFO):
        create_app(embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()

    messages = " ".join(r.message for r in caplog.records)
    assert "ollama" in messages
    assert "qwen3:4b" in messages
    assert "11434" not in messages
    assert "sk-ant-super-secret-value" not in messages


def test_startup_log_names_anthropic_provider_and_model(caplog, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    get_settings.cache_clear()

    with caplog.at_level(logging.INFO):
        create_app(embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()

    messages = " ".join(r.message for r in caplog.records)
    assert "anthropic" in messages
    assert "claude-sonnet-4-5" in messages


def test_app_state_carries_provider_and_model_name_for_usage_accounting(monkeypatch) -> None:
    """Feature 002-add-ollama-provider, T012's dependency: chat.py needs a
    plain `provider_name`/`model_name` string pair for usage accounting,
    sourced once here — never re-derived or branched-on downstream."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    get_settings.cache_clear()

    app = create_app(embedding_provider=FakeEmbeddingProvider())

    get_settings.cache_clear()
    assert app.state.llm_provider_name == "ollama"
    assert app.state.llm_model_name == "qwen3:4b"
