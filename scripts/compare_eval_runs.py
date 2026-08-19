"""Side-by-side comparison of two `scripts/run_eval.py --save-json` reports
(feature 004-rag-answerability-and-ollama-performance, Story 3 / SC-004).

Intended primarily for the `OLLAMA_THINK=true` vs. `OLLAMA_THINK=false`
A/B comparison: run `run_eval.py --save-json` once per configuration
(switching `OLLAMA_THINK` and restarting the `app` container between runs
— this script cannot do that itself, research.md §11), then diff the two
saved reports. Works equally well for any two labeled runs (e.g. the
existing Ollama-vs-Anthropic backend comparison, feature
002-add-ollama-provider) since both inputs are just `run_eval.py`'s own
saved output.

Usage:
    uv run python scripts/compare_eval_runs.py run_a.json run_b.json
"""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _fmt(value: float | None, suffix: str = "") -> str:
    return f"{value:.2f}{suffix}" if value is not None else "n/a"


def _pct(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "n/a"


def _print_comparison(
    label_a: str, summary_a: dict[str, Any], label_b: str, summary_b: dict[str, Any]
) -> None:
    col_a = label_a[:34]
    col_b = label_b[:34]

    def row(title: str, get: Callable[[dict[str, Any]], str]) -> None:
        print(f"{title:<32}{get(summary_a):<36}{get(summary_b)}")

    print("\n=== Eval run comparison ===\n")
    print(f"{'':32}{col_a:<36}{col_b}")
    print("-" * 100)

    row("Pass rate", lambda s: _pct(s["pass_rate"]))
    row(
        "Grounded accuracy",
        lambda s: f"{_pct(s['grounded_accuracy'])} (n={s['grounded_n']})",
    )
    row(
        "Insufficient-info rejection",
        lambda s: f"{_pct(s['insufficient_information_rejection_rate'])} (n={s['insufficient_n']})",
    )
    row(
        "Out-of-scope accuracy",
        lambda s: f"{_pct(s['out_of_scope_accuracy'])} (n={s['out_of_scope_n']})",
    )
    row(
        "False-grounded",
        lambda s: f"{s['false_grounded_count']} ({_pct(s['false_grounded_rate'])})",
    )
    print("-" * 100)
    row("Latency avg (ms)", lambda s: _fmt(s["latency_avg_ms"]))
    row("Latency p50 (ms)", lambda s: _fmt(s["latency_p50_ms"]))
    row("Latency p95 (ms)", lambda s: _fmt(s["latency_p95_ms"]))
    print("-" * 100)
    row("Avg output tokens", lambda s: _fmt(s["avg_output_tokens"]))
    row("Avg generation tokens/sec", lambda s: _fmt(s["avg_tokens_per_second"]))
    row("Avg prompt-eval tokens/sec", lambda s: _fmt(s["avg_prompt_eval_tokens_per_second"]))
    row("Avg load duration (ms)", lambda s: _fmt(s["avg_load_duration_ms"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a", type=Path, help="A --save-json report from scripts/run_eval.py")
    parser.add_argument("run_b", type=Path, help="A second --save-json report to compare against")
    args = parser.parse_args()

    report_a = _load(args.run_a)
    report_b = _load(args.run_b)

    _print_comparison(
        report_a["backend"], report_a["summary"], report_b["backend"], report_b["summary"]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
