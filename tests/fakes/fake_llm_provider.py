"""Deterministic in-memory LLMProvider test double (research.md §8).

No network, no sleep, no retry loop of its own — `complete()` either
returns its configured response or raises its configured error, exactly
once per call. Tests that need to prove `ask_question.py` doesn't add a
retry loop on top of the real provider's (Design Constraint 1) configure
`error` and assert on `call_count`.
"""

from albercik_chatbot.providers.llm.protocol import LLMResult


class FakeLLMProvider:
    def __init__(
        self,
        *,
        response: LLMResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or LLMResult(
            text="To jest odpowiedź testowa.",
            model="fake-llm",
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
        )
        self.error = error
        self.calls: list[dict[str, object]] = []

    def complete(self, *, system_prompt: str, user_message: str, max_tokens: int) -> LLMResult:
        self.calls.append(
            {"system_prompt": system_prompt, "user_message": user_message, "max_tokens": max_tokens}
        )
        if self.error is not None:
            raise self.error
        return self.response

    @property
    def call_count(self) -> int:
        return len(self.calls)
