# Implementation Plan: Conversational UX for Public Chat

**Branch**: `007-conversational-chat-ux` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-conversational-chat-ux/spec.md`

## Summary

Add a deterministic, regex-based small-talk classifier as a new domain
module (`domain/small_talk.py`, mirroring the existing `domain/scope.py`
pattern) that `application/ask_question.py` consults immediately after the
existing rate-limit → kill-switch/budget → concurrency-guard safeguards and
before scope evaluation. A message whose entire normalized text matches a
greeting, goodbye, thanks, courtesy, capability, or identity pattern
short-circuits with a new additive `small_talk` outcome and a canned Polish
reply — never touching embeddings, retrieval, or the LLM provider. Any
message that also carries distinguishable factual content (the anchored
whole-message match simply fails) falls through to the existing,
completely unmodified scope/retrieval/LLM pipeline. On the public widget
side, `chat.js` gains an explicit `small_talk` branch in `handleResponse()`
so the new outcome renders its friendly reply instead of falling into the
existing generic-error fallback, stops rendering the sources line for
every outcome (presentation-only; the backend keeps returning `sources`
unchanged), gains
a small CSS-background-image assistant avatar (decorative, `aria-hidden`,
fails silently with no broken-image glyph) shown on the launcher and every
assistant message bubble, and the panel identity is renamed from
"Albertos AI" to "Asystent Albertos". This feature adds **one new backend
module, one new additive response-outcome value, one new static SVG asset,
and edits to five existing files** — no new dependency, no new endpoint, no
new database table, and zero changes to retrieval, embeddings, chunking,
prompting, provider selection, rate limiting, budget/kill-switch, or
concurrency logic.

## Technical Context

**Language/Version**: Python 3.14 (backend classifier + pipeline wiring,
unchanged runtime); vanilla ES2017+ JavaScript, no transpilation (widget
changes) — both already the project's established stack from features
001–006, no new language/runtime.

**Primary Dependencies**: None new. The classifier is plain Python `re`
(already used by `domain/scope.py`); the widget changes use the same
vanilla-JS/CSS approach as feature 006 — this feature adds no line to
`pyproject.toml`/`uv.lock`.

**Storage**: N/A new. No new table/column/migration — a `small_talk`
outcome response never creates a `UsageRecord` row (same as
`out_of_scope`/pre-retrieval `insufficient_information` today), and no
conversation state is persisted server-side (unchanged: `sessionStorage`
remains the only persistence, client-side, per FR-015/FR-016).

**Testing**: pytest + FastAPI `TestClient` (existing) using the existing
`fake_llm_provider`/`fake_embedding_provider` test doubles' `call_count`/
`embed_calls` spies to prove zero invocation for small talk (research.md
§8), plus the existing static-source-assertion pattern
(`tests/unit/test_chat_widget_client_script.py`) extended for the new
avatar/no-sources client behavior. No new test framework, no Node.js
runner, no browser-automation tool, no real Ollama/GPU/Anthropic
credentials/network access (spec's Testing requirements; SC-008).

**Target Platform**: Linux server, same Docker container/image as the
existing app (no new service, no new container).

**Project Type**: Single project (web service) — this feature extends the
existing `domain/`, `application/`, `api/`, and `public_site/` packages in
place; it does not add a package, a route, or a deployable unit.

**Performance Goals**: A small-talk reply is a pure in-process regex match
plus a constant lookup — no network, no DB write beyond what already
happens for `out_of_scope` today — so it is at least as fast as, and
categorically cheaper than, the existing `out_of_scope` path it sits next
to. No new performance target beyond "at least as fast as the pipeline
step it replaces."

**Constraints**: MUST NOT modify retrieval, embeddings, chunking,
similarity thresholds, context limits, the structured answerability
contract, Ollama model selection, provider selection, LLM budget controls,
rate limiting, concurrency controls, or prompt-injection protections (spec
FR-006, Constraints section). MUST NOT introduce an LLM-based intent
classifier (spec Scope §1). MUST NOT introduce LangChain, LangGraph, or any
orchestration framework (spec FR-020). MUST NOT change the backend request
contract or any existing response field/outcome value's meaning — only one
new additive outcome value, `small_talk`, is permitted (spec FR-014,
Clarifications). MUST keep every existing automated test passing unmodified
(spec SC-008).

**Scale/Scope**: 1 new Python module (`domain/small_talk.py`, on the order
of the size of `domain/scope.py` — a handful of compiled regex patterns per
intent category plus a reply-text bank); 1 new static SVG asset
(`public_site/static/img/assistant-avatar.svg`); 5 existing files edited
(`application/ask_question.py` — one new short-circuit branch;
`api/schemas.py` — one Literal value added; `public_site/templates/
base.html` — identity rename + avatar markup; `public_site/static/css/
site.css` — avatar styling; `public_site/static/js/chat.js` — new
`small_talk` response branch, remove source-line rendering, add avatar
rendering, rename in-flight status text);
several new/extended test files (unit classifier tests, contract pipeline
tests, markup/static-source tests). Zero new dependencies, zero new routes,
zero new database migrations.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applicability | Assessment |
|---|---|---|
| I. Security by Default | Applies | The small-talk reply bank is a fixed, developer-authored constant table — never derived from user input, retrieved documents, or LLM output — so there is no new untrusted-input surface. The widget's avatar/no-sources rendering changes continue to insert all LLM-derived `answer` text via `textContent` only (unchanged from feature 006). **Pass.** |
| II. Tenancy Posture | N/A | No tenant concept touched. |
| III. Secure RAG | Applies | The classifier is a pure keyword/regex gate that runs *before* retrieval and can only ever short-circuit to a fixed canned reply — it has no path to invent or paraphrase a factual claim, and it cannot suppress or alter the existing `insufficient_information`/`out_of_scope`/`grounded` decisions for any message it does not match (FR-004, FR-005). **Pass.** |
| IV. Secure Document Ingestion | N/A | No uploads in this feature. |
| V. LLM Provider Neutrality | Applies | The classifier and its reply bank live in `domain/`, import nothing from `providers/`, and never construct or call an LLM — they are strictly more provider-neutral than the pipeline step they sit beside. **Pass.** |
| VI. Embedding Provider Neutrality | Applies | Same reasoning as V — a `small_talk` outcome never calls `embed_query`/`embed_passages`. **Pass.** |
| VII. Cloud/Provider Neutrality | Applies | No cloud-specific service introduced; one new static SVG served from the existing container the same way every other static asset already is. **Pass.** |
| VIII. API Security | Applies | No new endpoint. The existing `ChatRequest` (`extra="forbid"`, single `question` field) is unchanged, so a client still cannot supply or override an intent/classification field (FR-018) — the new `small_talk` value is purely additive on the *response* side. **Pass.** |
| IX. Privacy and Logging | Applies | No new logging. A `small_talk` outcome deliberately creates no `UsageRecord` row (mirrors the existing `out_of_scope` path) — nothing about the small-talk classification itself is persisted server-side. **Pass.** |
| X. Cost Safety (NON-NEGOTIABLE) | Applies | Per Clarifications, small talk still passes through rate limiting, the kill switch/budget check, and the concurrency guard, unchanged — it only skips the embedding/retrieval/LLM-call step itself, which is strictly a cost *reduction*, never a bypass of any control. **Pass.** |
| XI. Testing Discipline (NON-NEGOTIABLE) | Applies | New unit tests for the classifier (parametrized, mirroring `test_scope.py`) and new contract tests proving `fake_llm_provider.call_count == 0` / `fake_embedding_provider.embed_calls == []` / no `UsageRecord` row for small talk, plus proof that rate limiting/kill-switch/budget still apply to small-talk requests (SC-009) — all via the existing pytest/`TestClient`/fake-provider stack, no live provider/GPU dependency. **Pass.** |
| XII. Engineering Quality | Applies | `domain/small_talk.py` follows the exact structure, docstring style, and compiled-regex-tuple pattern already established by `domain/scope.py` — no new abstraction invented for a single, simple classification concern. **Pass.** |
| XIII. Simplicity for MVP | Applies | No LLM-based classifier, no orchestration framework, no new provider abstraction, no new database table. The avatar's failure-safe behavior is achieved with a CSS `background-image` on a decorative `<span>` rather than any new JS error-handling machinery. **Pass.** |
| XIV. Approved MVP Technology Stack | Applies | Zero new technology introduced — reuses exactly Python `re`, FastAPI/Pydantic, and vanilla CSS/JS. **Pass — no Complexity Tracking entry needed.** |

**Gate result (pre-Phase-0)**: PASS, with **no deviation to justify** — this
feature introduces no new dependency, endpoint, or architectural layer;
Complexity Tracking is intentionally empty below.

**Post-Phase-1 re-check**: `research.md`, `data-model.md`,
`contracts/small-talk-classification-contract.md`, and `quickstart.md` were
produced without introducing anything beyond what the pre-Phase-0 table
above already assessed — no new dependency, no new database table, no new
provider/SDK, no new route, no change to any existing security/cost/rate-
limit control, and exactly one additive response-outcome value (already
accounted for under Principle VIII above). **Gate result: still PASS. No
new deviation introduced during design.**

**Post-implementation re-check (T035, Polish phase, all five user stories
complete)**: the table above was re-read against the final diff and holds
exactly as written, with no update needed. Verified directly against the
repository, not just re-asserted:
- `git diff --stat pyproject.toml uv.lock` — empty (Principle XIV: zero
  new dependency).
- No file under `alembic/` touched; `git diff --stat
  persistence/models.py` — empty (no new database table/migration).
- `git diff src/albercik_chatbot/api/routers/` — empty (no new endpoint).
- `git diff src/albercik_chatbot/api/schemas.py` — exactly one line
  changed: `ChatResponse.outcome`'s `Literal` gains `"small_talk"`; every
  other field/type in the file is byte-for-byte unchanged (Principle VIII;
  the one additive response-outcome value promised above, and nothing
  more).
- `domain/small_talk.py` imports only `re` and `typing` — no
  `providers/`, no LLM/embedding SDK import, at any point across User
  Stories 1–3 (Principles V/VI).
- Full suite: 386 (pre-feature baseline) → 499 tests, 100% passing;
  `ruff check`/`ruff format --check`/`mypy src tests`/`docker compose
  config` all clean (Principle XI).
**Gate result: still PASS. No deviation was introduced across
implementation — the Constitution Check performed before Phase 0 remains
accurate as the as-built description of this feature.**

## Project Structure

### Documentation (this feature)

```text
specs/007-conversational-chat-ux/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/             # Phase 1 output (/speckit-plan command)
│   └── small-talk-classification-contract.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Single project (existing pattern — extended in place, same as features 005/006)
src/albercik_chatbot/
├── api/
│   ├── routers/chat.py          # UNCHANGED — no new route, no new dependency wiring
│   └── schemas.py                # MODIFIED — ChatResponse.outcome Literal gains "small_talk"
├── application/
│   └── ask_question.py           # MODIFIED — one new short-circuit branch: classify → return
│                                  #   AskQuestionResult(outcome="small_talk", ...) before
│                                  #   is_albertos_scope(); Outcome Literal gains "small_talk"
├── domain/
│   ├── scope.py                   # UNCHANGED — existing Albertos-scope classifier, reused as-is
│   └── small_talk.py              # NEW — deterministic, whole-message-anchored regex
│                                  #   classifier + Polish reply-text bank (greeting, goodbye,
│                                  #   thanks, courtesy, capability, identity)
├── providers/, persistence/, infra/   # UNCHANGED — no provider, schema, or infra change
├── main.py                         # UNCHANGED
└── public_site/
    ├── router.py, models.py, filters.py, data/   # UNCHANGED
    ├── templates/
    │   └── base.html                # MODIFIED — panel title "Albertos AI" → "Asystent
    │                                 #   Albertos"; avatar markup added to launcher and panel
    │                                 #   header
    └── static/
        ├── css/site.css              # MODIFIED — `.chat-avatar` decorative background-image
        │                              #   styles (launcher + per-message), fallback
        │                              #   background-color, no layout dependency on the SVG
        │                              #   loading successfully
        ├── img/
        │   └── assistant-avatar.svg   # NEW — local, lightweight, non-robot decorative mark
        └── js/
            ├── site.js                 # UNCHANGED
            └── chat.js                 # MODIFIED — `handleResponse()` gains an explicit
                                         #   `small_talk` branch (renders `answer`, no
                                         #   sources); `renderMessage()` no longer appends a
                                         #   sources line for any outcome; adds a decorative
                                         #   avatar element to assistant message bubbles;
                                         #   in-flight status text no longer says "Albertos AI"

tests/
├── unit/
│   ├── test_scope.py                        # UNCHANGED
│   ├── test_small_talk_classifier.py         # NEW — parametrized whole-message classification
│   │                                          #   table (mirrors test_scope.py's style):
│   │                                          #   greetings/goodbyes/thanks/courtesy/
│   │                                          #   capability/identity → matched; combined
│   │                                          #   greeting+question messages → NOT matched
│   └── test_chat_widget_client_script.py      # MODIFIED — extended static-source assertions:
│                                               #   no "Źródła" string literal remains reachable
│                                               #   from any outcome branch; avatar element is
│                                               #   constructed with aria-hidden
├── contract/
│   ├── test_chat.py, test_chat_answerability.py, test_chat_no_client_override.py,
│   │   test_chat_rate_limit.py, test_chat_budget.py, test_chat_kill_switch.py,
│   │   test_chat_concurrency.py, test_chat_size_limits.py, test_chat_usage_accounting.py,
│   │   test_chat_provider_switch.py, test_chat_provider_failure.py,
│   │   test_chat_provider_parity.py, test_chat_ollama_default.py   # UNCHANGED — re-run as
│   │                                                                 #   the non-regression
│   │                                                                 #   proof (SC-008)
│   └── test_chat_small_talk.py               # NEW — HTTP-level contract tests: greeting/
│                                              #   thanks/goodbye/courtesy/capability/identity
│                                              #   → 200 + `outcome: "small_talk"` +
│                                              #   `fake_llm_provider.call_count == 0` +
│                                              #   `fake_embedding_provider.embed_calls == []`
│                                              #   + no new `UsageRecord` row; combined
│                                              #   greeting+question message → normal RAG path
│                                              #   unchanged; small talk still 429s under rate
│                                              #   limiting and still respects the kill switch
│                                              #   (SC-009)
└── contract/
    └── test_public_site_chat_widget.py        # MODIFIED — extended markup assertions:
                                                 #   "Asystent Albertos" panel title present;
                                                 #   avatar element present with aria-hidden;
                                                 #   no "AI chatbot"/"LLM"/"RAG"/"Ollama" string
                                                 #   in visitor-facing markup
```

**Structure Decision**: Single project, extended in place — this feature
adds exactly one new backend module (`domain/small_talk.py`) and one new
static asset; every other change is an edit to an existing file, mirroring
how features 005/006 extended the codebase additively rather than
introducing a new package or deployment unit. `public_site/` still imports
nothing from `domain/`, `application/`, or `providers/` directly — the
widget continues to reach the small-talk behavior exclusively through the
same public, unauthenticated `/api/v1/chat` HTTP boundary it already uses,
which is also what keeps this behavior consistent for direct API clients
and future clients (spec's Architecture constraint).

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

*No violations — this feature introduces no new dependency, endpoint, or
architectural layer beyond one small domain module and one additive
response-outcome value, both already justified inline in the Constitution
Check table above. Table intentionally omitted.*
