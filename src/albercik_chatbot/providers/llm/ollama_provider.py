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

Feature 004-rag-answerability-and-ollama-performance: the request now
carries `"format": ANSWERABILITY_JSON_SCHEMA` (Ollama's own structured-
output mechanism, research.md §3), so `message.content` is a JSON string
this provider parses for `supported`/`answer` instead of treating it as
raw answer text. A structured response that fails to parse, is missing a
required key, or has the wrong key type is a provider/protocol failure —
it is caught here and raised as `LLMProviderError` (mapping to the
existing `unavailable` outcome), exactly like any other malformed response
body; it is never returned as `LLMResult(supported=False, ...)`
(research.md §5, FR-008).

User Story 3 adds two more Ollama-only, server-config-owned behaviors,
neither of which is part of the shared `LLMProvider` Protocol (FR-012,
FR-013):
  - `think` (constructor-only, from `Settings.OLLAMA_THINK` via `main.py`)
    is forwarded as the top-level `think` request field, controlling
    Qwen3's extended-reasoning step. `complete()` itself takes no `think`
    argument — a public request can never reach this setting.
  - `provider_metrics` on the returned `LLMResult` is populated verbatim
    (native nanoseconds, `*_duration_ns` key names — no unit conversion)
    from Ollama's own `total_duration`/`load_duration`/
    `prompt_eval_duration`/`eval_duration` response fields, when present.
    `message.thinking` (populated by Ollama alongside `content` when
    `think=true`) is never read anywhere in this module, in any form —
    not as the answer, not inside `provider_metrics` (FR-016, research.md
    §7).

Reproducibility experiment (research.md §14) adds two more, same pattern:
  - `temperature`/`seed` (constructor-only, from `Settings.OLLAMA_TEMPERATURE`
    / `Settings.OLLAMA_SEED` via `main.py`) are forwarded inside the request
    `options` object, alongside `num_predict`. Neither is a `complete()`
    parameter — a public request can never override them. They exist purely
    to make repeated identical calls to this provider reproducible for eval
    and prompt-calibration purposes; they have no bearing on the
    answerability contract itself.
"""

import json
import time

import httpx

from albercik_chatbot.infra.logging import get_logger
from albercik_chatbot.providers.llm.protocol import (
    ANSWERABILITY_JSON_SCHEMA,
    LLMProviderError,
    LLMResult,
)

logger = get_logger(__name__)

_BACKOFF_SECONDS = [0.5, 1.0]

# Maps Ollama's own native (nanosecond) response field names to the
# `*_duration_ns` keys this feature stores them under (research.md §8) —
# the rename makes the unit explicit; the values themselves are copied
# verbatim, with no conversion.
_DURATION_FIELD_NAMES = {
    "total_duration": "total_duration_ns",
    "load_duration": "load_duration_ns",
    "prompt_eval_duration": "prompt_eval_duration_ns",
    "eval_duration": "eval_duration_ns",
}


def _extract_provider_metrics(body: dict) -> dict[str, int] | None:
    """Best-effort, defensive extraction — a missing or malformed duration
    field (wrong type) is simply omitted, never raised: telemetry is
    opaque, optional usage-accounting data (research.md §8), and MUST NOT
    be able to affect the answerability decision this function has no
    involvement in (this function never touches `supported`/`answer`)."""
    metrics = {
        renamed: value
        for field_name, renamed in _DURATION_FIELD_NAMES.items()
        if isinstance(value := body.get(field_name), int) and not isinstance(value, bool)
    }
    return metrics or None


class OllamaLLMProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        max_retries: int,
        timeout_seconds: float,
        think: bool,
        temperature: float,
        seed: int,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = (
            client
            if client is not None
            else httpx.Client(base_url=base_url, timeout=timeout_seconds)
        )
        self._model = model
        self._max_retries = max_retries
        # Fixed at construction time, before any request exists — nothing
        # about `ChatRequest`/the request path can reach any of these three
        # (FR-013; research.md §14).
        self._think = think
        self._temperature = temperature
        self._seed = seed

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
                        "options": {
                            "num_predict": max_tokens,
                            # Server-only, constructor-fixed (research.md
                            # §14) — makes repeated identical calls
                            # reproducible; never influenced by request
                            # content.
                            "temperature": self._temperature,
                            "seed": self._seed,
                        },
                        # Structured answerability contract (research.md
                        # §2, §3) — shared verbatim with AnthropicLLMProvider,
                        # never Ollama-specific.
                        "format": ANSWERABILITY_JSON_SCHEMA,
                        # Server-only, constructor-fixed (research.md §6,
                        # FR-012/FR-013) — never influenced by request
                        # content.
                        "think": self._think,
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
                    content = body["message"]["content"]
                except (ValueError, KeyError, TypeError) as exc:
                    # Malformed envelope — not a network-transient failure,
                    # so not retried; fails safely instead of letting a
                    # KeyError/ValueError escape this module.
                    logger.warning("Ollama returned a malformed response: %s", exc)
                    raise LLMProviderError("Ollama returned a malformed response") from exc
                try:
                    structured = json.loads(content)
                    answer = structured["answer"]
                    supported = structured["supported"]
                    if not isinstance(answer, str) or not isinstance(supported, bool):
                        raise TypeError("supported/answer field has the wrong type")
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    # Schema-level failure: the envelope is fine, but
                    # `message.content` isn't the structured
                    # `{"supported": bool, "answer": str}` JSON the `format`
                    # request field constrained it to be — a provider/
                    # protocol failure, never a "no evidence" answerability
                    # decision (research.md §5, FR-008). Deliberately never
                    # returns `LLMResult(supported=False, ...)` here.
                    logger.warning(
                        "Ollama returned a structured answerability response that failed to "
                        "parse or validate: %s",
                        exc,
                    )
                    raise LLMProviderError(
                        "Ollama returned a malformed structured answerability response"
                    ) from exc
                return LLMResult(
                    answer=answer,
                    supported=supported,
                    model=body.get("model") or self._model,
                    input_tokens=body.get("prompt_eval_count"),
                    output_tokens=body.get("eval_count"),
                    latency_ms=latency_ms,
                    provider_metrics=_extract_provider_metrics(body),
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
