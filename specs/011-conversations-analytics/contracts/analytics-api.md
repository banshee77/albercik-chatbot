# Contract: `/api/v1/admin/analytics`

Three new, read-only, tenant-scoped endpoints. All require authentication
(`get_current_administrator` + `get_current_tenant`). All accept the same
optional `start_date`/`end_date` query parameters; when either is omitted,
both default to a `[now - 30 days, now]` window
(`config.Settings.ANALYTICS_DEFAULT_LOOKBACK_DAYS`, research.md §7). An
invalid or inverted range (`end_date` before `start_date`) → `400`.

## New: `GET /api/v1/admin/analytics/summary`

**Response `200`**:

```json
{
  "range": {"start": "2026-07-21T00:00:00Z", "end": "2026-08-20T00:00:00Z"},
  "total_requests": 214,
  "outcomes": {
    "grounded": {"count": 150, "rate": 0.7009},
    "insufficient_information": {"count": 40, "rate": 0.1869},
    "out_of_scope": {"count": 15, "rate": 0.0701},
    "unavailable": {"count": 5, "rate": 0.0234},
    "small_talk": {"count": 4, "rate": 0.0187}
  },
  "latency_ms": {"average": 890.4, "p50": 820, "p95": 1950},
  "tokens": {"input_total": 78210, "output_total": 15320},
  "providers": [
    {
      "provider_name": "ollama",
      "provider_model": "qwen3:8b",
      "request_count": 150,
      "input_tokens": 78210,
      "output_tokens": 15320
    }
  ]
}
```

- `outcomes.*.rate` = that outcome's count ÷ `total_requests`, `0.0` when
  `total_requests` is `0` (never a division error).
- `small_talk` requests count toward `total_requests` but contribute
  nothing to `tokens` or `providers` (FR-008, FR-026, SC-009) — this falls
  out of the underlying aggregation naturally, since their
  `ConversationRecord` rows have `provider_name`/`input_tokens`/
  `output_tokens` all `NULL` (data-model.md).
- `latency_ms.p50`/`p95` use PostgreSQL's `percentile_cont` (research.md
  §9); both are `null` when there are zero matching conversations in range.
- A tenant with zero activity in the range returns `200` with
  `"total_requests": 0`, every outcome's count `0`/rate `0.0`, `latency_ms`
  fields `null`, `tokens` totals `0`, and `"providers": []` — never an
  error (FR-025).
- `providers[].provider_name`/`provider_model` and every token/count
  figure are aggregated from `ConversationRecord`'s own stored snapshots
  (research.md §2a) — this endpoint never reads the deployment's *current*
  `LLM_PROVIDER`/model configuration. A range spanning a provider or model
  change shows each conversation contributing to the provider/model that
  actually answered it, so `providers` can legitimately list more than one
  provider/model pair for a single range.

## New: `GET /api/v1/admin/analytics/knowledge-gaps`

**Additional query parameter**: `limit` (integer, default `20`, clamped to
`[1, 100]`) — the maximum number of ranked groups to return.

**Response `200`**:

```json
{
  "range": {"start": "2026-07-21T00:00:00Z", "end": "2026-08-20T00:00:00Z"},
  "items": [
    {
      "normalized_question": "jakie sa ceny karnetu rodzinnego",
      "example_question": "Jakie są ceny karnetu rodzinnego?",
      "count": 7,
      "last_seen_at": "2026-08-19T18:04:00Z"
    }
  ]
}
```

- Built exclusively from `ConversationRecord` rows with `outcome =
  "insufficient_information"` in the tenant's own data for the given range
  (FR-027, FR-029) — grouped by `normalized_question`
  (`domain/question_normalization.py`, research.md §6), ordered by `count`
  descending, ties broken by `last_seen_at` descending.
- `example_question` is the raw `question` text of the most recently seen
  row in that normalized group (case/punctuation-preserved, for
  readability) — never a fabricated or LLM-generated paraphrase.
- Zero insufficient-information conversations in range → `200` with
  `"items": []` (FR-020-equivalent empty-result guarantee, spec.md Edge
  Cases).

## New: `GET /api/v1/admin/analytics/questions`

Identical shape and query parameters to `knowledge-gaps` above, with one
difference: grouped and ranked across **all** outcomes in range, not only
`insufficient_information` (FR-030).

```json
{
  "range": {"start": "2026-07-21T00:00:00Z", "end": "2026-08-20T00:00:00Z"},
  "items": [
    {
      "normalized_question": "jakie sa godziny otwarcia",
      "example_question": "Jakie są godziny otwarcia?",
      "count": 23,
      "last_seen_at": "2026-08-20T09:12:00Z"
    }
  ]
}
```

No LLM summarization or semantic clustering is used by either grouping
endpoint (FR-028; constitution "No LLM analytics processing" non-goal) —
both are exact/normalized-text `GROUP BY` queries.
