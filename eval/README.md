# Albercik RAG Evaluation Dataset

This directory contains a fixed set of evaluation questions for the ALBERTOS/Albercik chatbot.

## Files

- `questions.jsonl` — 30 test questions with an expected outcome.
- Each record contains:
  - `id`
  - `question`
  - `expected_outcome`
  - `notes`

## Running it locally

1. Bring up the stack and confirm it's healthy:
   ```bash
   docker compose build app
   docker compose up -d
   curl localhost:8000/health
   ```
2. Set a real `ANTHROPIC_API_KEY` in `.env` (with an actual balance/credits —
   without one, every `grounded` question will end up as `unavailable`, not
   because anything is broken, but because the LLM call itself genuinely
   fails).
3. Run the whole eval with one command:
   ```bash
   uv run python scripts/run_eval.py
   ```
   The script itself: creates/logs in as a dedicated `eval-runner` admin,
   **resets the knowledge base** (deletes every existing document and
   re-uploads `knowledge/*.txt` fresh), sends all 30 questions through
   `/api/v1/chat`, and prints a result-by-result table plus the metrics
   from the "Recommended metrics" section below. Exit code `0` means
   everything matched `expected_outcome`; `1` means there are mismatches
   (listed at the end under "Failures").

   To run the questions without resetting the knowledge base (e.g. you
   uploaded something manually and want to keep it): `--skip-reset`.

### Quick checks you can do yourself, without a full eval run

- **Whether the LLM call is even being reached** (e.g. whether the
  key/billing works): ask one question and check `outcome`:
  ```bash
  curl -s -X POST localhost:8000/api/v1/chat \
    -H 'content-type: application/json' \
    -d '{"question":"Gdzie odbywają się treningi ALBERTOS w Grodzinie?"}'
  ```
- **What actually went wrong** (server-side logs, never shown to the
  client — `providers/llm/anthropic_provider.py` logs every rejection/
  retry-exhaustion):
  ```bash
  docker compose logs app --tail=50 | grep WARNING
  ```
- **Anthropic account balance/credits** — the most reliable source is the
  provider's own dashboard directly: console.anthropic.com → Plans & Billing.

## Allowed `expected_outcome` values

- `grounded` — the answer should be based on ALBERTOS knowledge.
- `insufficient_information` — the question is about ALBERTOS, but the knowledge base doesn't contain enough information.
- `out_of_scope` — the question is outside the ALBERTOS chatbot's scope.

## Important rule

Don't change `expected_outcome` just because the current implementation fails the test.

This file is meant to be a fixed benchmark. If the chatbot answers differently than expected, treat that as a signal to analyze retrieval, the scope classifier, prompting, or answerability.

## Recommended metrics

For each run, it's worth collecting:

- expected outcome
- actual outcome
- pass/fail
- top-1/top-2/top-3 source
- similarity score for each result
- the model's answer
- latency
- token usage, if an LLM call occurred

The most important aggregate metrics:

- grounded accuracy
- insufficient-information rejection rate
- out-of-scope accuracy
- false-grounded rate

`false-grounded` is especially important: it means a case where
`insufficient_information` was expected, but the system returned `grounded`.

## Dataset

The questions were prepared for a test ALBERTOS knowledge base containing, among others:

- information about ALBERTOS
- trainings
- contact
- instructors
- Summer Karate CAMP 2026
- 2026 kyu exams

Before comparing results, make sure the corresponding knowledge files have been loaded into the database.
