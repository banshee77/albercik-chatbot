# Phase 1 Data Model: RAG Answerability & Ollama Performance

Derived from the spec's Key Entities section, resolved against research.md.
This feature makes one additive schema change (`usage_records.provider_metrics`)
and several application-level type changes; no existing table's meaning
changes, and no table is removed. `Administrator`, `KnowledgeDocument`,
`DocumentChunk`, and `RateLimitWindow` are untouched.

## `LLMResult` (modified) — `providers/llm/protocol.py`

The structured result every `LLMProvider.complete()` call returns. Was
"a completion"; is now "a completion plus an explicit answerability
decision" — the type this feature's core behavior change hangs on.

| Field | Type | Notes |
|---|---|---|
| `answer` | `str` | **RENAMED** from `text` (research.md §1). The model's answer text. Only meaningful as a user-facing answer when `supported=True`; when `supported=False`, callers MUST ignore its content (`application/ask_question.py` always substitutes the fixed insufficient-information message — spec FR-003). |
| `supported` | `bool` | **NEW.** `True` = the retrieved context (as judged by the model, per the structured-output contract) supports answering the question — application outcome `grounded`. `False` = it does not — application outcome `insufficient_information`. This field is only ever populated from a **successfully parsed** structured response (research.md §5) — a malformed/schema-invalid/unparseable structured response never produces an `LLMResult` at all; it raises `LLMProviderError` instead, mapping to the existing `unavailable` outcome. `LLMResult` structurally cannot represent "the provider failed to give us a decision." |
| `model` | `str` | Unchanged. |
| `input_tokens` | `int \| None` | Unchanged. Normalized, provider-neutral count — this (not `provider_metrics`) is what application/domain code may read. |
| `output_tokens` | `int \| None` | Unchanged. Normalized, provider-neutral count — this (not `provider_metrics`) is what application/domain code may read. |
| `latency_ms` | `int` | Unchanged — wall-clock round trip for the single provider call. |
| `provider_metrics` | `dict[str, int] \| None` | **NEW**, optional, default `None`. Opaque below the provider boundary: `application/ask_question.py` and `domain/` MUST NOT read or branch on any key inside this dict — it exists only for usage accounting and evaluation tooling (`scripts/run_eval.py`), never for a core RAG/application decision (research.md §8). Ollama populates `total_duration_ns`, `load_duration_ns`, `prompt_eval_duration_ns`, `eval_duration_ns` — copied verbatim from Ollama's own nanosecond-native response fields, no unit conversion; the `_duration_ns` suffix makes the unit explicit in the key itself. Anthropic leaves this `None`. |

**Validation rules**:
- `supported` is always present (not optional) — there is no `LLMResult`
  that lacks an answerability decision, structurally preventing the "LLM
  returned text ⇒ assume grounded" bug this feature fixes.
- `provider_metrics`, when present, MUST NOT contain reasoning/"thinking"
  text, prompt content, or retrieved document content (FR-020) — only
  numeric timing values.

## `ANSWERABILITY_JSON_SCHEMA` (new constant) — `providers/llm/protocol.py`

Not a database entity — a shared JSON Schema `dict` both providers adapt to
their own structured-output mechanism (research.md §2, §3, §4):

```json
{
  "type": "object",
  "properties": {
    "supported": {"type": "boolean"},
    "answer": {"type": "string"}
  },
  "required": ["supported", "answer"]
}
```

## `UsageRecord` (extended) — `persistence/models.py`

One row per LLM or embedding provider call — unchanged in purpose from
`001-albertos-rag-chatbot`'s and `002-add-ollama-provider`'s data models.
Adds one new nullable column.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | unchanged |
| `request_id` | UUID | unchanged — now also returned to the caller via `ChatResponse.request_id` (below) so `scripts/run_eval.py` can correlate a chat response back to this row (research.md §9) |
| `provider_kind` | enum: `llm`, `embedding` | unchanged |
| `provider_name` | enum: `anthropic`, `ollama`, `local_sentence_transformer` | unchanged |
| `provider_model` | text | unchanged |
| `input_tokens` | integer, nullable | unchanged |
| `output_tokens` | integer, nullable | unchanged |
| `success` | boolean | unchanged |
| `latency_ms` | integer | unchanged |
| `provider_metrics` | **NEW.** `JSONB`, nullable | Verbatim copy of `LLMResult.provider_metrics` when present (research.md §8) — keys use the `*_duration_ns` naming convention (e.g. `eval_duration_ns`), native Ollama units, no conversion. `NULL` for every Anthropic-backed and every embedding row. Opaque to core application logic — read only by `scripts/run_eval.py` for usage accounting/evaluation, never by `application/ask_question.py`. Never contains prompt/document/reasoning text (FR-020) — schema-level expectation, not database-enforced. |
| `created_at` | timestamptz | unchanged — indexed |

**Validation rules**:
- `provider_metrics` is written exactly once, at `_record_usage()` call
  time, straight from `LLMResult.provider_metrics` — `application/
  ask_question.py` never constructs or edits its contents.
- Migration is purely additive (`ADD COLUMN provider_metrics JSONB NULL`)
  — no backfill needed (existing rows correctly have no such data), unlike
  the `provider_name` migration in feature 002 which had to backfill a new
  `NOT NULL` column.

## `Settings` (extended) — `config.py`

| Field | Type | Default | Notes |
|---|---|---|---|
| `OLLAMA_THINK` | `bool` | `False` | **NEW.** Server-only (research.md §6); read once at provider-construction time in `main.py`, never derived from request content. Confirmed default per spec's "Default... should be false unless technical research shows a stronger reason otherwise" — this plan does not change that default; §11's A/B measurement may justify changing it later, as a documented configuration decision, not a code change. |

## `ChatResponse` (extended) — `api/schemas.py`

| Field | Type | Notes |
|---|---|---|
| `outcome` | `Literal[...]` | unchanged |
| `answer` | `str` | unchanged |
| `sources` | `list[SourceReferenceOut]` | unchanged |
| `request_id` | `uuid.UUID` | **NEW.** The same UUID already generated per request in `api/routers/chat.py` and passed to `ask_question(...)` for usage accounting — now also returned to the caller (research.md §9). Non-sensitive (a random correlation id); does not reveal cost, timing, or configuration by itself. |

## Eval report row (extended) — `scripts/run_eval.py`, in-memory only

Not persisted — the per-question dict `_run_questions()` builds, extended
with fields sourced from the `usage_records` row looked up via the new
`request_id` (research.md §9):

| Field | Notes |
|---|---|
| `id`, `question`, `expected_outcome`, `actual_outcome`, `passed`, `sources`, `answer`, `latency_ms`, `status_code` | unchanged |
| `input_tokens` | `int \| None` — from `usage_records.input_tokens` |
| `output_tokens` | `int \| None` — from `usage_records.output_tokens` |
| `tokens_per_second` | `float \| None` — generation tokens/sec, computed per research.md §10; `None` when the inputs it needs are missing |
| `prompt_eval_tokens_per_second` | `float \| None` — **NEW**, Ollama-only, computed per research.md §10 (`input_tokens / (prompt_eval_duration_ns / 1e9)`); `None` for Anthropic rows or when `usage_records.provider_metrics` lacks the field |
| `load_duration_ms` | `float \| None` — **NEW**, Ollama-only, `provider_metrics.load_duration_ns / 1e6` for display (research.md §10); `None` for Anthropic rows |

## Eval summary (extended) — `scripts/run_eval.py`, in-memory only

`_summarize()`'s existing dict (`total`, `passed`, `pass_rate`,
`grounded_accuracy`, `insufficient_information_rejection_rate`,
`out_of_scope_accuracy`, `false_grounded_count`, `false_grounded_rate` —
all unchanged) gains:

| Field | Notes |
|---|---|
| `latency_avg_ms`, `latency_p50_ms`, `latency_p95_ms` | Computed over all `latency_ms` values in the run |
| `avg_output_tokens` | Mean of non-`None` `output_tokens` values |
| `avg_tokens_per_second` | Mean of non-`None` per-question `tokens_per_second` (generation) values |
| `avg_prompt_eval_tokens_per_second` | **NEW.** Mean of non-`None` per-question `prompt_eval_tokens_per_second` values (Ollama only) |
| `avg_load_duration_ms` | **NEW.** Mean of non-`None` per-question `load_duration_ms` values (Ollama only) — near-zero on a warm model, useful for spotting cold-load outliers |

## Two-run comparison record — `scripts/compare_eval_runs.py`, in-memory only

Loaded from two `--save-json` files (research.md §11); no new persisted
entity — a pure read/diff of two already-defined Eval summary structures,
labeled by the backend/config string each run already prints (`_active_backend_label()`,
unchanged).

## Cross-cutting rules

- No entity introduced or modified by this feature stores prompt text,
  retrieved document content, or reasoning/"thinking" content (Principle
  IX; spec FR-020) — verified per-field above.
- `provider_metrics` (both the `LLMResult` field and the `usage_records`
  column) is the only genuinely new "shape" in this feature; everything
  else is either a rename, an added scalar field, or a new setting with a
  concrete default.
