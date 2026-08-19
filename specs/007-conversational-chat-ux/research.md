# Phase 0 Research: Conversational UX for Public Chat

Phase 0 output for `/speckit-plan`. Feature 007's source description was
unusually detailed and left no `NEEDS CLARIFICATION` markers in
`spec.md`'s Technical Context; the two open architectural decisions it did
carry (pipeline placement/safeguard scope, and response-outcome shape)
were already resolved during `/speckit-clarify` and are recorded in
`spec.md`'s Clarifications section. This document captures the remaining
implementation-level research needed before Phase 1 design: how to
classify a message, where exactly the code lives, and how to make the
avatar fail safely.

## §1 Classifier location and architecture

**Decision**: A new module, `src/albercik_chatbot/domain/small_talk.py`,
structurally mirroring the existing `domain/scope.py` (Albertos-scope
classifier): a small set of compiled `re.Pattern` tuples grouped by intent
category, plus a pure function that returns a classification result (or
`None` if the message doesn't match anything). `application/ask_question.py`
calls it as one new step in its existing strictly-ordered imperative
pipeline.

**Rationale**:
- `domain/scope.py` already establishes the project's precedent for
  "deterministic, keyword/regex-based, provider-free classification that
  runs before retrieval" — reusing that shape means no new architectural
  pattern needs to be learned, reviewed, or tested from scratch.
- Placing it in `domain/` (not `api/` or `application/`) matches the
  constitution's Separation of Concerns: classification of message intent
  is domain logic, not HTTP concern-handling or use-case orchestration.
  `application/ask_question.py` orchestrates *when* to call it, exactly as
  it already orchestrates *when* to call `is_albertos_scope`.
- Server-side placement (rather than duplicating logic in `chat.js`)
  satisfies the spec's Architecture constraint directly: the public
  website, direct API clients, and any future client all get identical
  small-talk behavior through the one existing `/api/v1/chat` endpoint,
  with zero new provider-specific logic anywhere near `application/` or
  `domain/`.

**Alternatives considered**:
- *LLM-based intent classification* — explicitly prohibited by the spec
  (Scope §1) and by Principle X (an LLM call for a decision this cheap and
  this deterministic is exactly the kind of avoidable cost/latency the
  constitution flags).
- *Classify client-side in `chat.js` before ever calling the API* —
  rejected: violates the spec's "preferred architectural direction is
  server-side handling so conversational behavior remains consistent for
  the public website, direct API clients, and future clients." A
  JS-only classifier would give a curl/Postman caller of `/api/v1/chat` a
  different (worse) experience than the widget, and would duplicate the
  reply-text bank in two languages/runtimes.
- *Classify inline in `api/routers/chat.py`* — rejected: the router today
  deliberately contains no business logic (`ask_question.py`'s docstring:
  "HTTP/payload validation and question length validation happen earlier
  ... this entire sequence is implemented as one strictly-ordered
  imperative function"); adding a second decision point in the router
  would split the pipeline's single source of truth about request
  ordering across two files for no benefit.

## §2 Matching strategy: whole-message anchors, not substring search

**Decision**: Each intent category is a set of regex patterns anchored to
match the **entire normalized message** (`^...$`, after trimming
whitespace and a small, explicit set of trailing punctuation/emoji), not a
substring-anywhere-in-the-message search. A message classifies as small
talk only when, after normalization, nothing is left unaccounted for by
the matched pattern (allowing a short, explicit list of harmless filler
additions per category, e.g. "cześć wszystkim", "dzięki bardzo", "dzień
dobry!"). If no whole-message pattern matches, the classifier returns
`None` and the message falls through to the existing, completely
unmodified `is_albertos_scope` → retrieval → LLM pipeline.

**Rationale**: This is the direct mechanism for FR-004 ("must not classify
a real Albertos question as small talk merely because it contains a
greeting or courtesy phrase"). `domain/scope.py`'s existing approach —
"does this message contain any off-topic marker anywhere" — is
deliberately substring-based and optimistic-by-default, which is exactly
right for *that* classifier (a single off-topic phrase anywhere in a mixed
message should reject the whole thing). Small talk needs the opposite
default: a greeting *prefix* on an otherwise-real question ("Cześć, o
której są treningi w Wierzbinie?") must NOT be swallowed by the small-talk
path, so the safe default here is "only short-circuit when the message
genuinely has no other content," which an anchored whole-message match
gives for free — no separate "does this also look like a question"
heuristic is needed, and no risk of the two classifiers disagreeing about
what "extra content" means.

**Alternatives considered**:
- *Substring match per category (mirroring `scope.py`)* — rejected: would
  fail the spec's own worked examples ("Cześć, o której jest trening w
  Wierzbinie?" contains "cześć" as a substring and would incorrectly
  short-circuit before the real question is ever seen).
- *Strip a recognized greeting/thanks prefix and route the remainder
  through the RAG pipeline as a modified question* — rejected as
  unnecessary complexity: the spec does not require preserving a factual
  question that follows a greeting in a *rewritten* form; the existing
  pipeline already receives and correctly evaluates the *full, original*
  message when the anchored small-talk match fails, so no rewriting step
  is needed at all — the fallthrough is the whole message, unmodified.
- *Fuzzy/edit-distance matching* — rejected: unnecessary complexity for a
  "simple, explicit, deterministic, and easily testable" requirement
  (spec Scope §1); the documented phrase list plus a modest set of
  hand-picked variants gives adequate coverage and is trivially testable
  with an exact input→output table, matching the project's existing
  `test_scope.py` style.

## §3 Response shape: additive `small_talk` outcome

**Decision** (already ratified in spec.md's Clarifications): `Outcome` in
`application/ask_question.py` and `ChatResponse.outcome` in
`api/schemas.py` both gain one new `Literal` member, `"small_talk"`. A
small-talk `AskQuestionResult`/`ChatResponse` reuses the existing `answer`
field for the canned reply text and the existing `sources` field with its
default empty list — no new field anywhere in the request or response
contract.

**Rationale**: Recorded in spec.md; repeated here because it directly
drives `data-model.md` and the API contract. Confirmed non-breaking by
inspecting `tests/contract/test_chat.py` and friends: every existing
assertion checks `body["outcome"] == "<specific value>"`, never an
exhaustive "is one of exactly these four" check, so adding a fifth Literal
member cannot fail any existing test.

## §4 Pipeline insertion point

**Decision**: Inside `ask_question()`, the new classification check is
inserted immediately after the concurrency guard is successfully acquired
and immediately before `is_albertos_scope(question)`:

```text
rate limit -> kill switch/budget -> concurrency guard ->
  [NEW] small-talk classification -> scope evaluation ->
  embedding/retrieval -> context limit -> LLM call -> usage accounting
```

**Rationale**: Per Clarifications, every existing pre-LLM safeguard must
keep applying unchanged to every message, small talk included — so the
new check cannot go *before* rate limiting/kill-switch/budget/concurrency
without violating SC-009. It must go *before* `is_albertos_scope` (rather
than after) because a small-talk message is a distinct outcome, not an
"out of scope" one — e.g. "Czy jesteś człowiekiem?" would otherwise risk
being misread as an off-topic question by a scope heuristic that has no
concept of small talk. Placing classification first also means the
embedding, retrieval, and LLM code paths are structurally unreachable for
any message the classifier matches — not just skipped by convention, but
never called, which is what makes SC-002/testing items 11-12
straightforward to prove with the existing fake-provider call-count spies
(research §8).

## §5 Reply-text bank

**Decision**: Canned Polish reply strings live as module-level constants
in `domain/small_talk.py`, one per intent category (greeting, goodbye,
thanks, courtesy, capability, identity), following the exact naming
convention `ask_question.py` already uses for `_OUT_OF_SCOPE_MESSAGE` /
`_INSUFFICIENT_INFORMATION_MESSAGE` / `_UNAVAILABLE_MESSAGE`. Content
matches the spec's worked examples verbatim where given (greeting, thanks,
identity) and follows the same tone for goodbye/courtesy/capability.

**Rationale**: Keeps all outcome-specific copy in one place, consistent
with the existing pattern, and makes the reply bank trivially unit-testable
independent of the HTTP layer.

## §6 Widget identity and avatar

**Decision**:
- Rename the panel's visible title from "Albertos AI" to "Asystent
  Albertos" in `base.html`; update `chat.js`'s in-flight status text
  (currently `"Albertos AI pisze odpowiedź…"`) to match.
- Add one new static asset, `public_site/static/img/assistant-avatar.svg`
  — a simple, non-robot, Japanese-inspired decorative mark consistent with
  the site's existing accent color (`--accent: #b3382c` in `site.css`).
  Exact artwork is a content decision (spec Assumptions), not fixed by
  this plan.
- Render the avatar via a fixed-size decorative `<span aria-hidden="true"
  class="chat-avatar">` whose **CSS `background-image`** points at the SVG
  — on the launcher button and, from `chat.js`, prepended to every
  assistant message bubble — rather than an `<img>` element.

**Rationale for CSS background-image over `<img>`**: This is the key
mechanism for FR-012 ("widget must continue to work correctly if the
avatar asset fails to load"). A `background-image` that 404s or fails to
load simply renders nothing — the element keeps its box, size, and any
CSS `background-color` fallback declared on the same rule, with no
browser-rendered "broken image" glyph and no `onerror` handler required.
An `<img src="...">`, by contrast, needs an explicit `onerror` listener in
`chat.js` to avoid a visible broken-image icon on failure — strictly more
code for an outcome the CSS approach gets for free, so it is the simpler
choice per Principle XIII.

**Alternatives considered**:
- *Inline `<svg>` markup (as the existing launcher speech-bubble icon
  already is)* — rejected for the *assistant identity* mark specifically:
  an inline SVG can never independently "fail to load" (it's part of the
  HTML document itself), so it can't exercise the failure-mode requirement
  FR-012 explicitly calls out, and duplicating a multi-path SVG inline
  into both `base.html` and every `chat.js`-rendered message bubble is
  more coupling than one external file referenced twice.
- *`<img>` with an `onerror` handler* — rejected per above; more code for
  an equivalent visual result.

## §7 Hiding source labels in the public widget

**Decision**: `chat.js`'s `renderMessage()` stops accepting/rendering a
`sources` parameter at all — the function's signature drops it, and the
one call site that currently passes deduplicated source labels for
`grounded` responses is changed to not pass them. `dedupeSourceLabels()`
is deleted (dead code once nothing renders its output). The backend
`sources` field is untouched — `handleResponse()` still receives it in the
parsed JSON body, it is simply never read for rendering purposes anymore.

**Rationale**: This is a pure subtraction in the presentation layer,
exactly matching FR-013/FR-014/spec Scope §6 ("this is a presentation-
layer change only... do NOT change the backend API contract solely to hide
sources"). Removing the dead `dedupeSourceLabels()` helper (rather than
leaving it unused) follows Principle XII/XIII — no unused code left behind
for a design that no longer calls it.

## §7a Widget must explicitly recognize the new `small_talk` outcome

**Decision**: `chat.js`'s `handleResponse()` gains one new explicit branch:
`if (body.outcome === "small_talk") { appendAndPersist("assistant",
body.answer, []); return; }`, alongside its existing `grounded`/
`insufficient_information`+`out_of_scope`/`unavailable` branches.

**Rationale**: `handleResponse()` (feature 006) is a closed switch, not a
defensive default — any `outcome` value it does not explicitly recognize
falls through to `showFallbackMessage()`, the same generic friendly-error
bucket used for network failures and malformed responses. Without this new
branch, every small-talk reply from the backend would incorrectly render
as "Coś poszło nie tak..." instead of the intended friendly reply,
silently defeating the entire feature at the last step. This is not
optional polish — it is required for SC-001/SC-002 to hold end-to-end
through the actual public widget, not just at the API layer (see
contracts/small-talk-classification-contract.md for the corresponding
wire-contract note).

## §8 Testing approach

**Decision**:
- **Classifier unit tests** (`tests/unit/test_small_talk_classifier.py`):
  a parametrized table of (input, expected category or `None`) pairs,
  mirroring `tests/unit/test_scope.py` exactly — including the spec's own
  worked "must NOT match" examples ("Cześć, o której jest trening w
  Wierzbinie?", "Dzięki, a kiedy jest następny egzamin?") as explicit
  negative cases.
- **Pipeline contract tests** (`tests/contract/test_chat_small_talk.py`):
  HTTP-level `TestClient` calls to `POST /api/v1/chat` for each small-talk
  category, asserting `response.json()["outcome"] == "small_talk"`, and —
  reusing the existing `fake_llm_provider`/`fake_embedding_provider`
  fixtures already wired into `test_app` (`tests/conftest.py`) —
  `fake_llm_provider.call_count == 0` and
  `fake_embedding_provider.embed_calls == []` after the request, plus a
  `session.query(UsageRecord).count()` check proving no usage row was
  created (mirroring how `out_of_scope` already behaves today). The same
  file proves rate limiting and the kill switch still apply to small-talk
  requests (SC-009), by reusing the exact test patterns already
  established in `test_chat_rate_limit.py`/`test_chat_kill_switch.py` but
  pointed at a small-talk message instead of a real question.
- **Regression proof** (SC-008): every existing `tests/contract/
  test_chat*.py` file is re-run unmodified — none of them is touched by
  this feature, since `ask_question.py`'s existing branches are not
  altered, only a new branch is inserted ahead of `is_albertos_scope`.
- **Widget tests**: `tests/contract/test_public_site_chat_widget.py`
  extended for the "Asystent Albertos" title, avatar element with
  `aria-hidden="true"`, and absence of "AI chatbot"/"LLM"/"RAG"/"Ollama"
  literal strings in visitor-facing markup; `tests/unit/
  test_chat_widget_client_script.py` extended with static-source
  assertions that no `"Źródła"` string literal remains reachable from any
  rendering branch in `chat.js`, and that avatar construction sets
  `aria-hidden`.

**Rationale**: Every technique here already exists in the codebase
(fake-provider call-count spies, static-source scanning, parametrized
classifier tables) — this feature needs zero new test infrastructure,
satisfying "must not require a real Ollama model, a GPU, Anthropic
credentials, or external network access" trivially, the same way the
existing suite already does.
