"""T018 — proves AnthropicLLMProvider is the sole retry layer (Design
Constraint 1, tasks.md): bounded to `max_retries + 1` total attempts, and
returns exactly one outcome (success or LLMProviderError) to its caller.
"""

from unittest.mock import patch

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from albercik_chatbot.providers.llm.anthropic_provider import AnthropicLLMProvider
from albercik_chatbot.providers.llm.protocol import LLMProviderError

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeResponse:
    def __init__(self, text: str = "ok") -> None:
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
        self.messages = self  # mimics client.messages.create(...)

    def create(self, **_kwargs: object) -> _FakeResponse:
        self.calls += 1
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

    assert result.text == "ok"
    assert transport.calls == 3  # 2 failures + 1 success = max_retries + 1


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
