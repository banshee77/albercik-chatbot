"""AnthropicLLMProvider — the only layer in the codebase that retries a
provider call (Design Constraint 1, tasks.md).

Bounded per research.md §7: at most `max_retries` retries (so
`max_retries + 1` attempts total), exponential backoff, no retry on a 4xx
(non-retryable/client) error. Returns exactly one `LLMResult` or raises
exactly one `LLMProviderError` to its caller — `application/ask_question.py`
MUST NOT wrap this in a further retry loop.

Feature 004-rag-answerability-and-ollama-performance: the request now
carries `output_config={"format": {"type": "json_schema", "schema":
ANSWERABILITY_JSON_SCHEMA}}` — Anthropic's native, stable structured-
outputs parameter (research.md §4), not forced tool-use. The response's
text content is still a plain `TextBlock`, now constrained to a JSON
string this provider parses for `supported`/`answer` — the same shared
schema and parsing shape `OllamaLLMProvider` uses. A response that fails
to parse, is missing a required key, or has the wrong key type is a
provider/protocol failure — caught here and raised as `LLMProviderError`
(mapping to the existing `unavailable` outcome), never returned as
`LLMResult(supported=False, ...)` (research.md §5, FR-008).
"""

import json
import time
from typing import Protocol as TypingProtocol

from anthropic import Anthropic, APIConnectionError, APIStatusError, APITimeoutError

from albercik_chatbot.infra.logging import get_logger
from albercik_chatbot.providers.llm.protocol import (
    ANSWERABILITY_JSON_SCHEMA,
    LLMProviderError,
    LLMResult,
)

logger = get_logger(__name__)

_BACKOFF_SECONDS = [0.5, 1.0]


class _MessagesLike(TypingProtocol):
    def create(self, **kwargs: object) -> object: ...


class _AnthropicClientLike(TypingProtocol):
    """The minimal shape this provider needs from an Anthropic client —
    lets tests inject a fake transport (T018) without a real API key or
    network access."""

    @property
    def messages(self) -> _MessagesLike: ...


class AnthropicLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_retries: int,
        timeout_seconds: float = 20.0,
        client: _AnthropicClientLike | None = None,
    ) -> None:
        # `timeout_seconds` bounds each individual attempt inside the
        # retry loop below (tasks.md T067) — a public request can never
        # hang indefinitely on a stalled provider connection. A timeout is
        # just another transient failure to the loop below (caught as
        # `APITimeoutError`), retried like any other, bounded the same way.
        self._client = (
            client if client is not None else Anthropic(api_key=api_key, timeout=timeout_seconds)
        )
        self._model = model
        self._max_retries = max_retries

    def complete(self, *, system_prompt: str, user_message: str, max_tokens: int) -> LLMResult:
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    # Structured answerability contract (research.md §4) —
                    # the same shared schema OllamaLLMProvider uses, via
                    # Anthropic's own native structured-outputs parameter.
                    # No forced tool-use.
                    output_config={
                        "format": {"type": "json_schema", "schema": ANSWERABILITY_JSON_SCHEMA}
                    },
                )
            except APIStatusError as exc:
                if 400 <= exc.status_code < 500:
                    # Non-retryable: bad request, auth failure, exhausted
                    # billing balance, etc. Logged server-side only — the
                    # client only ever sees the generic `unavailable`
                    # outcome (FR-050); `str(exc)` is Anthropic's own
                    # error text, safe to log (never echoes back our API
                    # key/headers/prompt content).
                    logger.warning(
                        "Anthropic request rejected (status=%s): %s", exc.status_code, exc
                    )
                    raise LLMProviderError(
                        f"Anthropic request rejected (status {exc.status_code})"
                    ) from exc
                last_error = exc
            except (APIConnectionError, APITimeoutError) as exc:
                last_error = exc
            else:
                latency_ms = int((time.monotonic() - start) * 1000)
                content = getattr(response, "content", [])
                text = "".join(
                    block.text for block in content if getattr(block, "type", None) == "text"
                )
                try:
                    structured = json.loads(text)
                    answer = structured["answer"]
                    supported = structured["supported"]
                    if not isinstance(answer, str) or not isinstance(supported, bool):
                        raise TypeError("supported/answer field has the wrong type")
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    # Schema-level failure: a provider/protocol failure,
                    # never a "no evidence" answerability decision
                    # (research.md §5, FR-008). Deliberately never returns
                    # `LLMResult(supported=False, ...)` here.
                    logger.warning(
                        "Anthropic returned a structured answerability response that failed to "
                        "parse or validate: %s",
                        exc,
                    )
                    raise LLMProviderError(
                        "Anthropic returned a malformed structured answerability response"
                    ) from exc
                usage = getattr(response, "usage", None)
                return LLMResult(
                    answer=answer,
                    supported=supported,
                    model=getattr(response, "model", self._model),
                    input_tokens=getattr(usage, "input_tokens", None) if usage else None,
                    output_tokens=getattr(usage, "output_tokens", None) if usage else None,
                    latency_ms=latency_ms,
                )

            if attempt < self._max_retries:
                time.sleep(_BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)])

        logger.warning(
            "Anthropic provider failed after %d attempt(s), last error: %s: %s",
            self._max_retries + 1,
            type(last_error).__name__,
            last_error,
        )
        raise LLMProviderError("Anthropic provider failed after bounded retries") from last_error
