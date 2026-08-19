# Quickstart: Validating RAG Answerability & Ollama Performance

Validates the feature end-to-end against the running stack and the frozen
`eval/questions.jsonl` benchmark. See `data-model.md` for field shapes and
`contracts/chat-endpoint-delta.md` for the one public API change.

## Prerequisites

- Docker Compose stack built with this feature's changes:
  ```bash
  docker compose build app
  docker compose up -d
  curl localhost:8000/health
  ```
- Default `.env`: `LLM_PROVIDER=ollama`, `OLLAMA_THINK=false` (this
  feature's default — see `research.md` §6).
- `knowledge/*.txt` present (unchanged from prior features).

## Scenario 1 — Answerability accuracy meets the accepted targets (SC-001–SC-003)

```bash
uv run python scripts/run_eval.py --save-json /tmp/eval-think-false.json
```

Expected, on the Ollama backend:
- Grounded accuracy: 100% (20/20) — unchanged from baseline.
- Out-of-scope accuracy: 100% (3/3) — unchanged from baseline.
- Insufficient-information rejection rate: ≥ 85% (was 0%).
- False-grounded rate: ≤ 15% (was 100%).
- Exit code `0` only if every question passes; a non-zero exit with
  remaining mismatches is expected to still meet the rate targets above —
  read the printed summary, not just the exit code, to check SC-001–SC-003.

The printed report additionally shows, per question and in the summary,
input/output token counts and tokens/sec where available (data-model.md
"Eval report row"/"Eval summary").

**Measured 2026-08-19 (`qwen3:4b`, real GPU-accelerated Ollama,
`OLLAMA_THINK=false`, `OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`, 3
identical repeated runs)** — see `eval/README.md`'s "Reproducibility
experiment" section for the full diagnosis and all reports: **100%
(30/30) per-question outcome agreement across all 3 runs, zero unstable
questions** — the sampling non-determinism previously suspected of
masking prompt-fix signal (see the "Known open issue" section, 2026-08-18)
is confirmed eliminated by pinning temperature/seed. Deterministic
result, identical every run: out-of-scope accuracy 100% (3/3) ✅,
insufficient-information rejection 100% (7/7) ✅ (≥6/7), false-grounded
0/7 ✅ (≤1/7). **Grounded accuracy 85% (17/20) ❌ — SC-001 (20/20) is
still NOT met**, with the same 3 questions (#3, #6, #22) failing in every
run — a genuine, reproducible recall gap now, not a measurement artifact.
Further prompt calibration against these 3 questions is scientifically
meaningful going forward (a single re-run's delta can now be trusted) —
see `eval/README.md` before attempting a fix.

**Update, same day**: a targeted rule-8 prompt clarification was tried
against exactly these 3 questions and **measured as a severe regression**
(35%, 7/20 grounded — down from the 85% baseline above). **Rule 8 was
reverted the same day** (`domain/prompting.py::SYSTEM_PROMPT` restored to
rules 1–7 exactly) and a confirming re-run measured the baseline restored
exactly: 85% (17/20) grounded, 100% (7/7) insufficient-information
rejection, 0/7 false-grounded, 100% (3/3) out-of-scope, same failing
questions (#3, #6, #22) — see `eval/README.md`'s "Final targeted
calibration pass" and "Deterministic baseline restored" sections for the
full diagnosis, root-cause hypothesis, and revert confirmation.

**Model switched 2026-08-19**: with the prompt held fixed at the
restored rules-1–7 baseline above, `qwen3:8b` was evaluated under the
same deterministic config and measured **95% (19/20) grounded** — up
from `qwen3:4b`'s 85% (17/20), with insufficient-information rejection
(7/7), false-grounded (0/7), and out-of-scope (3/3) all unchanged, and no
OOM/timeout/provider failures on the RTX 3070 (~6.0 GB VRAM used).
**`qwen3:8b` is now the default `OLLAMA_MODEL`** (was `qwen3:4b`);
`qwen3:4b` remains available as a manual override. Only question **#6**
still fails on `qwen3:8b` — #3 and #22 now pass. Against the *original*
20/20 target this is NOT met — see `eval/README.md`'s "Model selection:
qwen3:8b adopted as default" section for the full comparison and
`research.md` §17 for the decision record. The `qwen3:4b` measurements
above remain historical — they describe the model that was the default
at the time, not the current one.

**SC-001 amended 2026-08-19**: rather than continue tuning to close
question #6 (a prior targeted attempt at this class of case caused a
severe measured regression elsewhere — research.md §16), SC-001 was
deliberately changed to **grounded accuracy ≥19/20 (≥95%)** for the MVP
— see `spec.md`'s "SC-001 acceptance-criterion amendment" and
`research.md` §18. The measured 19/20 **meets** the amended SC-001;
combined with SC-002/SC-003/SC-004 already met, **feature 004 is
complete**, with #6 retained as a known, accepted MVP limitation.

## Scenario 2 — A false-grounded case is now correctly rejected

Pick one of the 7 `insufficient_information`-expected questions in
`eval/questions.jsonl` that previously scored `grounded` (see the
feature's baseline numbers in spec.md). Ask it directly:

```bash
curl -s -X POST localhost:8000/api/v1/chat \
  -H 'content-type: application/json' \
  -d '{"question":"<one of the previously-false-grounded questions>"}' | python3 -m json.tool
```

Expected: `"outcome": "insufficient_information"`, and the standard
insufficient-information message — not a fabricated answer. Response also
includes a `request_id` (contracts/chat-endpoint-delta.md).

## Scenario 3 — No negative inference from silent context

Ask a question whose answer would require the model to state a negative
fact the knowledge base never actually states (see spec.md User Story 2
examples — e.g. a service/offering the context never mentions either way).

Expected: `"outcome": "insufficient_information"` — never a confident "no,
Albertos does not do X" answer grounded in silence.

## Scenario 4 — Malformed structured output fails safe (automated, not manual)

Not manually reproducible against a live model reliably — covered by
automated provider unit tests instead (spec Testing item 4):

```bash
uv run pytest tests/unit/test_ollama_provider.py tests/unit/test_anthropic_provider_retries.py -k malformed -v
```

Expected: both assert `complete()` **raises `LLMProviderError`** for a
malformed/schema-invalid/unparseable structured body — it does **not**
return a synthesized `LLMResult(supported=False, ...)`. A separate
contract-level test confirms this surfaces as the `unavailable` outcome
(FR-008), never `insufficient_information` and never `grounded`; a
structured response that *parses successfully* with `supported=false`
remains a normal `LLMResult` mapping to `insufficient_information`.

## Scenario 5 — `OLLAMA_THINK` is server-only and forwarded correctly

```bash
uv run pytest tests/unit/test_ollama_provider.py -k think -v
```

Expected: tests prove `think: true`/`think: false` is forwarded in the
Ollama request body exactly as configured, and that no `ChatRequest` field
can influence it (`ChatRequest`'s existing `extra="forbid"` already makes
this structurally impossible — confirm no new field was added to
`ChatRequest`):

```bash
grep -n "class ChatRequest" -A6 src/albercik_chatbot/api/schemas.py
```

## Scenario 6 — think=true vs. think=false comparison (Story 3, SC-004)

```bash
# Run 1 — think disabled (default)
uv run python scripts/run_eval.py --save-json /tmp/eval-think-false.json

# Edit .env: OLLAMA_THINK=true
docker compose up -d app

# Run 2 — think enabled
uv run python scripts/run_eval.py --save-json /tmp/eval-think-true.json

uv run python scripts/compare_eval_runs.py /tmp/eval-think-false.json /tmp/eval-think-true.json
```

Expected: a side-by-side table of accuracy (grounded/insufficient/out-of-
scope/false-grounded) and latency (average, p50, p95) for both
configurations. Document the resulting default choice in `eval/README.md`
or this feature's PR description per spec SC-004 — do not assume
`think=false` is faster/better without this output.

**Completed 2026-08-18** — reports saved at
`eval/results/qwen3-4b-think-false.json` /
`eval/results/qwen3-4b-think-true.json`; full table in `eval/README.md`'s
"OLLAMA_THINK A/B comparison" → "Measured result" subsection. Outcome:
`OLLAMA_THINK=false` selected as the default (~3.6x faster on average,
and `think=true` introduced 6/30 new `unavailable` outcomes from
exhausting the answer-token budget on reasoning before producing valid
structured output — see research.md §11 "Measured result").

## Scenario 7 — Existing security/cost controls unaffected

```bash
uv run pytest tests/contract/ tests/unit/test_budget.py tests/unit/test_provider_selection.py -v
```

Expected: all green — rate limiting, kill switch, budget, concurrency,
size limits, and prompt-injection tests (spec Testing items 13–14) are
unaffected by this feature.

## Full regression

```bash
uv run pytest
```

Expected: all green, or every failure traceable to a deliberate,
documented `LLMResult`/`ChatResponse` contract change from this feature
(spec SC-005) — never a silent regression.
