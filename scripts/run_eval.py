"""Runs `eval/questions.jsonl` against a live Albercik Chatbot instance and
reports pass/fail plus the metrics `eval/README.md` recommends collecting
(grounded accuracy, insufficient-information rejection rate, out-of-scope
accuracy, false-grounded rate).

Dev/eval tool only — not part of the application or its automated test
suite (which never makes a real Anthropic call, Design Constraint 2).
This script deliberately does.

Usage:
    uv run python scripts/run_eval.py [--base-url http://localhost:8000]

Prerequisites:
- The `app` + `db` containers (or an equivalent local run) up, with a
  real ANTHROPIC_API_KEY configured — otherwise every `grounded`-expected
  question resolves to `unavailable` instead (LLM_ENABLED/budget/provider
  behavior is unaffected by this script; it exercises the real pipeline
  as a public caller would).
- `knowledge/*.txt` and `eval/questions.jsonl` present.

Each run resets the knowledge base (deletes every existing document via
the admin API, then re-uploads `knowledge/*.txt` fresh) so results are
reproducible regardless of what was uploaded before. Uses a fixed,
eval-only administrator account (`create-admin`, idempotent — an
"already exists" failure is expected and ignored on repeat runs).
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
QUESTIONS_FILE = REPO_ROOT / "eval" / "questions.jsonl"

# Dev/eval-only account, never used for anything else. Not a real secret —
# hardcoded on purpose so repeat runs can log in without re-provisioning.
_EVAL_ADMIN_USERNAME = "eval-runner"
_EVAL_ADMIN_PASSWORD = "eval-runner-not-a-production-password-1"  # noqa: S105


def _ensure_eval_admin() -> None:
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "albercik_chatbot.cli",
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


def _load_questions() -> list[dict]:
    with QUESTIONS_FILE.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _ask(client: httpx.Client, question: str) -> tuple[httpx.Response, int]:
    start = time.monotonic()
    response = client.post("/api/v1/chat", json={"question": question})
    return response, int((time.monotonic() - start) * 1000)


def _run_questions(client: httpx.Client, questions: list[dict]) -> list[dict]:
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
    }


def _print_report(results: list[dict], summary: dict) -> None:
    print(f"\n{'ID':<4}{'Expected':<24}{'Actual':<24}{'':<6}{'ms':<7}Question")
    for r in results:
        mark = "OK" if r["passed"] else "FAIL"
        print(
            f"{r['id']:<4}{r['expected_outcome']:<24}{r['actual_outcome']:<24}{mark:<6}"
            f"{r['latency_ms']:<7}{r['question'][:60]}"
        )

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Don't delete/re-upload the knowledge base — use whatever is already loaded.",
    )
    args = parser.parse_args()

    _ensure_eval_admin()

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        token = _login(client)
        if not args.skip_reset:
            _reset_knowledge_base(client, token)
        questions = _load_questions()
        results = _run_questions(client, questions)

    summary = _summarize(results)
    _print_report(results, summary)

    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
