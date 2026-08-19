"""LLMProvider Protocol (Principle V).

Core RAG logic (`domain/`, `application/`) depends only on this Protocol —
never on the Anthropic SDK or any other provider-specific type. The
constitution and research.md §7 place bounded-retry responsibility inside
the concrete implementation (see `anthropic_provider.py`): a `Protocol`
method call here returns exactly one outcome — a successful `LLMResult` or
a raised `LLMProviderError` — never a signal that invites the caller to
retry (Design Constraint 1, tasks.md).

Feature 004-rag-answerability-and-ollama-performance extends `LLMResult`
with an explicit `supported` answerability decision produced in the same
call that produces the answer (FR-004), via `ANSWERABILITY_JSON_SCHEMA` —
one shared, provider-independent contract (FR-009) both concrete providers
adapt to their own native structured-output mechanism. A structured
response that fails to parse or validate against this schema is a
provider/protocol failure, not an answerability decision: it MUST be
raised as `LLMProviderError`, never returned as a `LLMResult` with
`supported=False` (research.md §5, FR-008).
"""

from dataclasses import dataclass
from typing import Protocol

ANSWERABILITY_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "answer": {"type": "string"},
    },
    "required": ["supported", "answer"],
}


class LLMProviderError(Exception):
    """Raised after the provider implementation's own bounded-retry policy
    is exhausted, on a non-retryable failure, or when the model's
    structured answerability response is missing, malformed, or fails
    schema validation (research.md §5). Callers MUST NOT retry again on
    catching this."""


@dataclass(frozen=True)
class LLMResult:
    answer: str
    supported: bool
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    provider_metrics: dict[str, int] | None = None


class LLMProvider(Protocol):
    def complete(self, *, system_prompt: str, user_message: str, max_tokens: int) -> LLMResult:
        """Returns a single completion with an explicit `supported`
        answerability decision. Raises `LLMProviderError` on failure after
        any internal retries are exhausted, or when the structured
        answerability response cannot be parsed/validated — never
        partially succeeds and never signals "retry me" to the caller."""
        ...
