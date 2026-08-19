"""T018 — proves AnthropicLLMProvider is the sole retry layer (Design
Constraint 1, tasks.md): bounded to `max_retries + 1` total attempts, and
returns exactly one outcome (success or LLMProviderError) to its caller.
"""

import json
import logging
from unittest.mock import patch

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from albercik_chatbot.providers.llm.anthropic_provider import AnthropicLLMProvider
from albercik_chatbot.providers.llm.protocol import ANSWERABILITY_JSON_SCHEMA, LLMProviderError

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def _structured_content(*, answer: str = "ok", supported: bool = True) -> str:
    """The JSON string a structured-output response's text content holds
    (feature 004-rag-answerability-and-ollama-performance) — same shape
    `OllamaLLMProvider` parses from `message.content`."""
    return json.dumps({"supported": supported, "answer": answer})


class _FakeResponse:
    def __init__(self, text: str = _structured_content()) -> None:
        self.content = [_FakeMessage(text)]
        self.model = "claude-fake"
        self.usage = _FakeUsage(10, 5)


class _FailNTimesThenSucceed:
    """Fake transport: raises a retryable connection error `fail_count`
    times, then returns a successful response. Records every call so the
    test can assert on total attempts."""

    def __init__(self, fail_count: int) -> None:
        self.fail_count = fail_count
        self.calls = 0
        self.last_kwargs: dict[str, object] = {}
        self.messages = self  # mimics client.messages.create(...)

    def create(self, **kwargs: object) -> _FakeResponse:
        self.calls += 1
        self.last_kwargs = kwargs
        if self.calls <= self.fail_count:
            raise APIConnectionError(request=_REQUEST)
        return _FakeResponse()


class _AlwaysFailTransient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = self

    def create(self, **_kwargs: object) -> _FakeResponse:
        self.calls += 1
        raise APIConnectionError(request=_REQUEST)


class _AlwaysFailTimeout:
    """A stalled/timed-out provider connection (T067) — treated as a
    transient, retryable failure exactly like a connection error, bounded
    by the same max_retries policy; never hangs the caller indefinitely."""

    def __init__(self) -> None:
        self.calls = 0
        self.messages = self

    def create(self, **_kwargs: object) -> _FakeResponse:
        self.calls += 1
        raise APITimeoutError(request=_REQUEST)


class _AlwaysFail4xx:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = self

    def create(self, **_kwargs: object) -> _FakeResponse:
        self.calls += 1
        response = httpx.Response(400, request=_REQUEST)
        raise APIStatusError("bad request", response=response, body=None)


def test_succeeds_after_transient_failures_within_budget() -> None:
    transport = _FailNTimesThenSucceed(fail_count=2)
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    result = provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert result.answer == "ok"
    assert result.supported is True
    assert transport.calls == 3  # 2 failures + 1 success = max_retries + 1


def test_output_config_json_schema_is_sent_with_answerability_schema() -> None:
    transport = _FailNTimesThenSucceed(fail_count=0)
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.last_kwargs["output_config"] == {
        "format": {"type": "json_schema", "schema": ANSWERABILITY_JSON_SCHEMA}
    }


class _FixedContentTransport:
    """Fake transport returning one fixed text content, no retries needed —
    used where the test only cares about how `complete()` parses a
    specific content string."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls = 0
        self.messages = self

    def create(self, **_kwargs: object) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(text=self._content)


def test_successful_generation_with_supported_false() -> None:
    transport = _FixedContentTransport(_structured_content(answer="", supported=False))
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    result = provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert result.supported is False


def test_non_json_text_content_raises_provider_error_not_retried() -> None:
    transport = _FixedContentTransport("po prostu zwykły tekst, nie JSON")
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.calls == 1


def test_structured_content_missing_supported_key_raises_provider_error() -> None:
    transport = _FixedContentTransport(json.dumps({"answer": "hi"}))
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.calls == 1


def test_structured_content_wrong_type_raises_provider_error() -> None:
    transport = _FixedContentTransport(json.dumps({"supported": "yes", "answer": "hi"}))
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.calls == 1


def test_bounded_at_max_retries_plus_one_total_attempts() -> None:
    transport = _AlwaysFailTransient()
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    # Exactly max_retries + 1 attempts — proves no additional retry layer
    # anywhere multiplies this count.
    assert transport.calls == 3


def test_no_retry_on_4xx_client_error() -> None:
    transport = _AlwaysFail4xx()
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.calls == 1


def test_raises_exactly_one_outcome_not_a_retry_signal() -> None:
    """The caller (application/ask_question.py) MUST receive a single
    success or a single LLMProviderError — never a partial/retry-me signal
    it could act on by retrying itself."""
    transport = _AlwaysFailTransient()
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=0, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.calls == 1  # max_retries=0 -> exactly one attempt, no retries at all


def test_provider_timeout_is_bounded_and_fails_safely() -> None:
    transport = _AlwaysFailTimeout()
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with pytest.raises(LLMProviderError):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert transport.calls == 3  # bounded, same policy as any other transient failure


def test_configured_timeout_is_passed_to_the_anthropic_client() -> None:
    with patch("albercik_chatbot.providers.llm.anthropic_provider.Anthropic") as mock_client_cls:
        AnthropicLLMProvider(
            api_key="unused", model="claude-fake", max_retries=2, timeout_seconds=7.5
        )

    mock_client_cls.assert_called_once_with(api_key="unused", timeout=7.5)


def test_non_retryable_4xx_failure_is_logged_server_side(caplog) -> None:
    """Previously silent: a real (non-retryable) provider rejection — e.g.
    an exhausted Anthropic billing balance, seen live during manual
    evaluation — produced no log line anywhere, making it undiagnosable
    from the outside (the client only ever sees the generic `unavailable`
    outcome, by design). This must be logged server-side (never exposed to
    the client) so an operator can tell *why* `/chat` is failing."""
    transport = _AlwaysFail4xx()
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMProviderError):
            provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert len(caplog.records) == 1
    assert "400" in caplog.records[0].message


def test_retry_exhausted_failure_is_logged_server_side(caplog) -> None:
    transport = _AlwaysFailTransient()
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMProviderError):
            provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert len(caplog.records) == 1
    assert "APIConnectionError" in caplog.records[0].message


def test_successful_call_logs_nothing(caplog) -> None:
    transport = _FailNTimesThenSucceed(fail_count=0)
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    with caplog.at_level(logging.WARNING):
        provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert caplog.records == []


def test_constructor_has_no_temperature_or_seed_parameter() -> None:
    """`OLLAMA_TEMPERATURE`/`OLLAMA_SEED` (research.md §14) are Ollama-only
    provider configuration — `AnthropicLLMProvider.__init__` must not even
    accept them, structurally proving no code path can thread either value
    into an Anthropic call."""
    transport = _FailNTimesThenSucceed(fail_count=0)
    with pytest.raises(TypeError):
        AnthropicLLMProvider(
            api_key="unused",
            model="claude-fake",
            max_retries=2,
            client=transport,
            temperature=0.0,  # type: ignore[call-arg]
        )
    with pytest.raises(TypeError):
        AnthropicLLMProvider(
            api_key="unused",
            model="claude-fake",
            max_retries=2,
            client=transport,
            seed=42,  # type: ignore[call-arg]
        )


def test_request_body_never_carries_temperature_or_seed() -> None:
    """Even with the reproducibility-experiment settings holding their
    Ollama defaults (`OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`), the
    Anthropic `messages.create(...)` call this provider makes never gains a
    `temperature`/`seed` kwarg — behavior is unaffected regardless of those
    settings' values, since this provider never reads them at all."""
    transport = _FailNTimesThenSucceed(fail_count=0)
    provider = AnthropicLLMProvider(
        api_key="unused", model="claude-fake", max_retries=2, client=transport
    )

    provider.complete(system_prompt="sys", user_message="hi", max_tokens=100)

    assert "temperature" not in transport.last_kwargs
    assert "seed" not in transport.last_kwargs
