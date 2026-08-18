"""LLMProvider Protocol (Principle V).

Core RAG logic (`domain/`, `application/`) depends only on this Protocol —
never on the Anthropic SDK or any other provider-specific type. The
constitution and research.md §7 place bounded-retry responsibility inside
the concrete implementation (see `anthropic_provider.py`): a `Protocol`
method call here returns exactly one outcome — a successful `LLMResult` or
a raised `LLMProviderError` — never a signal that invites the caller to
retry (Design Constraint 1, tasks.md).
"""

from dataclasses import dataclass
from typing import Protocol


class LLMProviderError(Exception):
    """Raised after the provider implementation's own bounded-retry policy
    is exhausted (or on a non-retryable failure). Callers MUST NOT retry
    again on catching this."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class LLMProvider(Protocol):
    def complete(self, *, system_prompt: str, user_message: str, max_tokens: int) -> LLMResult:
        """Returns a single completion. Raises `LLMProviderError` on
        failure after any internal retries are exhausted — never partially
        succeeds and never signals "retry me" to the caller."""
        ...
