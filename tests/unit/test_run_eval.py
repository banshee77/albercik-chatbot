"""Unit tests for `scripts/run_eval.py`'s pure-Python summarization logic
(feature 004-rag-answerability-and-ollama-performance, User Story 3) —
latency avg/p50/p95, generation and prompt-eval tokens/sec, load duration,
and the aggregate `_summarize()` step. No HTTP client, no database, no
real Ollama/Anthropic call (spec Testing; Design Constraint 2): these are
plain functions over in-memory data.
"""

from scripts.run_eval import (
    _avg,
    _generation_tokens_per_second,
    _load_duration_ms,
    _percentile,
    _prompt_eval_tokens_per_second,
    _summarize,
)


def test_avg_ignores_none_values() -> None:
    assert _avg([10.0, None, 20.0, None, 30.0]) == 20.0


def test_avg_is_none_when_every_value_is_missing() -> None:
    assert _avg([None, None]) is None


def test_avg_of_empty_list_is_none() -> None:
    assert _avg([]) is None


def test_percentile_p50_and_p95_over_ten_values() -> None:
    values: list[float | None] = [float(v) for v in range(1, 11)]  # 1..10

    assert _percentile(values, 50) == 5.0
    assert _percentile(values, 95) == 10.0


def test_percentile_ignores_none_values() -> None:
    values = [10.0, None, 20.0, None, 30.0]

    assert _percentile(values, 50) == 20.0


def test_percentile_of_empty_or_all_none_is_none() -> None:
    assert _percentile([], 50) is None
    assert _percentile([None, None], 95) is None


def test_percentile_single_value() -> None:
    assert _percentile([42.0], 50) == 42.0
    assert _percentile([42.0], 95) == 42.0


def test_generation_tokens_per_second_uses_eval_duration_ns_when_present() -> None:
    # 100 tokens in 0.5s (500_000_000ns) = 200 tok/s.
    result = _generation_tokens_per_second(
        output_tokens=100,
        provider_metrics={"eval_duration_ns": 500_000_000},
        latency_ms=9999,  # deliberately different, to prove the precise field wins
    )

    assert result == 200.0


def test_generation_tokens_per_second_falls_back_to_wall_clock_latency() -> None:
    # No provider_metrics at all (e.g. Anthropic) — 50 tokens in 2s = 25 tok/s.
    result = _generation_tokens_per_second(output_tokens=50, provider_metrics=None, latency_ms=2000)

    assert result == 25.0


def test_generation_tokens_per_second_is_none_without_output_tokens() -> None:
    assert (
        _generation_tokens_per_second(output_tokens=None, provider_metrics=None, latency_ms=1000)
        is None
    )
    assert (
        _generation_tokens_per_second(output_tokens=0, provider_metrics=None, latency_ms=1000)
        is None
    )


def test_generation_tokens_per_second_never_divides_by_zero() -> None:
    # Both eval_duration_ns and latency_ms are zero/missing — must not raise.
    assert (
        _generation_tokens_per_second(
            output_tokens=10, provider_metrics={"eval_duration_ns": 0}, latency_ms=0
        )
        is None
    )


def test_generation_tokens_per_second_ignores_malformed_provider_metrics() -> None:
    """A malformed/wrong-typed `eval_duration_ns` (e.g. a string, from a
    corrupted or future-incompatible `usage_records` row) must never raise
    — it's simply treated as absent, falling back to wall-clock latency.
    Malformed telemetry must never affect the eval report's ability to run,
    let alone the chatbot's answerability behavior (which this module has
    no access to at all)."""
    result = _generation_tokens_per_second(
        output_tokens=10, provider_metrics={"eval_duration_ns": "not-a-number"}, latency_ms=1000
    )

    assert result == 10.0  # fell back to latency_ms


def test_prompt_eval_tokens_per_second_uses_prompt_eval_duration_ns() -> None:
    # 40 tokens in 0.2s (200_000_000ns) = 200 tok/s.
    result = _prompt_eval_tokens_per_second(
        input_tokens=40, provider_metrics={"prompt_eval_duration_ns": 200_000_000}
    )

    assert result == 200.0


def test_prompt_eval_tokens_per_second_has_no_fallback() -> None:
    """Unlike generation tokens/sec, there is no wall-clock fallback —
    Anthropic exposes no equivalent duration at all (research.md §10)."""
    assert _prompt_eval_tokens_per_second(input_tokens=40, provider_metrics=None) is None
    assert _prompt_eval_tokens_per_second(input_tokens=None, provider_metrics={}) is None


def test_prompt_eval_tokens_per_second_never_divides_by_zero() -> None:
    assert (
        _prompt_eval_tokens_per_second(
            input_tokens=40, provider_metrics={"prompt_eval_duration_ns": 0}
        )
        is None
    )


def test_load_duration_ms_converts_from_native_nanoseconds() -> None:
    assert _load_duration_ms({"load_duration_ns": 250_000_000}) == 250.0


def test_load_duration_ms_is_none_when_absent_or_malformed() -> None:
    assert _load_duration_ms(None) is None
    assert _load_duration_ms({}) is None
    assert _load_duration_ms({"load_duration_ns": "oops"}) is None


def _result(
    *,
    expected_outcome: str,
    actual_outcome: str,
    latency_ms: int = 100,
    output_tokens: int | None = None,
    tokens_per_second: float | None = None,
    prompt_eval_tokens_per_second: float | None = None,
    load_duration_ms: float | None = None,
) -> dict:
    return {
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "passed": expected_outcome == actual_outcome,
        "latency_ms": latency_ms,
        "output_tokens": output_tokens,
        "tokens_per_second": tokens_per_second,
        "prompt_eval_tokens_per_second": prompt_eval_tokens_per_second,
        "load_duration_ms": load_duration_ms,
    }


def test_summarize_computes_existing_accuracy_metrics_unchanged() -> None:
    results = [
        _result(expected_outcome="grounded", actual_outcome="grounded"),
        _result(expected_outcome="grounded", actual_outcome="grounded"),
        _result(expected_outcome="insufficient_information", actual_outcome="grounded"),
        _result(
            expected_outcome="insufficient_information", actual_outcome="insufficient_information"
        ),
        _result(expected_outcome="out_of_scope", actual_outcome="out_of_scope"),
    ]

    summary = _summarize(results)

    assert summary["total"] == 5
    assert summary["passed"] == 4
    assert summary["grounded_accuracy"] == 1.0
    assert summary["insufficient_information_rejection_rate"] == 0.5
    assert summary["out_of_scope_accuracy"] == 1.0
    assert summary["false_grounded_count"] == 1
    assert summary["false_grounded_rate"] == 0.5


def test_summarize_adds_latency_percentiles() -> None:
    results = [
        _result(expected_outcome="grounded", actual_outcome="grounded", latency_ms=ms)
        for ms in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000)
    ]

    summary = _summarize(results)

    assert summary["latency_avg_ms"] == 550.0
    assert summary["latency_p50_ms"] == 500.0
    assert summary["latency_p95_ms"] == 1000.0


def test_summarize_adds_token_and_throughput_averages() -> None:
    results = [
        _result(
            expected_outcome="grounded",
            actual_outcome="grounded",
            output_tokens=100,
            tokens_per_second=50.0,
            prompt_eval_tokens_per_second=200.0,
            load_duration_ms=10.0,
        ),
        _result(
            expected_outcome="grounded",
            actual_outcome="grounded",
            output_tokens=200,
            tokens_per_second=100.0,
            prompt_eval_tokens_per_second=None,  # e.g. Anthropic row
            load_duration_ms=None,
        ),
    ]

    summary = _summarize(results)

    assert summary["avg_output_tokens"] == 150.0
    assert summary["avg_tokens_per_second"] == 75.0
    # Only the non-None Ollama-only figures are averaged.
    assert summary["avg_prompt_eval_tokens_per_second"] == 200.0
    assert summary["avg_load_duration_ms"] == 10.0


def test_summarize_performance_fields_are_none_when_no_data_available() -> None:
    """All-Anthropic run (or a run against a backend that reports none of
    this): every new aggregate field must be `None`, never a fabricated
    0.0 or an exception (FR-019)."""
    results = [_result(expected_outcome="grounded", actual_outcome="grounded")]

    summary = _summarize(results)

    assert summary["avg_output_tokens"] is None
    assert summary["avg_tokens_per_second"] is None
    assert summary["avg_prompt_eval_tokens_per_second"] is None
    assert summary["avg_load_duration_ms"] is None
