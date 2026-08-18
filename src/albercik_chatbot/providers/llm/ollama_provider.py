"""OllamaLLMProvider — second `LLMProvider` implementation (feature
002-add-ollama-provider), calling a locally-hosted Ollama instance's HTTP
API directly via `httpx` (already a project dependency) — no Ollama SDK
(research.md §1).

Like `AnthropicLLMProvider`, this owns its own bounded retry loop (Design
Constraint 1, tasks.md): no other layer retries a provider call. It reuses
the existing `PROVIDER_MAX_RETRIES` setting rather than introducing a
separate Ollama-specific retry-count knob (research.md §3) — only the
timeout is independently configurable (`OLLAMA_TIMEOUT_SECONDS`), since
local CPU-hosted inference is expected to be slower than the hosted
Anthropic API.

Every failure mode — connection refused, timeout, a missing/unpulled
model, a malformed response body — is caught here and re-raised as the
existing provider-level `LLMProviderError` abstraction; no Ollama-specific
exception, response body, or internal URL ever escapes this module
(`application/ask_question.py` only ever sees `LLMProviderError`, exactly
as it already does for Anthropic).
"""

import time

import httpx

from albercik_chatbot.infra.logging import get_logger
from albercik_chatbot.providers.llm.protocol import LLMProviderError, LLMResult

logger = get_logger(__name__)

_BACKOFF_SECONDS = [0.5, 1.0]


class OllamaLLMProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        max_retries: int,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = (
            client
            if client is not None
            else httpx.Client(base_url=base_url, timeout=timeout_seconds)
        )
        self._model = model
        self._max_retries = max_retries

    def complete(self, *, system_prompt: str, user_message: str, max_tokens: int) -> LLMResult:
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                response = self._client.post(
                    "/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        "stream": False,
                        # Server-controlled output cap (Principle X) — comes
                        # from the `max_tokens` parameter this Protocol
                        # method already receives, never from any
                        # Ollama-specific or client-supplied value.
                        "options": {"num_predict": max_tokens},
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if 400 <= status_code < 500:
                    # Non-retryable: bad request, or the configured model
                    # isn't pulled on this Ollama instance (404). Logged
                    # server-side only — deliberately logs only the status
                    # code, never `str(exc)`/`repr(exc)`: httpx's own
                    # `HTTPStatusError` message embeds the full request URL
                    # (`... for url 'http://ollama:11434/api/chat'`), which
                    # would leak the internal Ollama address into logs.
                    logger.warning("Ollama request rejected (status=%s)", status_code)
                    raise LLMProviderError(
                        f"Ollama request rejected (status {status_code})"
                    ) from exc
                last_error = exc
            except httpx.TransportError as exc:
                # Connection refused, DNS failure, read/connect timeout —
                # all transient-shaped, retried like any other.
                last_error = exc
            else:
                latency_ms = int((time.monotonic() - start) * 1000)
                try:
                    body = response.json()
                    text = body["message"]["content"]
                except (ValueError, KeyError, TypeError) as exc:
                    # Malformed response body — not a network-transient
                    # failure, so not retried; fails safely instead of
                    # letting a KeyError/ValueError escape this module.
                    logger.warning("Ollama returned a malformed response: %s", exc)
                    raise LLMProviderError("Ollama returned a malformed response") from exc
                return LLMResult(
                    text=text,
                    model=body.get("model") or self._model,
                    input_tokens=body.get("prompt_eval_count"),
                    output_tokens=body.get("eval_count"),
                    latency_ms=latency_ms,
                )

            if attempt < self._max_retries:
                time.sleep(_BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)])

        logger.warning(
            "Ollama provider failed after %d attempt(s), last error: %s: %s",
            self._max_retries + 1,
            type(last_error).__name__,
            last_error,
        )
        raise LLMProviderError("Ollama provider failed after bounded retries") from last_error
