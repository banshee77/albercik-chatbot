# Phase 1 Data Model: Local Ollama LLM Provider

Derived from the spec's Key Entities section and resolved against the Phase 0
research decision on budget isolation (research.md §4). This feature makes
exactly one additive schema change; every other existing table
(`Administrator`, `KnowledgeDocument`, `DocumentChunk`, `RateLimitWindow`) is
untouched.

## UsageRecord (extended)

One row per LLM or embedding provider call — unchanged in purpose from
`001-albertos-rag-chatbot`'s data-model.md. Adds one new required column so
budget enforcement can structurally distinguish which backend a paid-kind
(`provider_kind='llm'`) row belongs to, per research.md §4.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | unchanged |
| `request_id` | UUID | unchanged |
| `provider_kind` | enum: `llm`, `embedding` | unchanged — still the *kind of resource* dimension (paid-model-call vs. local-embedding-call) |
| `provider_name` | enum: `anthropic`, `ollama`, `local_sentence_transformer` | **NEW.** The *which backend* dimension, orthogonal to `provider_kind`. Always populated, including on `embedding`-kind rows (which today are always local `sentence-transformers` calls — recorded as `provider_name='ollama'`'s sibling would be wrong; see Validation rules below for the exact value embedding rows use). |
| `provider_model` | text | unchanged — e.g. `claude-sonnet-4-5`, `qwen3:4b`, `intfloat/multilingual-e5-small` |
| `input_tokens` | integer, nullable | unchanged |
| `output_tokens` | integer, nullable | unchanged |
| `success` | boolean | unchanged |
| `latency_ms` | integer | unchanged |
| `created_at` | timestamptz | unchanged — indexed; budget checks (`infra/budget.py`) query this column |

**Validation rules**:
- Never contains prompt text, document content, API keys, or credentials
  (unchanged from `001`, FR-048/Principle IX) — `provider_name` is a short
  enum value, not free text, so it cannot itself become a content leak.
- `provider_name` is set from the caller's own configured/active backend at
  write time, never inferred from `provider_model`'s string value (the
  entire point of this column, per research.md §4's rejected-alternative
  discussion) or persisted with a NULL/optional intent — it is `NOT NULL`.
- Embedding rows (`provider_kind='embedding'`) are, today, always produced
  by the local `sentence-transformers` model — a *third* kind of "backend"
  that is neither the Anthropic LLM backend nor the Ollama LLM backend.
  Rather than force embedding rows into an ill-fitting `anthropic`/`ollama`
  choice, the enum gains a third value used only by embedding-kind rows:
  see **`ProviderName` enum** below.

## `ProviderName` enum

| Value | Used by `provider_kind='llm'` rows | Used by `provider_kind='embedding'` rows |
|---|---|---|
| `anthropic` | Yes — a Claude call | No |
| `ollama` | Yes — a local-model call | No |
| `local_sentence_transformer` | No | Yes — the existing local `sentence-transformers` embedding call (unchanged provider, newly named for symmetry with the new column) |

**Budget query change** (`infra/budget.py`): the existing filter
`WHERE provider_kind = 'llm'` becomes `WHERE provider_kind = 'llm' AND
provider_name = 'anthropic'`. Since `provider_kind='embedding'` rows never
use `provider_name='anthropic'` (they always use
`local_sentence_transformer`) and `provider_kind='llm'` rows from the
Ollama backend use `provider_name='ollama'`, this filter now structurally
excludes both existing embedding usage *and* new local-LLM usage from the
paid budget in one consistent rule, without relying on `provider_kind`
alone the way the pre-existing query did.

## Migration

One new Alembic migration, in four explicit, ordered steps — chosen
specifically so the column is never briefly `NOT NULL` with ambiguous or
guessed data for a single row, on a table that may already hold production
usage history:

1. `ALTER TABLE usage_records ADD COLUMN provider_name <enum> NULL` — added
   nullable first; no existing row is touched or required to have a value
   yet, so this step alone cannot fail or violate a constraint regardless
   of table size or content.
2. Backfill every existing row deterministically, in the same migration,
   keyed **exclusively on the existing `provider_kind` column** — never on
   `provider_model` / model-name string matching, even though
   `provider_model` would today happen to disambiguate correctly too.
   `provider_kind` is the only signal this feature already treats as the
   structurally-guaranteed-correct one (research.md §4); inferring from a
   free-text model name is exactly the fragile pattern research.md §4
   rejected for the write path, and would be equally wrong to rely on for
   the backfill path:
   ```sql
   UPDATE usage_records SET provider_name = 'anthropic'
     WHERE provider_kind = 'llm';
   UPDATE usage_records SET provider_name = 'local_sentence_transformer'
     WHERE provider_kind = 'embedding';
   ```
   These two statements are exhaustive and non-overlapping — `provider_kind`
   is itself `NOT NULL` with exactly two possible values, so every existing
   row receives a deterministic value and no row is left unmatched.
3. Verify no row was missed (belt-and-suspenders, since step 2 is already
   exhaustive by construction): the migration asserts
   `SELECT count(*) FROM usage_records WHERE provider_name IS NULL` is `0`
   before proceeding to step 4, and fails loudly (migration aborts) rather
   than silently proceeding if that's ever not the case.
4. `ALTER TABLE usage_records ALTER COLUMN provider_name SET NOT NULL` —
   only now, once every row is confirmed populated, does the column become
   required. No `SERVER DEFAULT` is set at any point: every future
   application-level insert (`application/ask_question.py`,
   `application/upload_document.py`) specifies `provider_name` explicitly,
   the same way it already explicitly specifies `provider_kind` today —
   there is no "default backend" for a database row the way there is for
   `LLM_PROVIDER` configuration.

The downgrade migration drops the column; no other column is removed or
renamed, and every existing query/model reference to `UsageRecord` other
than `infra/budget.py`'s filter continues to work unmodified.

## Configuration (not a persisted entity, but part of this feature's data shape)

| Setting | Type | Default | Notes |
|---|---|---|---|
| `LLM_PROVIDER` | enum: `anthropic`, `ollama` | `ollama` | Clarifications session, 2026-08-18. Server-side only — never derived from request content. |
| `OLLAMA_BASE_URL` | text (URL) | `http://ollama:11434` | Internal Docker network address by default (research.md §6). |
| `OLLAMA_MODEL` | text | `qwen3:4b` | Never hardcoded in `application/`/`domain/` logic (spec FR-006). |
| `OLLAMA_TIMEOUT_SECONDS` | float | to be finalized during implementation (research.md §3 — deliberately more generous than Anthropic's `PROVIDER_TIMEOUT_SECONDS`) | Independent from the Anthropic timeout setting. |

`PROVIDER_MAX_RETRIES` (existing setting) is reused by `OllamaLLMProvider`
rather than duplicated (research.md §3) — no new retry-count setting is
introduced by this feature.
