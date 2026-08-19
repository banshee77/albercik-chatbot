# Albercik RAG Evaluation Dataset

This directory contains a fixed set of evaluation questions for the ALBERTOS/Albercik chatbot.

**Current status (2026-08-19)**: feature 004 is **complete**. The default
Ollama model is `qwen3:8b`, measuring a deterministic **19/20 (95%)**
grounded accuracy, 7/7 insufficient-information rejection, 0/7
false-grounded, 3/3 out-of-scope. SC-001 was deliberately **amended** to
accept ≥19/20 for the MVP (see
`specs/004-rag-answerability-and-ollama-performance/spec.md`'s "SC-001
acceptance-criterion amendment" and `research.md` §18) — question **#6**
("Czy na treningach ćwiczy się w butach?") is a known, intentionally
accepted MVP limitation, not an unresolved gap. Everything below this
line is the full historical record of how that number was reached
(model/prompt experiments, dated measurements, and superseded status
notes) — read the model-selection and amendment sections above for
current status; older sections describe earlier, since-superseded states
of the feature and are preserved as-recorded, not updated to match.

## Files

- `questions.jsonl` — 30 test questions with an expected outcome.
- Each record contains:
  - `id`
  - `question`
  - `expected_outcome`
  - `notes`

## Running it locally

1. Bring up the stack and confirm it's healthy. The default backend is
   the local Ollama model — no API key needed, and its model is
   provisioned automatically on `docker compose up -d` (see
   `specs/002-add-ollama-provider/quickstart.md`):
   ```bash
   docker compose build app
   docker compose up -d
   curl localhost:8000/health
   ```
   To evaluate the paid Anthropic backend instead, set `LLM_PROVIDER=anthropic`
   and a real `ANTHROPIC_API_KEY` (with an actual balance/credits — without
   one, every `grounded` question will end up as `unavailable`, not because
   anything is broken, but because the LLM call itself genuinely fails) in
   `.env`, then `docker compose up -d app` to restart with it.
2. Run the whole eval with one command:
   ```bash
   uv run python scripts/run_eval.py
   ```
   The script itself: creates/logs in as a dedicated `eval-runner` admin,
   **resets the knowledge base** (deletes every existing document and
   re-uploads `knowledge/*.txt` fresh), sends all 30 questions through
   `/api/v1/chat`, and prints a result-by-result table plus the metrics
   from the "Recommended metrics" section below. Exit code `0` means
   everything matched `expected_outcome`; `1` means there are mismatches
   (listed at the end under "Failures"). Every report is headed with
   `=== Eval run — backend: <provider> (model=<model>) ===`, read from the
   same configuration the target app is running with (spec FR-016).

   To run the questions without resetting the knowledge base (e.g. you
   uploaded something manually and want to keep it): `--skip-reset`.

   To also save the full per-question results + summary to a JSON file
   (for `scripts/compare_eval_runs.py`, below): `--save-json <path>`.

### Comparing both backends

Run the eval once per backend, switching `LLM_PROVIDER` and restarting
`app` between runs — the question set itself never changes:

```bash
# Run 1: local Ollama backend (default)
uv run python scripts/run_eval.py

# Run 2: paid Anthropic backend
#   .env: LLM_PROVIDER=anthropic, ANTHROPIC_API_KEY=<a real key with balance>
#   docker compose up -d app
uv run python scripts/run_eval.py
```

Each run's report header identifies which backend produced it, so the two
reports' pass/fail and metric tables can be compared side by side (spec
Acceptance Scenario US3.1).

### `OLLAMA_THINK` A/B comparison (feature 004-rag-answerability-and-ollama-performance)

`OLLAMA_THINK` controls whether the local Qwen3 model performs its
extended internal reasoning step before answering — a server-only,
non-client-overridable setting (`.env`, `config.py::Settings.OLLAMA_THINK`,
default `false`). Measuring its effect uses the same "run once per
configuration, compare the two labeled reports" pattern as the
cross-provider comparison above, plus `scripts/compare_eval_runs.py` for
an automatic side-by-side diff:

```bash
# Run 1: thinking disabled (default)
uv run python scripts/run_eval.py --save-json eval/results/qwen3-4b-think-false.json

# Edit .env: OLLAMA_THINK=true, then:
docker compose up -d app

# Run 2: thinking enabled
uv run python scripts/run_eval.py --save-json eval/results/qwen3-4b-think-true.json

# Side-by-side table: accuracy, latency (avg/p50/p95), tokens/sec
uv run python scripts/compare_eval_runs.py \
  eval/results/qwen3-4b-think-false.json eval/results/qwen3-4b-think-true.json
```

The report's backend header includes `think=True`/`think=False` for the
Ollama backend specifically, so the two saved JSON files are
self-identifying even without the filenames.

#### Measured result (2026-08-18, `qwen3:4b`, RTX 3070 GPU, `LLM_MAX_ANSWER_TOKENS=1024`)

Saved reports: [`eval/results/qwen3-4b-think-false.json`](results/qwen3-4b-think-false.json),
[`eval/results/qwen3-4b-think-true.json`](results/qwen3-4b-think-true.json).

| Metric | `think=false` | `think=true` |
|---|---|---|
| Pass rate | 77% (23/30) | 80% (24/30) |
| Grounded accuracy | 65% (13/20) | 70% (14/20) |
| Insufficient-info rejection | 100% (7/7) | 100% (7/7) |
| Out-of-scope accuracy | 100% (3/3) | 100% (3/3) |
| False-grounded | 0/7 (0%) | 0/7 (0%) |
| Latency avg / p50 / p95 (ms) | 2467 / 2138 / 6017 | 8948 / 9620 / 13551 |
| Avg generation tokens/sec | 75.5 | 85.2 |
| Avg prompt-eval tokens/sec | 7514 | 14791 |
| Avg load duration (ms) | 186 | 203 |
| `unavailable` outcomes | 0/30 | **6/30** |

**Decision: `OLLAMA_THINK=false` is the default**, and this is a measured
result, not an assumption. `think=true` is ~3.6x slower on average
(9.6x at p95) for a 5-percentage-point grounded-accuracy gain that is
more than offset by a new reliability problem it introduces:
on 6 of 30 questions, `qwen3:4b` spent its entire
`LLM_MAX_ANSWER_TOKENS` (1024) budget on the internal reasoning step,
leaving nothing for the actual structured `{"supported": ..., "answer":
...}` JSON — `message.content` came back an **empty string**, which
correctly fails safe to `unavailable` (`LLMProviderError`, logged as
"Ollama returned a structured answerability response that failed to
parse or validate: Expecting value: line 1 column 1 (char 0)") rather
than being silently misreported as `grounded` or
`insufficient_information` — proof the fail-safe design (research.md §5,
FR-008) holds up under a real adverse interaction, but also a genuine,
newly-discovered downside of `think=true` at the current token budget
that `think=false` never hits. Both configurations are labeled Ollama
runs against the exact same knowledge base and question set — no
retrieval, prompting, or benchmark changes were made between runs.

**Open issue, not fixed by this comparison**: neither configuration
reaches the SC-001 grounded-accuracy target (20/20) — see "Known
open issue" below. This is orthogonal to the `OLLAMA_THINK` decision
(`think=true` does not fix it and makes overall reliability worse), so it
does not change which `OLLAMA_THINK` value is preferred, but it does mean
this feature's answerability-correctness acceptance gate (SC-001) is not
currently met by either configuration and needs separate follow-up
investigation into the answerability system-prompt rules (out of scope
for this evaluation task, and no such change was made here).

### Quick checks you can do yourself, without a full eval run

- **Whether the LLM call is even being reached** (e.g. whether the
  key/billing works): ask one question and check `outcome`:
  ```bash
  curl -s -X POST localhost:8000/api/v1/chat \
    -H 'content-type: application/json' \
    -d '{"question":"Gdzie odbywają się treningi ALBERTOS w Grodzinie?"}'
  ```
- **What actually went wrong** (server-side logs, never shown to the
  client — `providers/llm/anthropic_provider.py` or
  `providers/llm/ollama_provider.py`, whichever backend is active, logs
  every rejection/retry-exhaustion):
  ```bash
  docker compose logs app --tail=50 | grep WARNING
  ```
- **Anthropic account balance/credits** (only relevant when
  `LLM_PROVIDER=anthropic`) — the most reliable source is the provider's
  own dashboard directly: console.anthropic.com → Plans & Billing.

## Allowed `expected_outcome` values

- `grounded` — the answer should be based on ALBERTOS knowledge.
- `insufficient_information` — the question is about ALBERTOS, but the knowledge base doesn't contain enough information.
- `out_of_scope` — the question is outside the ALBERTOS chatbot's scope.

## Important rule

Don't change `expected_outcome` just because the current implementation fails the test.

This file is meant to be a fixed benchmark. If the chatbot answers differently than expected, treat that as a signal to analyze retrieval, the scope classifier, prompting, or answerability.

## Recommended metrics

For each run, `scripts/run_eval.py` reports, per question (printed and, with
`--save-json`, saved):

- expected outcome
- actual outcome
- pass/fail
- the model's answer
- sources
- latency (ms)
- input/output token counts (correlated from the corresponding
  `usage_records` row via the response's `request_id` — see
  `contracts/chat-endpoint-delta.md` in the feature spec)
- generation tokens/sec (`output_tokens / (eval_duration_ns / 1e9)` on
  Ollama; falls back to the coarser `output_tokens / (latency_ms / 1000)`
  when that native figure isn't available, e.g. on Anthropic)
- prompt-eval tokens/sec (`input_tokens / (prompt_eval_duration_ns / 1e9)`)
  — Ollama-only, no fallback
- load duration (ms) — Ollama-only, time spent loading the model before
  prompt evaluation/generation; near-zero on a warm model

Any field the active backend doesn't report is shown as `n/a`, never a
fabricated number.

The most important aggregate metrics (printed in the "Summary" and
"Performance" sections):

- grounded accuracy
- insufficient-information rejection rate
- out-of-scope accuracy
- false-grounded rate
- latency average / p50 / p95
- average output tokens, average generation tokens/sec, average
  prompt-eval tokens/sec, average load duration

`false-grounded` is especially important: it means a case where
`insufficient_information` was expected, but the system returned `grounded`.

See spec.md's Success Criteria (SC-002) for why the ≥85% insufficient-
information rejection target is phrased as "at least 6 of the 7"
questions on this specific fixture: it's an MVP acceptance gate sized to
catch a regression back toward the pre-fix 0/7 failure mode, not a
statistically powered claim about production-scale accuracy — 7 items is
too small a sample for a tight confidence interval.

## Known open issue: grounded accuracy below target (measured 2026-08-18)

The live evaluation runs recorded above (`qwen3:4b`, both `OLLAMA_THINK`
settings, real GPU-accelerated Ollama, no Anthropic call) show:

- **SC-001 (grounded accuracy 20/20) — NOT MET.** `think=false`: 13/20
  (65%). `think=true`: 14/20 (70%).
- SC-002 (insufficient-information rejection ≥6/7) — met, both runs: 7/7.
- SC-003 (false-grounded ≤1/7) — met, both runs: 0/7.
- Out-of-scope accuracy 3/3 — met, both runs.

The structured-answerability fix (Stories 1–2) correctly eliminated the
pre-fix 7/7 false-grounded failure mode this feature targeted, but the
model was over-conservative on a subset of genuinely grounded questions
— see the targeted correction attempt below for root-cause diagnosis and
what was (and wasn't) fixed.

### Targeted correction attempt (2026-08-18)

Each of the 7 originally-failing questions (ids 6, 11, 13, 14, 24, 25, 26)
was diagnosed individually by replicating `ask_question.py`'s exact
retrieval → relevance-filter → context-limit → prompt-assembly → LLM-call
pipeline and inspecting retrieved chunks, similarity scores, the final
context sent to the model, and the raw structured `supported`/`answer`
result. **Retrieval was never the problem**: every one of the 7 questions
had its supporting fact(s) retrieved above the relevance threshold and
present in the final context sent to the LLM (category A — insufficient
retrieval — ruled out for all 7; category C — structured-output/provider
parsing failure — also ruled out, all 7 produced valid, well-formed
`{"supported": ..., "answer": ...}` JSON). The failures were category
**B** (context present, answerability rules read too strictly) in 6 of 7
cases, with #25 additionally showing category **D** (compound-question
handling — the model correctly answered one sub-question but not the
other, both from the same retrieved chunk):

| # | Question | Diagnosis |
|---|---|---|
| 6 | Czy na treningach ćwiczy się w butach? | B — context says "ćwiczenia odbywają się na boso" (barefoot); model treated this paraphrase as not "jednoznaczne" (unambiguous) enough |
| 11 | Czy na obóz mogą pojechać dzieci, które nie trenują karate? | B — context explicitly says non-karate people may attend; model's own answer text was self-contradictory (misread the Polish double-negation "nie tylko") yet correctly suppressed via `supported=false` |
| 13 | Ile kosztuje egzamin na żółty pas? | B — requires combining "żółty pas = 8 kyu" with "9–6 kyu costs 100 zł", both explicit in the same chunk |
| 14 | Czy trzeba mieć licencję PFKT, żeby przystąpić do egzaminu? | B — explicit fact present ("licencję PFKT od egzaminu na żółty pas (8 kyu)"), with a genuine minor source-wording ambiguity about earlier exams |
| 24 | A co z Wierzbinem dla początkujących? | B — context has an explicit Wierzbin/beginners section; standalone question is fully answerable from it (no conversation memory needed) |
| 25 | ile kosztuje egzamin na 8 kyu i czy potrzebuje licencji pfkt? | D (+B) — compound question; model answered the license half correctly but failed the cost half, which needs the same fact-combination as #13 |
| 26 | Moje dziecko nie ćwiczy karate. Czy mimo tego może pojechać z ALBERTOS na obóz? | B — model's own `answer` text was actually correct, but it still set `supported=false`, hedging past the point the explicit context supported |

No question required a fabricated negative claim to fail — rule 6 (no
inference from silence) was working correctly throughout; the failures
were all instances of the model being *more* cautious than the explicit
context warranted.

**Fix applied**: one new rule (`domain/prompting.py::SYSTEM_PROMPT` rule
7) clarifying that `supported=true` is appropriate whenever KONTEKST
contains the facts needed — even when the answer requires combining two
facts, the question is a paraphrase, KONTEKST uses different wording than
the question, the correct answer is affirmative or negative, or the facts
span more than one retrieved chunk. Rule 6 was left completely unchanged
and rule 7 is explicitly scoped to "facts genuinely present" — it cannot
be read as license to infer from silence. No retrieval, chunking,
embedding, Top-K, threshold, or scope-classifier code was touched, and
`eval/questions.jsonl`'s expected outcomes were not modified. Regression
tests were added in `tests/unit/test_prompting.py` asserting rule 7's
content and that it cannot be overridden by retrieved-document content
(same injection-resistance guarantee as rule 6).

**Re-run result (`OLLAMA_THINK=false`, same knowledge base, same
question set)** — [`eval/results/qwen3-4b-think-false-v2.json`](results/qwen3-4b-think-false-v2.json):

| Metric | Pre-fix | Post-fix (rule 7) |
|---|---|---|
| Grounded accuracy | 65% (13/20) | 65% (13/20) — **unchanged in aggregate** |
| Insufficient-info rejection | 100% (7/7) | 85.7% (6/7) — still meets ≥6/7 |
| False-grounded | 0/7 (0%) | 1/7 (14.3%) — still meets ≤1/7, but non-zero for the first time |
| Out-of-scope accuracy | 100% (3/3) | 100% (3/3) |

**SC-001 is still NOT met.** The composition of failures changed —
#13, #14, and #24 (three of the originally diagnosed questions) now pass
— but #3, #5, and #22 (previously passing) newly failed, and a new
false-grounded case (#15, "Czy ALBERTOS prowadzi indywidualne treningi
karate?" — the model incorrectly conflated "prowadzi grupy dla dzieci,
młodzieży i dorosłych" [runs group classes] with "prowadzi treningi
indywidualne" [runs individual training], a genuine misreading rule 6
still correctly should have caught) appeared. #6, #11, #25, #26 remain
failing despite the fix.

**Root cause of the flat aggregate result: `qwen3:4b` sampling
non-determinism dominates the signal at this benchmark size.** A
same-prompt, same-context diagnostic re-run of question #13 (run before
this fix was even deployed) independently returned `supported=true` with
the correct answer on one call and `supported=false` on another (the
original failing eval run) — i.e. the model's judgment on borderline
questions is not stable across identical inputs, only across the same
temperature-driven decoding process. With only 20 `grounded`-expected
questions, a handful of questions flipping either direction from run to
run is enough to fully mask or fully fabricate an apparent accuracy
change. **This means a single 30-question run's pass/fail delta is not,
by itself, reliable evidence that a prompt change helped or hurt** — the
same caveat spec.md already applies to SC-002's small sample size (see
"Recommended metrics" above) turns out to apply to SC-001 too, and more
severely, since `grounded` correctness here depends on the model's free-
text judgment call, not just a threshold-shaped retrieval decision.

**Stopping here, as instructed — no further prompt tuning attempted.**
Per this task's explicit scope: the diagnosis found no retrieval issue,
one well-targeted, minimal prompt clarification was made and verified not
to weaken rule 6, and one re-run was executed. Chasing this single run's
specific remaining failures with further prompt edits would be exactly
the "blind tuning against one noisy sample" this task was told to avoid.
**Recommended next step for a future session** (not undertaken here):
run the frozen benchmark multiple times (e.g. 3–5 repetitions) per prompt
variant and compare *distributions*, not single-run pass counts, before
attributing any further change to the prompt rather than to sampling
variance — and/or evaluate whether a lower/fixed `temperature` specifically
for the eval harness (not necessarily production) would stabilize
measurement without changing the fix approach.

Feature 004 is **not safe to close** on SC-001. SC-002/SC-003 (the
feature's original headline problem — false grounding) remain solidly
fixed in aggregate (both runs stay within their MVP-gate targets), but
the newly observed non-zero false-grounded case in the post-fix run is
worth a human's attention even though it stays within threshold.

### Reproducibility experiment: `OLLAMA_TEMPERATURE`/`OLLAMA_SEED` (2026-08-19)

The "recommended next step" above — stabilize measurement before doing
any more prompt tuning — was executed. Two new, Ollama-provider-only,
server-config settings were added (`config.py`, forwarded by
`OllamaLLMProvider` inside the request `options` object, alongside
`num_predict`; never part of the shared `LLMProvider.complete()`
signature, never client-overridable — same pattern as `OLLAMA_THINK`,
proven by `tests/unit/test_ollama_provider.py` and the parametrized
override-rejection tests in `tests/contract/test_chat_no_client_override.py`):

- `OLLAMA_TEMPERATURE=0` (was Ollama's own nonzero sampling default)
- `OLLAMA_SEED=42`

`AnthropicLLMProvider` has no `temperature`/`seed` parameter at all and
its request body is unaffected regardless of these settings' values
(`tests/unit/test_anthropic_provider_retries.py`).

**Experiment**: the frozen 30-question benchmark was run 3 times back to
back, same knowledge base, same model (`qwen3:4b`), `OLLAMA_THINK=false`,
`OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`, no config change between runs —
[`eval/results/repeatability-run-1.json`](results/repeatability-run-1.json),
[`-2.json`](results/repeatability-run-2.json),
[`-3.json`](results/repeatability-run-3.json).

**Result: perfectly stable.** All 30 questions produced the identical
`actual_outcome` in all 3 runs — **30/30 (100%) per-question outcome
agreement**, **zero unstable question IDs**. Question #13 specifically
(the question whose instability motivated this experiment) returned
`supported=true`/`grounded` in all 3 runs — **stable**.

| Metric | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Grounded accuracy | 85% (17/20) | 85% (17/20) | 85% (17/20) |
| Insufficient-info rejection | 100% (7/7) | 100% (7/7) | 100% (7/7) |
| False-grounded | 0/7 | 0/7 | 0/7 |
| Out-of-scope accuracy | 100% (3/3) | 100% (3/3) | 100% (3/3) |

Identical failing questions in every run: #3, #6, #22 — all three
`insufficient_information` where `grounded` was expected (the model
under-answers; never a false-grounded/safety miss). Latency/tokens-per-
second figures still vary run to run (GPU scheduling noise, not a
determinism target), but every accuracy/outcome figure is now bit-for-bit
identical.

**Conclusion**: this eliminates sampling non-determinism as an
explanation for either the remaining gap or of any future prompt-tuning
signal. Grounded accuracy at 85% (17/20) — deterministically measured —
is the current true baseline, still short of the SC-001 target (20/20),
but **further prompt calibration is now scientifically meaningful**: a
future change's effect on these specific 3 remaining questions (#3, #6,
#22) can be measured directly and trusted, without needing repeated runs
to separate signal from sampling noise. No prompt, retrieval, embedding,
Top-K, threshold, chunking, or scope-classifier code was touched during
this experiment, and `eval/questions.jsonl`'s expected outcomes were not
modified — per this task's explicit scope, no further tuning was
attempted here either; that is left for the next session, now on solid
methodological footing.

### Final targeted calibration pass: rule 8 — MEASURED REGRESSION, not adopted (2026-08-19)

With the deterministic baseline established above (85%, 17/20, identical
failures every run: #3, #6, #22), those 3 remaining questions were
diagnosed individually the same way as the earlier 7 (retrieved chunks,
similarity, final context, raw structured result all inspected). **Every
needed fact was present in the final context sent to the LLM in all 3
cases** — retrieval (category A) and structured-output parsing (category
C) were ruled out again:

| # | Question | Fact present in context | Reasoning step needed |
|---|---|---|---|
| 3 | O której zaczyna się trening początkujących w Wierzbinie? | Yes — "Wierzbin ... Poniedziałek i środa, godz. 17:30–18:25. Dzieci i młodzież: początkujący..." verbatim in the retrieved `treningi.txt` chunk | Correct-item selection: the fact sits among 4 other similarly-worded venue/group entries in the same chunk; the model appears to lose it in the list rather than fail to retrieve it |
| 6 | Czy na treningach ćwiczy się w butach? | Yes — "Ćwiczenia odbywają się na boso." | Logical negation: the model's own raw `answer` text explicitly reasoned "co oznacza, że nie używa się butów" (correctly deriving "no shoes") **but still set `supported=false`** — the clearest possible evidence the failure is a decision-threshold problem, not a comprehension problem |
| 22 | Nigdy wcześniej nie trenowałem karate i nie mam jeszcze kimona. Czy mogę przyjść na pierwszy trening? | Yes — "Na początek treningów wystarczy strój sportowy..." | Direct inference from an explicit general condition applied to the asker's stated situation; the model's raw `answer` degenerated into echoing the question text verbatim rather than answering it |

No question required inventing a negative from silence — rule 6 held
throughout. **Fix applied**: rule 8, added to `SYSTEM_PROMPT`
(`domain/prompting.py`), explicitly naming the (A) fact-genuinely-absent
vs. (B) fact-present-needs-one-step distinction rule 7 didn't cover:
logical negation of an explicit statement (barefoot → not in shoes),
correct-item selection among similarly-worded list entries, and a direct
inference from an explicit general condition — all scoped, like rule 7,
to never override rule 6 when the fact is genuinely absent (a contrasting
online-classes example was included in the rule text itself for this
reason). Regression tests were added in `tests/unit/test_prompting.py`
(rule 8's content covers all 3 shapes; rule 6 remains completely intact
for the genuinely-absent case; rule 8 cannot be planted or overridden by
retrieved-document content) — all passed (TDD RED confirmed first).

**Re-run result** (`OLLAMA_THINK=false`, `OLLAMA_TEMPERATURE=0`,
`OLLAMA_SEED=42`, same KB, single run per this task's explicit
"do not modify the prompt again in the same pass" instruction) —
[`eval/results/qwen3-4b-think-false-rule8.json`](results/qwen3-4b-think-false-rule8.json):

| Metric | Deterministic baseline (rules 1–7) | With rule 8 |
|---|---|---|
| Grounded accuracy | 85% (17/20) | **35% (7/20) — severe regression** |
| Insufficient-info rejection | 100% (7/7) | 100% (7/7) |
| False-grounded | 0/7 | 0/7 |
| Out-of-scope | 100% (3/3) | 100% (3/3) |

**Rule 8 made grounded accuracy dramatically worse, not better.** 13
questions failed instead of 3 — every one of the 3 originally-targeted
questions (#3, #6, #22) *still* failed, plus 10 more previously-passing
questions newly failed (#1, #2, #5, #11, #13, #14, #23, #24, #25, #26),
all with the identical canned `insufficient_information` message. This is
not a case of "traded some failures for others" (as rule 7's flat result
was) — it is a strict regression across the board. The most plausible
explanation: rule 8 is long (roughly as long as rules 5–7 combined) and
its (A) branch repeats "supported=false" / negation-heavy framing
prominently right at its start; on a small local model already prone to
over-caution, adding more instruction text emphasizing the false-case
appears to have shifted the model's general decision threshold toward
`false`, rather than surgically fixing only the 3 targeted patterns. This
is a genuine, reproducible (deterministic config, single run trusted per
the established §15 methodology) negative result — the false-grounded
rate stayed at 0/7 throughout, so no safety property regressed, but the
recall cost is severe.

**Per this task's explicit instructions ("do not tune further, stop"),
rule 8 was initially left in the codebase exactly as measured, not
reverted or edited again in that same pass** — the decision of whether to
revert it was left to the next session/a human reviewer.

**REJECTED, reverted 2026-08-19 (same day, next pass)**: rule 8 was
removed from `SYSTEM_PROMPT` (`domain/prompting.py`) and its 3 regression
tests (`test_system_prompt_distinguishes_missing_fact_from_explicit_fact_needing_a_step`,
`test_rule_8_does_not_weaken_rule_6_for_genuinely_missing_facts`,
`test_document_content_cannot_override_rule_8_either`) were removed from
`tests/unit/test_prompting.py`, restoring the exact rules-1–7 prompt text
that measured the real, deterministic 85% (17/20) baseline in §15. **Rule
8 is not part of the active prompt.** This section, and research.md §16,
are kept as the historical record of the experiment and its rejection —
the rule-8 prompt text itself is preserved in git history (not
reproduced again here) for anyone who wants to inspect exactly what was
tried. The re-run confirming the restored baseline is in the section
immediately below.

Any future attempt at the remaining #3/#6/#22 gap should change at most
one small, narrowly-scoped instruction at a time and re-measure after
each change individually, rather than adding another multi-clause rule —
this experiment is evidence that, for this model, prompt length/emphasis
has a real and unpredictable effect on the false/true threshold, not just
on the targeted failure patterns.

**SC-001 is still not met** (85%/17/20, the restored baseline — see
below for the confirming re-run). **Not safe to close.**

### Deterministic baseline restored (2026-08-19)

After reverting rule 8, the frozen 30-question benchmark was run once
more with the unchanged deterministic configuration
(`OLLAMA_THINK=false`, `OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`, same KB)
to confirm the revert actually restores the §15 baseline rather than
landing on some other state:

| Metric | §15 baseline (rules 1–7) | Rule 8 (rejected) | Post-revert (rules 1–7, confirmed) |
|---|---|---|---|
| Grounded accuracy | 85% (17/20) | 35% (7/20) | **85% (17/20)** |
| Insufficient-info rejection | 100% (7/7) | 100% (7/7) | **100% (7/7)** |
| False-grounded | 0/7 | 0/7 | **0/7** |
| Out-of-scope | 100% (3/3) | 100% (3/3) | **100% (3/3)** |

Identical failing questions as the §15 baseline: **#3, #6, #22** — see
[`eval/results/qwen3-4b-think-false-post-revert.json`](results/qwen3-4b-think-false-post-revert.json).
The deterministic rules-1–7 baseline is confirmed restored exactly.

### Model selection: qwen3:8b adopted as default (2026-08-19)

With the prompt fixed at the confirmed rules-1–7 deterministic baseline
above (no prompt, retrieval, embedding, chunking, threshold, Top-K,
context-limit, scope-classifier, or answerability-contract changes), a
controlled evaluation compared `qwen3:8b` against the `qwen3:4b` baseline
— same deterministic config (`OLLAMA_THINK=false`,
`OLLAMA_TEMPERATURE=0`, `OLLAMA_SEED=42`), same knowledge base, same
frozen 30-question benchmark, single run each, model provisioned via the
existing `ollama-init` mechanism (no new provisioning code).

| Metric | qwen3:4b (baseline) | qwen3:8b |
|---|---|---|
| Grounded accuracy | 85% (17/20) | **95% (19/20)** |
| Insufficient-info rejection | 100% (7/7) | 100% (7/7) |
| False-grounded | 0/7 | 0/7 |
| Out-of-scope accuracy | 100% (3/3) | 100% (3/3) |
| Latency avg / p50 / p95 (ms) | 1881.53 / 1492.00 / 5469.00 | 2572.53 / 2031.00 / 4177.00 |
| Generation tokens/sec | 80.11 | 55.30 |
| Prompt-eval tokens/sec | 12511.61 | 10002.58 |
| Avg load duration (ms) | 399.35 | 755.11 |
| VRAM (RTX 3070, 8 GB budget) | — | ~6.0 GB, no OOM/timeout/provider failures |

Full reports:
[`eval/results/qwen3-4b-think-false-post-revert.json`](results/qwen3-4b-think-false-post-revert.json)
(baseline) and
[`eval/results/qwen3-8b-think-false.json`](results/qwen3-8b-think-false.json)
(8B), compared with `scripts/compare_eval_runs.py`.

**Per-question**: qwen3:8b's only failure was **#6** ("Czy na treningach
ćwiczy się w butach?") — the same question that failed on 4B. Of the
other two 4B failures, **#3 and #22 now pass** on 8B (both `grounded`, as
expected); no previously-passing question regressed, and no
`unavailable`/false-grounded outcomes appeared. No workaround targeting
#3, #6, or #22 specifically was made — this is purely a model swap.

**Decision: `qwen3:8b` adopted as the default Ollama model** (was
`qwen3:4b`) — `config.py`, `.env.example`, `docker-compose.yml`. Rationale:
higher deterministic grounded accuracy (19/20 vs. 17/20) at identical
insufficient-information rejection, false-grounded, and out-of-scope
rates, with no safety regression and no reliability issue (no OOM,
timeout, or provider failure) on the RTX 3070 reference host; the latency
increase (avg +0.69s, ~31% lower generation tokens/sec) remains
acceptable for this deployment's interactive use case. `qwen3:4b` remains
a fully valid, lower-resource manual override
(`OLLAMA_MODEL=qwen3:4b` in `.env`) — no new model-selection mechanism
was introduced.

**SC-001 (original: grounded accuracy 20/20) is NOT met on qwen3:8b** —
19/20, not 20/20. Question #6 was deliberately **not** investigated or
fixed in this pass (a narrow model-adoption/documentation change only,
per that task's explicit scope).

**Superseded 2026-08-19**: SC-001 itself was subsequently amended (a
deliberate product decision, not a re-measurement) to accept **grounded
accuracy ≥19/20 (≥95%)** for the MVP — see `spec.md`'s "SC-001
acceptance-criterion amendment" and `research.md` §18 for the full
decision record. Against the amended criterion, this 19/20 result
**meets SC-001**, and — with SC-002/SC-003/SC-004 also already met —
**feature 004 is documented as complete**, with question #6 retained as
a known, accepted MVP limitation rather than an open gap.

**Historical note**: all `qwen3:4b`-labeled results elsewhere in this
document (the original Polish-phase measurements, the rule-7/rule-8
experiments, the §15 reproducibility experiment, and the post-revert
confirmation) describe runs against `qwen3:4b` specifically and are left
exactly as originally recorded — they are not, and must not be read as,
`qwen3:8b` results. `qwen3:4b` was the default at the time those sections
were written; `qwen3:8b` is the default from this section forward.

## Dataset

The questions were prepared for a test ALBERTOS knowledge base containing, among others:

- information about ALBERTOS
- trainings
- contact
- instructors
- Summer Karate CAMP 2026
- 2026 kyu exams

Before comparing results, make sure the corresponding knowledge files have been loaded into the database.
