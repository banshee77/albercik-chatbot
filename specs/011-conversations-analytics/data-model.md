# Phase 1 Data Model: Conversations & Analytics

One new table, `conversation_records`, added to
`src/shiruno/persistence/models.py` (research.md §2, §12). No existing
table is altered — `UsageRecord` is explicitly left untouched (research.md
§2).

## ConversationRecord (new)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Uuid` | PK, `default=uuid.uuid4` | |
| `tenant_id` | `Uuid` | `NOT NULL`, FK → `tenants.id` | Server-resolved only (research.md §4) — never client-supplied. |
| `request_id` | `Uuid` | `NOT NULL`, unique | Same value already generated in `chat.py::post_chat` and threaded through `ask_question()`/`_record_usage()`; non-authoritative correlation key back to `UsageRecord`, not queried at read time (research.md §2). |
| `question` | `Text` | `NOT NULL` | The visitor's submitted question, verbatim. |
| `normalized_question` | `Text` | `NOT NULL` | `domain/question_normalization.py::normalize_question(question)` (research.md §6) — lowercase, whitespace-collapsed. |
| `outcome` | `Enum(ConversationOutcome)` | `NOT NULL` | Mirrors `ask_question.Outcome` exactly: `grounded`, `insufficient_information`, `out_of_scope`, `unavailable`, `small_talk`. |
| `answer` | `Text` | `NOT NULL` | The exact public answer text shown to the visitor. |
| `sources` | `JSONB` | nullable | `[{"document_id": "...", "label": "..."}, ...]` snapshot at answer time, only ever populated for `grounded` (FR-005, FR-010); `NULL` otherwise. |
| `safe_failure_category` | `Enum(FailureCategory)` | nullable | Only set when `outcome = unavailable`: `provider_error`, `budget_exceeded`, `kill_switch`, `concurrency_limit` (research.md §5). `NULL` for every other outcome. |
| `provider_name` | `Enum(ProviderName)` | nullable | Reuses the existing `ProviderName` enum from `persistence/models.py`. Populated only when a real provider call was attempted (research.md §5); `NULL` for `small_talk`, `out_of_scope`, and the zero-chunk `insufficient_information` case. |
| `provider_model` | `String` | nullable | Paired with `provider_name`. |
| `input_tokens` | `Integer` | nullable | Copied from the same `LLMResult` that produced the answer, when applicable. |
| `output_tokens` | `Integer` | nullable | Same. |
| `provider_metrics` | `JSONB` | nullable | Verbatim copy of whatever `_record_usage()` also wrote to the corresponding `UsageRecord` row — opaque, never branched on (matching `UsageRecord.provider_metrics`'s own existing contract). |
| `latency_ms` | `Integer` | `NOT NULL` | End-to-end application processing time for the whole request (research.md §9) — always present, even for `small_talk`/`out_of_scope`/rejected-before-LLM `insufficient_information`. |
| `created_at` | `DateTime(timezone=True)` | `NOT NULL`, `server_default=func.now()` | |

```python
class ConversationOutcome(enum.StrEnum):
    grounded = "grounded"
    insufficient_information = "insufficient_information"
    out_of_scope = "out_of_scope"
    unavailable = "unavailable"
    small_talk = "small_talk"


class FailureCategory(enum.StrEnum):
    provider_error = "provider_error"
    budget_exceeded = "budget_exceeded"
    kill_switch = "kill_switch"
    concurrency_limit = "concurrency_limit"


class ConversationRecord(Base):
    __tablename__ = "conversation_records"
    __table_args__ = (
        Index("ix_conversation_records_tenant_id_created_at", "tenant_id", "created_at"),
        Index(
            "ix_conversation_records_tenant_id_outcome_created_at",
            "tenant_id", "outcome", "created_at",
        ),
        Index(
            "ix_conversation_records_tenant_id_normalized_question",
            "tenant_id", "normalized_question",
        ),
        UniqueConstraint("request_id", name="uq_conversation_records_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[ConversationOutcome] = mapped_column(
        Enum(ConversationOutcome, name="conversation_outcome",
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    safe_failure_category: Mapped[FailureCategory | None] = mapped_column(
        Enum(FailureCategory, name="conversation_failure_category",
             values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    provider_name: Mapped[ProviderName | None] = mapped_column(
        Enum(ProviderName, name="provider_name", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    provider_model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`provider_name`'s `Enum` reuses the *existing* `provider_name` Postgres
enum type (already created by the initial-schema migration for
`UsageRecord`) — the new column just references the same type, no new
enum type for that column.

### Lifecycle rules

- A `ConversationRecord` is written exactly once, at the end of a chat
  request that reached one of the five outcomes, and is never updated
  afterward (write-once/immutable — there is no supported operation that
  mutates an existing row).
- `sources` is populated only for `outcome = grounded` and is a frozen
  snapshot: it is never recomputed from current `KnowledgeDocument` state,
  so a later replace/delete of the referenced document does not change or
  invalidate a historical conversation's recorded evidence (FR-010, edge
  case in spec.md).
- `safe_failure_category` is populated only for `outcome = unavailable`;
  `NULL` for every other outcome.
- `provider_name`/`provider_model`/`input_tokens`/`output_tokens`/
  `provider_metrics` are, like `sources`, a frozen snapshot of the actual
  provider call made for this specific request — never re-read from
  `config.Settings` (`LLM_PROVIDER`, `ANTHROPIC_MODEL`, `OLLAMA_MODEL`) at
  analytics read time. A later change to the deployment's configured
  provider or model does not rewrite, reinterpret, or retroactively
  relabel any already-written row (research.md §2a); each row keeps
  showing whichever provider/model genuinely answered it.
- `provider_name`/`provider_model`/`input_tokens`/`output_tokens`/
  `provider_metrics` are populated only when a real provider call was
  attempted for this request (grounded; the `result.supported is False`
  flavor of `insufficient_information`; and the `provider_error` flavor of
  `unavailable`) — `NULL` for `small_talk`, `out_of_scope`, the
  zero-chunk `insufficient_information` case, and the `budget_exceeded` /
  `kill_switch` / `concurrency_limit` flavors of `unavailable` (no call was
  ever attempted in those cases).
- `latency_ms` is always present regardless of outcome.

## Relationships (target state)

```text
Tenant (1) ──< ConversationRecord (many)          [new]
```

No relationship is modeled to `UsageRecord` beyond the non-authoritative
`request_id` correlation value (research.md §2) — no foreign key, no ORM
`relationship()`, since it is deliberately never queried through at read
time. `UsageRecord` itself gains no column, no backfill, and no new read
path from this feature (research.md §2a) — it remains exactly what it was
before Feature 011.

Likewise, no relationship is modeled to `KnowledgeDocument` — `sources` is
a plain `JSONB` snapshot, not a foreign key or join target, precisely so
that a later replace/delete of the referenced document cannot alter or
invalidate it (research.md §2a). `list_conversations()`,
`get_conversation()`, and every `conversation_analytics.py` query read
only `ConversationRecord`'s own columns; none of them ever joins to
`KnowledgeDocument` or `UsageRecord` to "fill in" or reconstruct a value.

## Cross-cutting rules

- `tenant_id` is always the server-resolved public reference tenant
  (`config.Settings.PUBLIC_CHAT_TENANT_SLUG`, default `"albertos"`) —
  never derived from, or influenced by, any client-supplied value
  (constitution Principle II).
- No `tenant_id` semantics from Feature 009/010 are altered.

## Migration plan (Alembic)

One migration (research.md §12), additive, no backfill:

1. **`add_conversation_records`**
   - `CREATE TYPE conversation_outcome AS ENUM (...)`
   - `CREATE TYPE conversation_failure_category AS ENUM (...)`
   - `CREATE TABLE conversation_records (...)` with all columns above,
     `tenant_id` FK to `tenants.id`, `provider_name` reusing the existing
     `provider_name` enum type.
   - Three composite indexes (`tenant_id, created_at`;
     `tenant_id, outcome, created_at`; `tenant_id, normalized_question`)
     plus the `request_id` unique constraint.
   - **Downgrade**: drop the table, then drop both new enum types.

This migration touches no existing table and requires no backfill —
`conversation_records` has no historical rows by construction (research.md
§12).
