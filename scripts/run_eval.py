"""Runs `eval/questions.jsonl` against a live Shiruno (Albertos) instance and
reports pass/fail plus the metrics `eval/README.md` recommends collecting
(grounded accuracy, insufficient-information rejection rate, out-of-scope
accuracy, false-grounded rate, latency percentiles, and — where the active
backend reports it — token throughput and model-load time).

Dev/eval tool only — not part of the application or its automated test
suite (which never makes a real Anthropic call, Design Constraint 2).
This script deliberately does.

Usage:
    uv run python scripts/run_eval.py [--base-url http://localhost:8000]
    uv run python scripts/run_eval.py --save-json /tmp/eval-run.json

Every printed report is labeled with the backend (`LLM_PROVIDER`) and
model that were actually active for that run (research.md §7, feature
002-add-ollama-provider, spec FR-016) — run this script once per backend
(switching `LLM_PROVIDER` and restarting `app` between runs, no question-
set changes) to produce two directly comparable, labeled reports. The same
pattern applies to comparing `OLLAMA_THINK=true` vs. `false` (feature
004-rag-answerability-and-ollama-performance) — see
`scripts/compare_eval_runs.py` for a side-by-side diff of two
`--save-json` outputs.

Prerequisites:
- The `app` + `db` containers (or an equivalent local run) up. If
  `LLM_PROVIDER=anthropic`, a real `ANTHROPIC_API_KEY` must also be
  configured — otherwise every `grounded`-expected question resolves to
  `unavailable` instead. The local Ollama backend (the default) needs no
  API key (LLM_ENABLED/budget/provider behavior is unaffected by this
  script either way; it exercises the real pipeline as a public caller
  would).
- `knowledge/*.txt` and `eval/questions.jsonl` present.
- Direct database access (the same `DATABASE_URL` the target app itself
  uses) to correlate each response's `request_id` back to its
  `usage_records` row for token/telemetry data (research.md §9) — this
  script is a dev/eval tool with the same environment access `main.py`
  has, not a production, unauthenticated-adjacent client.

Each run resets the knowledge base (deletes every existing document via
the admin API, then re-uploads `knowledge/*.txt` fresh) so results are
reproducible regardless of what was uploaded before. Uses a fixed,
eval-only administrator account (`create-admin`, idempotent — an
"already exists" failure is expected and ignored on repeat runs).
"""

import argparse
import json
import math
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from shiruno.config import get_settings
from shiruno.persistence.database import get_session_factory
from shiruno.persistence.models import ProviderKind, UsageRecord

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
QUESTIONS_FILE = REPO_ROOT / "eval" / "questions.jsonl"

# Dev/eval-only account, never used for anything else. Not a real secret —
# hardcoded on purpose so repeat runs can log in without re-provisioning.
_EVAL_ADMIN_USERNAME = "eval-runner"
_EVAL_ADMIN_PASSWORD = "eval-runner-not-a-production-password-1"  # noqa: S105

_NS_PER_SECOND = 1_000_000_000


def _ensure_eval_admin() -> None:
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "shiruno.cli",
            "create-admin",
            "--username",
            _EVAL_ADMIN_USERNAME,
            "--password",
            _EVAL_ADMIN_PASSWORD,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,  # non-zero exit == "already exists", expected on repeat runs
    )


def _login(client: httpx.Client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": _EVAL_ADMIN_USERNAME, "password": _EVAL_ADMIN_PASSWORD},
    )
    response.raise_for_status()
    token: str = response.json()["access_token"]
    return token


def _reset_knowledge_base(client: httpx.Client, token: str) -> None:
    headers = {"authorization": f"Bearer {token}"}

    existing = client.get("/api/v1/documents", headers=headers)
    existing.raise_for_status()
    for doc in existing.json():
        client.delete(f"/api/v1/documents/{doc['id']}", headers=headers)

    for path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        with path.open("rb") as fh:
            response = client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": (path.name, fh, "text/plain")},
            )
        response.raise_for_status()
        status = response.json()["status"]
        if status != "ready":
            print(f"WARNING: {path.name} uploaded with status={status!r}", file=sys.stderr)


def _active_backend_label() -> str:
    """Reads `LLM_PROVIDER` (and the corresponding model name) from the
    same configuration the target app itself is expected to be running
    with (research.md §7) — so two runs of this script, one per backend,
    each print an unambiguous, backend-labeled report (spec FR-016). Never
    prints anything else from `Settings` (no base URLs, no credentials,
    no `OLLAMA_THINK` — that's read separately, deliberately, since it's
    the one thing feature 004's A/B comparison needs surfaced), mirroring
    `main.py`'s own startup log line.
    """
    settings = get_settings()
    model = settings.OLLAMA_MODEL if settings.LLM_PROVIDER == "ollama" else settings.ANTHROPIC_MODEL
    label = f"{settings.LLM_PROVIDER} (model={model})"
    if settings.LLM_PROVIDER == "ollama":
        label += f", think={settings.OLLAMA_THINK}"
    return label


def _load_questions() -> list[dict]:
    with QUESTIONS_FILE.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _ask(client: httpx.Client, question: str) -> tuple[httpx.Response, int]:
    start = time.monotonic()
    response = client.post("/api/v1/chat", json={"question": question})
    return response, int((time.monotonic() - start) * 1000)


def _lookup_llm_usage_row(session: Session, request_id: uuid.UUID) -> UsageRecord | None:
    """Correlates a `/chat` response back to the `usage_records` row
    `_record_usage()` wrote for it (research.md §9) — `request_id` is
    unique per request, and this script only ever cares about the `llm`-
    kind row (never the `embedding`-kind row also written for the same
    request)."""
    return (
        session.query(UsageRecord)
        .filter(
            UsageRecord.request_id == request_id,
            UsageRecord.provider_kind == ProviderKind.llm,
        )
        .one_or_none()
    )


def _generation_tokens_per_second(
    *, output_tokens: int | None, provider_metrics: dict | None, latency_ms: int | None
) -> float | None:
    """`eval_count / (eval_duration_ns / 1e9)` when Ollama's native
    generation-only duration is available (research.md §10); falls back to
    the coarser wall-clock `output_tokens / (latency_ms / 1000)` otherwise
    (includes network/queueing time — a genuine, non-fabricated figure,
    just less precise). `None` — never a fabricated/divide-by-zero value —
    when neither input is usable (FR-019)."""
    if not output_tokens or output_tokens <= 0:
        return None
    eval_duration_ns = (provider_metrics or {}).get("eval_duration_ns")
    if isinstance(eval_duration_ns, int | float) and eval_duration_ns > 0:
        return output_tokens / (eval_duration_ns / _NS_PER_SECOND)
    if latency_ms and latency_ms > 0:
        return output_tokens / (latency_ms / 1000)
    return None


def _prompt_eval_tokens_per_second(
    *, input_tokens: int | None, provider_metrics: dict | None
) -> float | None:
    """`prompt_eval_count / (prompt_eval_duration_ns / 1e9)` — Ollama-only,
    no fallback: no other backend exposes an equivalent duration
    (research.md §10)."""
    if not input_tokens or input_tokens <= 0:
        return None
    prompt_eval_duration_ns = (provider_metrics or {}).get("prompt_eval_duration_ns")
    if isinstance(prompt_eval_duration_ns, int | float) and prompt_eval_duration_ns > 0:
        return input_tokens / (prompt_eval_duration_ns / _NS_PER_SECOND)
    return None


def _load_duration_ms(provider_metrics: dict | None) -> float | None:
    """`load_duration_ns` converted to milliseconds for display only — the
    stored `usage_records` value stays nanoseconds (research.md §10).
    Ollama-only; `None` when absent."""
    load_duration_ns = (provider_metrics or {}).get("load_duration_ns")
    if isinstance(load_duration_ns, int | float):
        return load_duration_ns / 1_000_000
    return None


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _percentile(values: list[float | None], pct: float) -> float | None:
    """Nearest-rank percentile — deterministic, dependency-free, and exact
    enough for a 30-question eval report (not a claim of statistical
    rigor; see spec.md's own MVP-gate framing for SC-002)."""
    present = sorted(v for v in values if v is not None)
    if not present:
        return None
    rank = max(0, min(len(present) - 1, math.ceil(pct / 100 * len(present)) - 1))
    return present[rank]


def _run_questions(client: httpx.Client, questions: list[dict], session: Session) -> list[dict]:
    results = []
    for row in questions:
        response, latency_ms = _ask(client, row["question"])
        if response.status_code == 429:
            # Rate-limit window rolled over mid-run — wait it out, retry once.
            wait_seconds = int(response.headers.get("retry-after", "5")) + 1
            time.sleep(wait_seconds)
            response, latency_ms = _ask(client, row["question"])

        content_type = response.headers.get("content-type", "")
        body = response.json() if content_type.startswith("application/json") else {}
        actual_outcome = body.get("outcome", f"HTTP {response.status_code}")

        input_tokens: int | None = None
        output_tokens: int | None = None
        provider_metrics: dict | None = None
        request_id_raw = body.get("request_id")
        if request_id_raw:
            usage_row = _lookup_llm_usage_row(session, uuid.UUID(request_id_raw))
            if usage_row is not None:
                input_tokens = usage_row.input_tokens
                output_tokens = usage_row.output_tokens
                provider_metrics = usage_row.provider_metrics

        results.append(
            {
                "id": row["id"],
                "question": row["question"],
                "expected_outcome": row["expected_outcome"],
                "actual_outcome": actual_outcome,
                "passed": actual_outcome == row["expected_outcome"],
                "sources": [s.get("label") for s in body.get("sources", [])],
                "answer": body.get("answer", ""),
                "latency_ms": latency_ms,
                "status_code": response.status_code,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "tokens_per_second": _generation_tokens_per_second(
                    output_tokens=output_tokens,
                    provider_metrics=provider_metrics,
                    latency_ms=latency_ms,
                ),
                "prompt_eval_tokens_per_second": _prompt_eval_tokens_per_second(
                    input_tokens=input_tokens, provider_metrics=provider_metrics
                ),
                "load_duration_ms": _load_duration_ms(provider_metrics),
            }
        )
    return results


def _summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(r["passed"] for r in results)

    def rate(expected: str) -> tuple[int, int]:
        subset = [r for r in results if r["expected_outcome"] == expected]
        ok = sum(r["passed"] for r in subset)
        return ok, len(subset)

    grounded_ok, grounded_n = rate("grounded")
    insuff_ok, insuff_n = rate("insufficient_information")
    oos_ok, oos_n = rate("out_of_scope")
    false_grounded = sum(
        1
        for r in results
        if r["expected_outcome"] == "insufficient_information" and r["actual_outcome"] == "grounded"
    )

    latencies = [r["latency_ms"] for r in results]

    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "grounded_accuracy": (grounded_ok / grounded_n) if grounded_n else None,
        "grounded_n": grounded_n,
        "insufficient_information_rejection_rate": (insuff_ok / insuff_n) if insuff_n else None,
        "insufficient_n": insuff_n,
        "out_of_scope_accuracy": (oos_ok / oos_n) if oos_n else None,
        "out_of_scope_n": oos_n,
        "false_grounded_count": false_grounded,
        "false_grounded_rate": (false_grounded / insuff_n) if insuff_n else None,
        "latency_avg_ms": _avg(latencies),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "avg_output_tokens": _avg([r["output_tokens"] for r in results]),
        "avg_tokens_per_second": _avg([r["tokens_per_second"] for r in results]),
        "avg_prompt_eval_tokens_per_second": _avg(
            [r["prompt_eval_tokens_per_second"] for r in results]
        ),
        "avg_load_duration_ms": _avg([r["load_duration_ms"] for r in results]),
    }


def _fmt(value: float | None, suffix: str = "") -> str:
    return f"{value:.2f}{suffix}" if value is not None else "n/a"


def _print_report(results: list[dict], summary: dict, backend_label: str) -> None:
    print(f"\n=== Eval run — backend: {backend_label} ===")
    print(f"\n{'ID':<4}{'Expected':<24}{'Actual':<24}{'':<6}{'ms':<7}Question")
    for r in results:
        mark = "OK" if r["passed"] else "FAIL"
        print(
            f"{r['id']:<4}{r['expected_outcome']:<24}{r['actual_outcome']:<24}{mark:<6}"
            f"{r['latency_ms']:<7}{r['question'][:60]}"
        )
        perf_bits = []
        if r["input_tokens"] is not None:
            perf_bits.append(f"in={r['input_tokens']}")
        if r["output_tokens"] is not None:
            perf_bits.append(f"out={r['output_tokens']}")
        if r["tokens_per_second"] is not None:
            perf_bits.append(f"gen_tok/s={_fmt(r['tokens_per_second'])}")
        if r["prompt_eval_tokens_per_second"] is not None:
            perf_bits.append(f"prompt_tok/s={_fmt(r['prompt_eval_tokens_per_second'])}")
        if r["load_duration_ms"] is not None:
            perf_bits.append(f"load_ms={_fmt(r['load_duration_ms'])}")
        if perf_bits:
            print(f"      {' '.join(perf_bits)}")

    print("\n--- Summary ---")
    print(f"Total: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']:.0%})")
    print(f"Grounded accuracy: {summary['grounded_accuracy']} (n={summary['grounded_n']})")
    print(
        "Insufficient-information rejection rate: "
        f"{summary['insufficient_information_rejection_rate']} (n={summary['insufficient_n']})"
    )
    print(
        f"Out-of-scope accuracy: {summary['out_of_scope_accuracy']} (n={summary['out_of_scope_n']})"
    )
    rate = summary["false_grounded_rate"]
    print(f"False-grounded: {summary['false_grounded_count']} (rate: {rate})")

    print("\n--- Performance ---")
    print(
        f"Latency avg/p50/p95 (ms): {_fmt(summary['latency_avg_ms'])} / "
        f"{_fmt(summary['latency_p50_ms'])} / {_fmt(summary['latency_p95_ms'])}"
    )
    print(f"Avg output tokens: {_fmt(summary['avg_output_tokens'])}")
    print(f"Avg generation tokens/sec: {_fmt(summary['avg_tokens_per_second'])}")
    print(f"Avg prompt-eval tokens/sec: {_fmt(summary['avg_prompt_eval_tokens_per_second'])}")
    print(f"Avg load duration (ms): {_fmt(summary['avg_load_duration_ms'])}")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\n--- Failures ---")
        for r in failed:
            print(
                f"#{r['id']}: expected={r['expected_outcome']} actual={r['actual_outcome']} "
                f"q={r['question']!r}"
            )
            print(f"    answer: {r['answer'][:200]!r}")
            print(f"    sources: {r['sources']}")


def _save_json(path: Path, *, backend_label: str, results: list[dict], summary: dict) -> None:
    path.write_text(
        json.dumps({"backend": backend_label, "results": results, "summary": summary}, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved report to {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Don't delete/re-upload the knowledge base — use whatever is already loaded.",
    )
    parser.add_argument(
        "--save-json",
        type=Path,
        default=None,
        help="Also write the full per-question results + summary to this JSON file "
        "(for scripts/compare_eval_runs.py).",
    )
    args = parser.parse_args()

    _ensure_eval_admin()
    backend_label = _active_backend_label()

    session_factory = get_session_factory()
    session = session_factory()
    try:
        with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
            token = _login(client)
            if not args.skip_reset:
                _reset_knowledge_base(client, token)
            questions = _load_questions()
            results = _run_questions(client, questions, session)
    finally:
        session.close()

    summary = _summarize(results)
    _print_report(results, summary, backend_label)
    if args.save_json:
        _save_json(args.save_json, backend_label=backend_label, results=results, summary=summary)

    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
