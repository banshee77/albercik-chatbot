# Phase 0 Research: Conversations & Analytics

Every decision below resolves an item the spec explicitly left to planning
(conversation/usage data model relationship, transaction/failure semantics,
public-tenant resolution, pagination style) or a gap discovered while
reading the current implementation (`src/shiruno/`) that this feature's
requirements depend on. No `NEEDS CLARIFICATION` markers remain in
`plan.md`'s Technical Context.

## 1. Which requests actually reach a persistable outcome today

**Finding**: Tracing `api/routers/chat.py` → `application/ask_question.py`
shows the request pipeline has two structurally different kinds of
rejection:

- **Pre-outcome rejections** — request-body-size (`api/deps.py::
  require_bounded_request_body`), question-length (`ChatRequest`'s Pydantic
  validator), and rate limiting (`infra/rate_limit.py::check_and_increment`,
  which raises `RateLimitedError`) — all happen *before* `ask_question()`
  ever returns a value, or before it is even called. None of these produce
  an `AskQuestionResult`; they propagate as `AppError` subclasses straight
  to the generic exception handler, bypassing `ChatResponse` entirely.
- **Outcome-classified results** — everything from the LLM kill switch
  onward returns a real `AskQuestionResult` with one of the five outcomes
  (`grounded`, `insufficient_information`, `out_of_scope`, `unavailable`,
  `small_talk`), including budget-exceeded, kill-switch-off,
  concurrency-limit-full, and LLM-provider-failure, which all already map
  to `outcome="unavailable"` today.

**Decision**: Persist a `ConversationRecord` only for the second category —
exactly the resolution the Clarifications session settled (spec.md
FR-001/FR-001a). Pre-outcome rejections never reach `record_conversation()`
at all; there is no code path that would need to suppress them.

**Rationale**: Matches the spec's explicit scope boundary and avoids
turning conversation storage into a write target reachable by traffic that
never got authorized to consume any real resource in the first place —
consistent with Cost Safety (Principle X) applying to *any* new public
write surface, not only paid-provider calls.

## 2. Conversation ↔ UsageRecord relationship: snapshot, not backfill

**Finding**: `UsageRecord` predates `Tenant` by multiple features (it
exists since the original MVP) and is written for *two* purposes that a
naive `tenant_id` backfill would conflate:

1. Per-request accounting (one `embedding`-kind row and, for a
   real LLM call, one `llm`-kind row, correlated by `request_id`).
2. `infra/budget.py::check_llm_budget`'s hourly Anthropic-usage count,
   which is deliberately **platform-wide**, not tenant-scoped — Cost
   Safety (Principle X) is an anti-runaway-spend control, not a
   per-tenant billing feature, and must stay that way.

Backfilling `tenant_id` onto every historical `UsageRecord` row (Option A
from spec planning) would require guessing ownership for rows written
before `Tenant` existed at all, for purposes (health-check smoke calls,
early manual testing) that have no real tenant to attribute to — a far
riskier backfill than Feature 009's, which only had to backfill rows that
were unambiguously Albertos's.

**Decision**: `ConversationRecord` stores its own direct snapshot of the
operationally-relevant fields — `provider_name`, `provider_model`,
`input_tokens`, `output_tokens`, `provider_metrics`, `latency_ms`, and (for
`unavailable`) a `failure_category` — captured at write time from
`AskQuestionResult`, plus `request_id` as a non-authoritative correlation
key back to `UsageRecord` for any future manual cross-reference.
`UsageRecord` itself gains no new column and needs no migration or
backfill.

**Rationale**: This is Option C (hybrid) from the spec's Data Model
Direction, resolved concretely: tenant-scoped usage/provider visibility
(FR-031, FR-036) is satisfied because `ConversationRecord.tenant_id` is the
*only* source of truth queried for admin-facing usage figures — no runtime
join to `UsageRecord`, and no historical `UsageRecord` row (all of which
predate this feature) is ever reachable through a tenant-scoped endpoint.
Small-talk's "zero token usage, zero provider attribution" requirement
(FR-008, FR-026) falls out for free: `ask_question()`'s small-talk branch
never populates those `AskQuestionResult` fields, so the snapshot is
naturally empty — no special-casing needed anywhere in the analytics
queries.

**Alternatives considered**: Option A (add `tenant_id` to `UsageRecord`,
backfill) — rejected for the historical-ambiguity and scope-creep reasons
above; it would also entangle this feature's migration with the
platform-wide budget query, which must never become accidentally
tenant-filtered. Option B (pure foreign-key reference, `usage_record_id` on
`ConversationRecord`, no snapshot) — rejected because a grounded request
produces *two* `UsageRecord` rows (embedding + LLM) sharing one
`request_id`, so a single FK can't unambiguously represent "the usage for
this conversation" without a join and a `provider_kind` filter on every
read; snapshotting once at write time is simpler and avoids that
per-query disambiguation (Principle XIII).

## 2a. Every recorded field is an immutable, at-write-time snapshot

**Decision**: `sources`, `provider_name`, `provider_model`, `input_tokens`,
`output_tokens`, `provider_metrics`, and `safe_failure_category` on
`ConversationRecord` are captured exactly once, at the moment the row is
written, from data `ask_question()` already computed for *that specific
request*. None of them is ever recomputed, re-derived, or rewritten
afterward — there is no update path for an existing `ConversationRecord`
at all (data-model.md "Lifecycle rules": write-once/immutable). In
particular:

- **Sources vs. current `KnowledgeDocument` state**: `sources` is a frozen
  `(document_id, label)` snapshot of what actually grounded the answer at
  that moment. `get_conversation()`/`list_conversations()` read this
  column directly and never join to, or re-query, `KnowledgeDocument` to
  "refresh" it. A document later replaced (feature
  010-knowledge-base-admin) or soft-deleted has no effect whatsoever on a
  conversation recorded before that change — the historical label and id
  remain exactly as they were, even though `GET /documents/{id}` for that
  same id would now return `404` (FR-010).
- **Provider/model vs. current configuration**: `provider_name` and
  `provider_model` are copied from the actual `LLMResult`/provider call
  made for that request, the same values already written to that
  request's `UsageRecord` row — never re-read from
  `settings.LLM_PROVIDER`/`ANTHROPIC_MODEL`/`OLLAMA_MODEL` at analytics
  read time. If a deployment later switches `LLM_PROVIDER` from `ollama`
  to `anthropic`, or changes `OLLAMA_MODEL`, every `ConversationRecord`
  written before that change keeps showing the provider/model that was
  genuinely active when it was answered; nothing retroactively rewrites
  or reinterprets it.
- **`UsageRecord` itself**: unchanged by this feature in every sense — no
  new column, no backfill, no new read path either. Analytics/detail
  endpoints are satisfied entirely from `ConversationRecord`'s own
  columns (research.md §2); `UsageRecord` is never queried, joined, or
  read by any endpoint this feature introduces.

**Rationale**: This is what makes "historical analytics" honest —
FR-010's requirement that a conversation's evidence "remain historically
stable" only holds if *every* operationally-relevant field follows the
same rule, not sources alone. Treating write-time capture as the single,
uniform mechanism for all of these fields (rather than snapshotting some
and re-deriving others) keeps the guarantee simple to state, simple to
verify by reading `record_conversation.py` once, and simple to test.

**Testing implication**: an automated test must prove — not merely
assert by construction — that (1) recording a grounded conversation, then
replacing or deleting the document it cited, leaves that conversation's
`sources` unchanged when re-fetched; and (2) two conversations recorded
with different `provider_name`/`provider_model` values (simulating a
provider/model change between them) each continue to report their own
originally-recorded values via both the list and detail endpoints,
regardless of whatever `LLM_PROVIDER`/model the test's current app
instance happens to be configured with.

## 3. Recording must not risk the request's own transaction

**Finding**: `persistence/database.py::get_session` runs one transaction
per request — it commits once, after the route returns successfully, and
rolls back the *entire* transaction on any propagated exception.
`ask_question()` already writes `UsageRecord` rows via `session.flush()`
(not `commit()`) earlier in the same transaction. If `record_conversation()`
raised and that exception propagated out of `post_chat()`, two things would
go wrong at once: the visitor would receive a `500` instead of their
already-computed answer (violating FR-003), and the `get_session()`
rollback would also discard the `UsageRecord` rows already flushed for this
same request — a recording bug would silently corrupt cost/usage
accounting too.

**Decision**: `record_conversation()` first calls `resolve_public_tenant()`
(research.md §4) — a plain, non-mutating `SELECT` that needs no
transactional isolation of its own. Only once a tenant is actually
resolved does it open `session.begin_nested()` (a PostgreSQL `SAVEPOINT`),
nested *within* the same outer, per-request transaction `get_session()`
already opened — not a second session, connection, queue, or background
worker of any kind — and issue the `ConversationRecord` insert inside it.
The exact semantics:

- The `ConversationRecord` insert is issued on the request's existing
  session/connection, inside a `SAVEPOINT`, only after `resolve_public_
  tenant()` has already returned a valid tenant (a missing/inactive tenant
  short-circuits before any `SAVEPOINT` is even opened — see §4).
- If it succeeds, the savepoint is released (not committed on its own —
  a `SAVEPOINT` has no independent durability); the row becomes durable
  only later, together with everything else in the request, when
  `get_session()` issues the single outer `COMMIT` after `post_chat()`
  returns successfully.
- If it fails for any reason, only that `SAVEPOINT` is rolled back
  (`ROLLBACK TO SAVEPOINT`); the outer transaction is left exactly as it
  was immediately before the nested block started — still open, still
  valid, still holding any `UsageRecord` rows already flushed earlier in
  this same request — and execution continues normally from there.
- The call site in `chat.py` wraps the call in `try`/`except Exception`,
  logs via `logger.exception(...)` with only `request_id` as context
  (never `question`/`answer` content — FR-004, FR-038), and always
  proceeds to build and return the `ChatResponse` regardless of outcome.
- The outer transaction itself is never rolled back, retried, or replaced
  by this mechanism — a recording failure changes nothing about how the
  rest of the request's transaction behaves, it only removes the one
  `ConversationRecord` row that failed to insert.

In short: **`ConversationRecord` is committed or rolled back together with
the rest of the request's transaction, never independently.** The
`SAVEPOINT` only isolates the *failure*, not the row's durability — a
successful `ConversationRecord` still depends on the outer `COMMIT`
succeeding, exactly like every other row written during the request.

**Rationale**: This is the standard SQLAlchemy pattern for "this one write
may fail independently of the rest of the transaction" and requires no
second database session or connection, no message queue, and no
async/background worker — directly satisfying the spec's "primary chat
behavior remains authoritative" requirement (FR-003) and its "must not
silently swallow failures without logging" requirement (FR-004)
simultaneously, using only a mechanism the existing single-session,
single-transaction-per-request architecture already supports.

**Alternatives considered**: A separate, independently-committed
connection/transaction for `record_conversation()` — rejected as
unnecessary complexity (a second connection to write one row) when a
savepoint on the existing connection achieves the same isolation with far
less code. Fire-and-forget via a background task — rejected; it would
still need the same failure-isolation reasoning, adds a new execution
model (Principle XIII forbids introducing one for a single feature), and
this deployment has no task queue.

## 4. Resolving the public reference tenant

**Finding**: The public `/chat` endpoint has never resolved any tenant at
all — `persistence/repositories.py::search_similar_chunks` has no
`tenant_id` filter (public multi-tenant routing is explicitly out of scope
for this feature, per the spec's Assumptions and the constitution's own
Principle II Rule 10 deferral of Knowledge/Conversations/Usage). Nothing in
retrieval needs to change.

**Decision**: Add one new setting, `PUBLIC_CHAT_TENANT_SLUG: str =
"albertos"`, to `config.Settings`. A new, small, independently testable
function, `application/resolve_public_tenant.py::resolve_public_tenant(
session, *, slug: str) -> Tenant | None`, is the single place this
resolution ever happens. Its contract is exhaustively fail-closed:

- **Exists check**: `SELECT` the `Tenant` row by `slug` — the exact
  configured value, nothing else.
- **Active check**: if found, `tenant.status` MUST equal
  `TenantStatus.active`; an inactive tenant is treated identically to a
  missing one (same as `api/deps.py::get_current_tenant`'s existing
  admin-auth pattern — an inactive tenant is indistinguishable from a
  nonexistent one).
- **No fallback**: there is no `.first()`, no "pick any tenant," no
  default-to-earliest-created — an unmatched or inactive slug returns
  `None`, full stop. If more than one tenant somehow shared the configured
  slug, the table's existing `UNIQUE` constraint on `slug`
  (`persistence/models.py::Tenant`) makes that structurally impossible
  regardless.
- **No auto-create**: this function only ever reads; it never constructs a
  `Tenant` row, at request time or otherwise. Provisioning the public
  reference tenant remains exclusively `cli.py create-tenant`'s job, as
  today.
- **No client influence**: `slug` is always `settings.PUBLIC_CHAT_TENANT_SLUG`
  — server configuration only. Nothing in `ChatRequest` is read by this
  function or by anything that calls it; the public request schema does
  not change (FR-039 unchanged by this decision).
- **Fails closed, safely**: `resolve_public_tenant()` never raises for a
  missing/inactive tenant — it returns `None`, a clean, explicit "not
  available for recording" signal. `record_conversation()` (research.md
  §3) calls it *before* opening its `SAVEPOINT`; when it returns `None`,
  `record_conversation()` logs a single `logger.warning(...)` line naming
  only the configured slug (safe, non-sensitive server configuration, not
  visitor content) and returns immediately — no insert is attempted, since
  there is no valid tenant to attribute a `ConversationRecord` to in the
  first place.

**Crucially, this is a recording-subsystem concern only — it does not gate
the public chat response.** `ask_question()` and the `ChatResponse` the
visitor receives are completely unaffected by whether the public reference
tenant resolves; a misconfigured/missing/inactive public tenant means this
one request's conversation simply isn't recorded (exactly the same
externally-invisible outcome as any other recording failure under
research.md §3 / spec.md FR-003), never that the visitor sees an
`unavailable` answer or any other change in chat behavior. Gating the chat
response itself on tenant resolution was considered and rejected — see
Alternatives below.

**Rationale**: Matches the spec's preferred direction exactly
("application composition/config knows the public reference tenant... the
server resolves Albertos tenant internally... `POST /api/v1/chat` remains
unchanged") and mirrors how the Feature 009 migration itself already
resolves Albertos by its fixed slug rather than a hardcoded id. Extracting
resolution into its own pure-ish function (one `SELECT`, no side effects)
makes every fail-closed rule above independently unit-testable without
needing to drive a full HTTP request per case. A plain indexed lookup by
unique slug is cheap enough to not need caching for this MVP's traffic
scale (Principle XIII — no premature optimization).

**Alternatives considered**: Making `POST /api/v1/chat` itself return the
existing `unavailable` outcome whenever the public reference tenant cannot
be resolved — rejected. This codebase's chat/retrieval path has never been
tenant-scoped by design (this section's own Finding, and constitution
Principle II Rule 10's explicit deferral of Knowledge/Conversations/Usage);
every existing chat contract test (`test_chat.py`,
`test_chat_small_talk.py`, etc.) seeds tenants with random, non-`albertos`
slugs and asserts on the resulting `ChatResponse` outcome, never on
tenant-recording side effects. Gating the response on tenant resolution
would silently turn every one of those into an `unavailable` response,
violating FR-040 ("every previously existing chat outcome MUST remain
unchanged by this feature") and User Story 7 for no requirement that
actually demands it — the spec's own FR-003 is explicit that a recording
concern (which tenant-resolution is one instance of) must never become a
chat-reliability concern. Silently falling back to *some* tenant (e.g. the
first row, or the KnowledgeDocument-owning tenant already implied by
retrieval) — rejected as the exact "arbitrary fallback" the requirement
forbids, and because it would misattribute a real tenant's conversation
data to a guess rather than a verified configuration value.

**Testing implication**: existing chat tests continue to need no changes —
they seed random-slug tenants, `resolve_public_tenant()` correctly returns
`None` for them, and recording is skipped exactly like any other
non-fatal recording failure, with the `ChatResponse` itself unaffected.
New tests must cover, independently: (1) configured tenant exists and is
active → resolves and a `ConversationRecord` is written; (2) configured
tenant missing → `resolve_public_tenant()` returns `None`, no record is
written, `ChatResponse` unaffected; (3) configured tenant exists but is
`inactive` → same `None`/no-record/unaffected-response outcome as (2); (4)
a second, differently-slugged tenant existing simultaneously never gets
selected as a fallback; (5) no `Tenant` row is ever created as a side
effect of any of the above, verified by asserting the tenant table's row
count is unchanged after the request.

## 5. Distinguishing *why* a request is "unavailable"

**Finding**: `infra/budget.py::check_llm_budget` already collapses three
distinct situations into one `BudgetCheckResult(allowed=False)`: the kill
switch (`LLM_ENABLED=false`), genuine budget exhaustion, and a failed
budget-check query (itself failing closed). `ask_question()` separately
returns `outcome="unavailable"` for a full concurrency guard and for a
caught `LLMProviderError` — four operationally distinct reasons, zero
distinguishing signal returned anywhere today.

**Decision**: Extend `BudgetCheckResult` with a `reason: Literal[
"kill_switch", "budget_exceeded"] | None` field (`None` when
`allowed=True`); a budget-check query failure maps to `"budget_exceeded"`
(both mean "we could not verify we're within budget, so we declined" —
distinguishing a DB hiccup from real exhaustion has no operational value
worth a fifth category). Extend `AskQuestionResult` with `failure_category:
Literal["provider_error", "budget_exceeded", "kill_switch",
"concurrency_limit"] | None = None`, populated at each `unavailable` return
site in `ask_question()` from information already available in that
branch. Every other field this decision adds to `AskQuestionResult` —
`provider_name`, `provider_model`, `input_tokens`, `output_tokens`,
`provider_metrics` — is populated identically to what the adjacent
`_record_usage()` call already writes to `UsageRecord` at that same call
site, so there is no new data to compute, only new fields to also return.

**Rationale**: Directly satisfies the Clarifications session's decision
(spec.md, "Unavailable detail" question) and FR-009. Because
`ask_question()` already *knows* the reason internally in each branch, this
is a small, additive, zero-risk change — no new branch, no new decision
logic, just surfacing an existing fact through the return value instead of
letting it stay implicit in which `if` branch executed.

**Note on `insufficient_information` with real usage**: the
`result.supported is False` branch (domain/prompting's structured
"context doesn't support an answer" decision) runs *after* a real,
successful LLM call and its `_record_usage(success=True, ...)` write — so
this specific `insufficient_information` case legitimately has real
token/provider data available, unlike the "zero chunks cleared the
relevance threshold" case (no LLM call at all). No special-casing is
needed: `AskQuestionResult`'s new fields are simply populated with
whatever is actually known at each return site, `None` otherwise, and the
conversation snapshot honestly reflects real cost incurred at every
outcome, not the outcome label alone.

## 6. Question normalization

**Decision**: A new pure function, `domain/question_normalization.py::
normalize_question(text: str) -> str`, applying only lowercasing and
whitespace collapsing (`" ".join(text.split()).lower()`) — no punctuation
stripping, no stemming, no semantic processing. Computed once at
conversation-write time and stored in an indexed `normalized_question`
column, so knowledge-gap and common-question aggregation is a plain `GROUP
BY normalized_question` with no runtime normalization cost.

**Rationale**: Directly satisfies FR-028 ("deterministic normalization...
MUST NOT merge questions using speculative semantic similarity") and the
constitution's Simplicity principle. Punctuation normalization was
explicitly offered as optional by the spec brief; omitting it keeps the
function trivially testable and avoids any locale-specific tokenization
decisions for Polish text (the assistant's actual language) that would add
complexity without a concrete requirement demanding it.

**Alternatives considered**: Any semantic/embedding-based grouping —
explicitly forbidden by FR-028 and the constitution's "No LLM analytics
processing" non-goal. Punctuation stripping — deferred; nothing in the
spec's acceptance scenarios requires it, and it is additive (a future
change to `normalize_question` alone) if real usage data later shows it's
needed.

## 7. Pagination and date-range defaults

**Decision**: Plain `limit`/`offset` query parameters on `GET
/admin/conversations`, with server-configured defaults
(`CONVERSATION_LIST_DEFAULT_PAGE_SIZE = 20`,
`CONVERSATION_LIST_MAX_PAGE_SIZE = 100` — a request for more than the
maximum is clamped, not rejected, matching this project's existing
tolerant-input style elsewhere). All three analytics endpoints accept
optional `start_date`/`end_date`; when omitted, both default to
`[now - ANALYTICS_DEFAULT_LOOKBACK_DAYS, now]` with
`ANALYTICS_DEFAULT_LOOKBACK_DAYS = 30` (matching the spec's own documented
Assumption).

**Rationale**: No pagination convention exists yet anywhere in this
codebase (`GET /documents` is intentionally unbounded, since a tenant's
document count is small — Feature 010 research.md never needed to solve
this). `limit`/`offset` is the simplest mechanism that satisfies "bounded,
regardless of client input" (FR-019) for admin-scale conversation volumes,
requires no opaque cursor encoding/decoding, and every response can still
report `total` for a client to build page controls — cursor-based
pagination's consistency-under-concurrent-insert advantage isn't a
meaningful concern here since conversation records are append-only and
administrators are not scrolling through live-updating feeds in this
backend-only MVP.

**Alternatives considered**: Cursor-based pagination — rejected as
unnecessary complexity (Principle XIII) for a bounded, admin-facing,
append-only dataset at this scale; can be introduced later without
changing the resource shape if real usage ever demands it.

## 8. Search over question text

**Decision**: Case-insensitive substring match via PostgreSQL's `ILIKE
'%term%'` against the raw `question` column (not `normalized_question`,
which strips information a search might want to match, like exact
capitalization intent — though matching is itself case-insensitive
either way).

**Rationale**: Satisfies FR-018's "free-text search over the question"
with zero new infrastructure — no full-text search extension, no external
search service, consistent with "do not overbuild BI infrastructure."
Acceptable at this feature's scale (Principle XIII); a `pg_trgm`
GIN index could be added later without an API change if search performance
ever becomes a real bottleneck, which is not a concrete current
requirement.

## 9. Latency aggregates

**Decision**: `latency_ms` on `ConversationRecord` is measured in
`chat.py::post_chat` as wall-clock time around the entire `ask_question(...)`
call (`time.monotonic()` start/stop) — genuinely end-to-end application
processing time for that request, per FR-033. The analytics summary
computes `AVG(latency_ms)`, and p50/p95 via PostgreSQL's native
`percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)` /
`percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)` — no new
dependency, no application-side sorting of potentially large result sets.

**Rationale**: `ask_question()` itself already measures narrower,
provider-specific latencies (`embed_latency_ms`, `result.latency_ms` from
the LLM provider) for `UsageRecord` — those remain available via
`provider_metrics`/existing `UsageRecord` rows for anyone who needs
provider-internal timing, but are never conflated with the end-to-end
figure this feature reports, per FR-033's explicit requirement to keep
these distinguished.

## 10. Router and application-module placement

**Decision**: Two new router files, `api/routers/conversations.py` and
`api/routers/analytics.py`, both using `APIRouter(prefix="/api/v1/admin",
...)` — the same prefix `admin.py` already establishes and whose own
docstring names as "the namespace future admin features build under."
Five new application-layer modules: `resolve_public_tenant.py`,
`record_conversation.py`, `list_conversations.py`, `get_conversation.py`,
and `conversation_analytics.py` (the last containing all three read-only
aggregate query functions — summary, knowledge gaps, common questions —
since they share date-range-bounding logic and are one cohesive read
capability, not three unrelated ones).

**Rationale**: Mirrors this codebase's established one-resource-per-router,
one-use-case-per-module conventions (Feature 009's `admin.py`, Feature
010's `documents.py` and its `application/*.py` siblings) rather than
inventing a new organizational pattern for this feature alone.

## 11. Audit logging

**Decision**: None of the five new read endpoints call
`infra/audit.py::log_audit_event`. `record_conversation()` (a public,
unauthenticated write, not an administrator action) does not either.

**Rationale**: FR-037 explicitly states administrator reads introduced by
this feature do not require per-row audit logging beyond existing
authentication/tenant-security auditing, and `log_audit_event`'s own
docstring already establishes that auditing covers administrator actions
(login, upload, delete, replace, reindex), never visitor messages — this
feature does not change that boundary.

## 12. Migration

**Decision**: One new, additive, fully reversible Alembic migration,
`add_conversation_records`, creating the `conversation_records` table (see
data-model.md) with its four indexes. No existing table changes, no
backfill — the table has no historical rows by definition, since
conversation recording did not exist before this feature.

**Rationale**: Matches this project's established one-focused-migration
pattern; simpler than every prior tenant-related migration in this
codebase precisely because there is nothing to backfill (§2 above).
