# Feature Specification: Conversational UX for Public Chat

**Feature Branch**: `007-conversational-chat-ux`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Extend the existing Albertos public chat widget from Feature 006 so that interactions feel more natural and conversational — deterministic small talk (greetings, thanks, goodbyes, courtesy, capability, and identity questions) handled without retrieval/LLM calls, a non-human 'Asystent Albertos' identity with an accessible local SVG avatar, and hiding technical source labels from the public widget — all while preserving the existing grounded-answerability guarantees, cost controls, and provider neutrality from Feature 006/004."

## Clarifications

### Session 2026-08-19

- Q: Which existing pre-LLM safeguards (rate limiting, LLM kill switch, budget check, concurrency guard, question-length/size validation) should a small-talk message still pass through before getting its deterministic reply? → A: Apply all existing safeguards unchanged — small talk still passes through HTTP/payload validation, question-length validation, rate limiting, the kill switch, budget check, and concurrency guard exactly like today; only the embedding/retrieval/LLM-call step is skipped and replaced by the deterministic reply.
- Q: Should a small-talk reply reuse an existing response outcome value, or should the API response contract gain a new outcome value for small talk? → A: Add a new `small_talk` outcome value to the response contract. This is an additive, backward-compatible change (no existing consumer asserts the outcome enum is exhaustive); it keeps `grounded` meaning strictly "answered from the RAG pipeline with grounding evidence," which matters for the source-metadata field and for future admin/observability tooling that needs to tell small talk apart from real grounded answers.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visitor exchanges natural small talk with the assistant (Priority: P1)

A visitor opens the chat widget and greets it ("Cześć"), asks what it can help with, or thanks it after getting an answer. Today each of these produces the same "I don't have enough information" response as an unanswerable factual question, which feels broken and undermines trust in the rest of the widget. Instead, the visitor should get a short, friendly, on-brand reply immediately.

**Why this priority**: This is the core problem the feature exists to fix — the most visible and most frequently hit interaction (nearly everyone greets or thanks the assistant), and the most damaging to first impressions when handled badly.

**Independent Test**: Send each of a greeting, a thanks, a goodbye, a courtesy question ("jak się masz?"), and a capability question ("w czym możesz mi pomóc?") to the chat and confirm each produces a short natural reply instead of the insufficient-information message, with no observable retrieval or LLM latency/cost.

**Acceptance Scenarios**:

1. **Given** the chat panel is open, **When** the visitor sends a greeting such as "Cześć" or "Dzień dobry", **Then** the assistant responds immediately with a short, friendly greeting appropriate to the Albertos site, and no sources section is shown.
2. **Given** the chat panel is open, **When** the visitor sends a thanks message such as "Dzięki!", **Then** the assistant responds with a short acknowledgment such as "Nie ma sprawy! 🙂".
3. **Given** the chat panel is open, **When** the visitor sends a goodbye such as "Do zobaczenia" or "Pa", **Then** the assistant responds with a short farewell.
4. **Given** the chat panel is open, **When** the visitor asks a courtesy question such as "Jak się masz?", **Then** the assistant responds with a short, natural reply that does not claim personal feelings in a misleading way and steers back toward how it can help.
5. **Given** the chat panel is open, **When** the visitor asks what the assistant can help with (e.g. "W czym możesz mi pomóc?" or "Co potrafisz?"), **Then** the assistant responds with a short summary of the topics it can help with (club, trainings, schedule, sections, coaches, exams, camps).

---

### User Story 2 - Visitor asks a real question phrased with a greeting or courtesy opener (Priority: P1)

A visitor writes "Cześć, o której są treningi początkujących w Wierzbinie?" or "Dzięki, a kiedy jest następny egzamin?" — a message that opens with small talk but asks a genuine factual question. The assistant must recognize that this is fundamentally a knowledge-base question and answer it through the existing grounded RAG pipeline, not respond with a generic greeting that ignores the actual question.

**Why this priority**: This is the primary safety-relevant scope boundary of the feature. Getting this wrong either breaks real user questions (small talk swallows a real question) or reopens the hallucination risk the feature must not touch. It must ship correctly alongside User Story 1 for the feature to be trustworthy.

**Independent Test**: Send messages that combine a greeting or thanks with a factual question and confirm the response is a grounded RAG answer (or the existing insufficient-information/out-of-scope outcome), not a small-talk reply, and confirm retrieval/LLM usage occurred as it would without the small-talk prefix.

**Acceptance Scenarios**:

1. **Given** the chat panel is open, **When** the visitor sends "Cześć, o której są treningi początkujących w Wierzbinie?", **Then** the message is routed through the normal RAG pipeline and the response is a grounded answer (or the standard insufficient-information message if the knowledge base doesn't support it), not a greeting reply.
2. **Given** the chat panel is open, **When** the visitor sends "Dzięki, a kiedy jest następny egzamin?", **Then** the message is routed through the normal RAG pipeline, not treated as a thanks message.
3. **Given** a factual Albertos question the knowledge base does not support, **When** the visitor submits it (with or without a greeting prefix), **Then** the assistant returns the existing insufficient-information outcome — the conversational layer never invents an answer to fill the gap.
4. **Given** a question unrelated to Albertos, **When** the visitor submits it, **Then** the assistant returns the existing out-of-scope outcome unchanged.

---

### User Story 3 - Visitor learns the assistant's identity without being misled (Priority: P2)

A visitor asks directly whether they're talking to a person, or asks what the assistant is. The assistant must clearly and immediately identify itself as a virtual Albertos assistant — never implying it is a human, an instructor, or a club employee — and the widget's own presentation (name, avatar) must reinforce this without leaning on internal technical jargon.

**Why this priority**: Honesty about the assistant's nature is a trust and ethical requirement, but it affects fewer interactions than the baseline small-talk and RAG-routing behavior in User Stories 1–2.

**Independent Test**: Ask "Czy jesteś człowiekiem?" and "Co to jest?" style questions and confirm the reply clearly states it is a virtual Albertos assistant, with no retrieval or LLM call. Separately inspect the widget chrome (launcher, message avatars) and confirm it presents as "Asystent Albertos" rather than technical terms like "AI chatbot", "LLM", or "RAG".

**Acceptance Scenarios**:

1. **Given** the chat panel is open, **When** the visitor asks "Czy jesteś człowiekiem?" or "Czy rozmawiam z człowiekiem?", **Then** the assistant responds that it is a virtual Albertos assistant and is not a human, without a retrieval or LLM call.
2. **Given** the chat panel is open, **When** the visitor asks "Kim jesteś?" or "Co to jest?", **Then** the assistant responds with a short, clear description of itself as the Albertos virtual assistant.
3. **Given** any state of the widget, **When** a visitor looks at the launcher button, the panel header, or an assistant message, **Then** the visible identity is a consistent public-facing name (e.g. "Asystent Albertos") with no primary use of "AI chatbot", "LLM", "RAG", or "Ollama" in the visitor-facing copy.

---

### User Story 4 - Visitor sees a recognizable assistant avatar (Priority: P3)

The chat launcher and assistant messages currently have no visual identity beyond generic UI chrome. A visitor should see a small, simple, on-brand avatar consistent with the site's modern, Japanese-inspired visual language, reinforcing that they're talking to "the Albertos assistant" rather than a faceless system — without resembling a literal robot, and without harming accessibility if the visitor uses a screen reader or the asset fails to load.

**Why this priority**: This is a polish/brand-trust improvement layered on top of the functional behavior in User Stories 1–3; the widget works correctly without it, but it strengthens the intended identity.

**Independent Test**: Load the widget, open the panel, and visually confirm an avatar appears on the launcher and/or assistant messages. Inspect the DOM with assistive-technology tooling to confirm the avatar graphic is hidden from screen readers while the assistant's name/identity remains announced. Simulate the avatar asset failing to load and confirm the widget still renders and functions normally.

**Acceptance Scenarios**:

1. **Given** the widget is loaded on any public page, **When** the visitor views the chat launcher, **Then** a small avatar/icon representing the Albertos assistant is visible, distinct from a literal robot depiction.
2. **Given** the chat panel is open, **When** an assistant message is displayed, **Then** the same avatar identity is presented consistently (on the launcher and/or next to assistant messages).
3. **Given** a screen reader is used to navigate the widget, **When** the reader encounters the avatar graphic, **Then** the graphic is treated as decorative (not announced redundantly) while the assistant's name/identity is still conveyed through accessible text.
4. **Given** the avatar asset fails to load for any reason, **When** the visitor uses the widget, **Then** the launcher, panel, and messaging continue to function normally with no broken-image artifacts or blocked interactions.

---

### User Story 5 - Visitor no longer sees technical source labels (Priority: P2)

Today, a grounded answer is followed by a line such as "Źródła: treningi.txt", exposing internal filenames to the public. A visitor should see just the answer, presented naturally, without this technical detail — while the underlying source metadata remains available in the API response for future administrative tooling.

**Why this priority**: This is a straightforward, low-risk presentation fix with clear user-visible impact (removing a jarring, unprofessional-looking technical artifact), but it doesn't affect whether the assistant behaves correctly, so it ranks below the core conversational-safety stories.

**Independent Test**: Ask a question that produces a grounded answer with sources and confirm the rendered widget shows only the answer text, with no filename, chunk identifier, or "Źródła"/"Sources" line anywhere in the visible UI, while a direct inspection of the underlying API response confirms source metadata is still present and unchanged.

**Acceptance Scenarios**:

1. **Given** a grounded answer is returned with one or more sources, **When** the widget renders the response, **Then** no source filenames, chunk identifiers, or a "Źródła"/"Sources" label are shown anywhere in the visible transcript.
2. **Given** the same grounded answer, **When** the raw API response is inspected directly (outside the widget), **Then** it still contains the existing source metadata, unchanged from Feature 006 behavior.

---

### Edge Cases

- What happens when a message is ambiguous between small talk and a real question (e.g. a bare "Cześć" with no follow-up in the same message)? → Treated as small talk; the visitor can ask their real question next, which is then routed normally.
- What happens when a message contains a greeting/courtesy phrase plus additional words that don't form a clear question (e.g. "Cześć, mam pytanie")? → Since no factual question is actually present, this may reasonably be treated as small talk or fall through to the existing RAG path where it will produce the existing insufficient-information/out-of-scope outcome; either behavior is acceptable as long as no fact is invented and no accidental answer to an unrelated question is produced.
- What happens when a visitor sends an empty message, only emoji, or only punctuation? → Existing Feature 006 input handling is unchanged; this feature does not alter validation of empty/whitespace input.
- What happens when a small-talk message is sent while a previous RAG request is still loading? → Existing Feature 006 in-flight-request handling (e.g. disabling the input, one outstanding request at a time) is unchanged and applies uniformly regardless of message type.
- What happens if a client sends a request with an explicit field trying to force a message to be treated as small talk or as a RAG question? → The classification must be determined solely server-side from the message content; any such field must be rejected or ignored consistent with the existing strict request-validation behavior (extra fields rejected).
- What happens when the visitor's message mixes Polish and English small talk phrases (e.g. "hi, cześć")? → At minimum the documented Polish and English phrase sets from this spec must be recognized individually; mixed-language messages are handled on a best-effort basis and must never fall back to inventing a factual answer.
- What happens if the avatar SVG fails to load (network hiccup, blocked asset, corrupted file)? → The widget continues to function fully; a graceful fallback (e.g. no image, or a simple text/initial-based placeholder) is shown instead of a broken-image icon, and no functionality is blocked.
- What happens to the "insufficient information" and "out of scope" response copy — does it also get a friendlier tone? → Out of scope for this feature; those response paths and their exact wording are unchanged from Feature 006/004 except that source-label rendering is removed from all response types where it previously appeared.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST classify each incoming chat message, before invoking retrieval or an LLM, as either small talk (greeting, goodbye, thanks, courtesy, capability question, or identity question) or a message requiring the existing RAG pipeline.
- **FR-002**: The system MUST recognize, at minimum, the Polish and English greeting, goodbye, thanks, courtesy, capability-question, and identity-question phrases and common variants described in this spec's examples, matched deterministically (not via an LLM-based classifier).
- **FR-003**: For a message classified as small talk, the system MUST return a short, friendly, deterministic, pre-defined response without invoking embeddings, retrieval, the configured LLM provider, or LLM usage/budget accounting.
- **FR-003a**: All existing pre-LLM request safeguards (HTTP/payload validation, question-length/size validation, rate limiting, the LLM kill switch, budget check, and concurrency guard) MUST continue to apply, unchanged, to every incoming message regardless of whether it is subsequently classified as small talk or routed to the RAG pipeline; small-talk classification only replaces the embedding/retrieval/LLM-call step, never the safeguards that precede it.
- **FR-004**: The system MUST NOT classify a message as small talk merely because it contains a greeting, thanks, or courtesy phrase; a message that also carries a distinguishable factual question or request about Albertos MUST be routed through the existing RAG pipeline.
- **FR-005**: The small-talk layer MUST NOT be able to answer, or attempt to answer, a factual question about Albertos from general knowledge; any message requiring factual grounding MUST go through the existing retrieval/RAG pipeline, including its existing insufficient-information and out-of-scope outcomes.
- **FR-006**: The system MUST NOT change retrieval, embeddings, chunking, similarity thresholds, context limits, the structured answerability contract, Ollama model selection, provider selection, LLM budget controls, rate limiting, concurrency controls, or prompt-injection protections as part of this feature.
- **FR-007**: When a visitor directly asks whether they are speaking with a human, or asks what the assistant is, the system MUST respond with a deterministic, non-LLM message that clearly identifies the assistant as a virtual Albertos assistant and explicitly states it is not a human.
- **FR-008**: The assistant's identity responses MUST NOT claim or imply the assistant is a human, a karate instructor, a club employee, or a specific real person.
- **FR-009**: The public-facing widget MUST present the assistant under a consistent, neutral, non-technical public identity (e.g. "Asystent Albertos") and MUST NOT primarily describe itself to visitors using technical terms such as "AI chatbot", "LLM", "RAG", or "Ollama".
- **FR-010**: The public widget MUST display a visual avatar for the assistant that is a local, lightweight asset (no external network request), simple and recognizable at small sizes, consistent with the site's existing visual language, and not a literal robot depiction.
- **FR-011**: The avatar MUST be marked as decorative for assistive technology (not redundantly announced), while the assistant's textual name/identity remains accessible to screen readers.
- **FR-012**: The widget MUST continue to function correctly (launcher, panel, messaging) if the avatar asset fails to load, with no broken-image artifact blocking interaction.
- **FR-013**: The public widget MUST NOT render source filenames, chunk identifiers, retrieval metadata, or any other internal source label in the visible message transcript, for any response type.
- **FR-014**: The backend response contract's existing fields and existing outcome values (`grounded`, `insufficient_information`, `out_of_scope`, `unavailable`), including any existing source metadata field, MUST remain unchanged in meaning and shape; hiding sources is a public-widget presentation change only, not a backend contract change. This feature MAY additively introduce a new `small_talk` outcome value to distinguish a deterministic small-talk reply from a RAG-grounded answer; that is the only backend response-contract change this feature is permitted to make.
- **FR-015**: Small-talk messages and their responses MUST be stored in the same client-side sessionStorage transcript mechanism used for RAG interactions from Feature 006, with no separate storage mechanism introduced for small talk.
- **FR-016**: The existing Feature 006 transcript-persistence behavior (transcript survives same-tab navigation between public pages; chat panel starts closed after a fresh page load; visitor can reopen the panel and see prior history) MUST continue to work unchanged.
- **FR-017**: The widget MAY present a short initial assistant greeting when the panel is first opened, consistent with the existing Feature 006 accessibility behavior; this greeting MUST NOT automatically move keyboard focus away from the visitor's expected input focus.
- **FR-018**: The message-classification decision MUST be made entirely server-side from the message content; a client MUST NOT be able to select or override the conversational-intent classification via a request field, and any such attempt MUST be rejected consistent with the existing strict request-validation (unrecognized fields rejected) behavior.
- **FR-019**: This feature MUST NOT introduce persistent server-side conversation memory or multi-turn contextual follow-up resolution (e.g. resolving "a dla początkujących?" against a prior turn); each message continues to be evaluated independently, consistent with Feature 006.
- **FR-020**: This feature MUST NOT introduce LangChain, LangGraph, or another orchestration framework, and MUST NOT introduce provider-specific (e.g. Anthropic- or Ollama-specific) logic into the application or domain layers as part of implementing small-talk classification.

### Key Entities

- **Conversational Intent**: A server-derived, non-persisted classification of an inbound chat message as one of: greeting, goodbye, thanks, courtesy, capability question, identity question, or "requires RAG pipeline". Derived solely from message content; never supplied or overridden by the client.
- **Small-Talk Response**: A short, deterministic, pre-authored reply (in Polish, matching the production site's language) associated with a conversational intent category, containing no retrieved knowledge-base content and no per-request generation.
- **Chat Message (existing)**: The visitor-submitted question, unchanged in shape from Feature 006/004; this feature only adds a pre-processing classification step ahead of existing handling.
- **Chat Response (existing)**: The existing backend response structure, including its outcome type and source metadata; unchanged by this feature for the existing outcome values (grounded, insufficient_information, out_of_scope, unavailable), except that the outcome type gains one new additive value, `small_talk`, returned when the classifier short-circuits before retrieval/LLM invocation. A `small_talk` response reuses the existing `answer` field for its reply text and an empty `sources` list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Visitors sending a common greeting, thanks, goodbye, courtesy message, capability question, or identity question receive a natural, on-topic reply instead of the "insufficient information" message, in 100% of the documented example phrases and their close variants.
- **SC-002**: None of the deterministic small-talk interactions in SC-001 measurably invoke retrieval, an LLM call, or LLM usage/budget accounting — verified by automated tests asserting zero such invocations for these message classes.
- **SC-003**: Messages that combine a greeting or courtesy opener with a genuine factual question about Albertos continue to receive a grounded answer (or the existing insufficient-information/out-of-scope outcome) in 100% of the documented example phrases, indistinguishable in accuracy from Feature 006 behavior without the small-talk prefix.
- **SC-004**: Zero grounded-answer responses rendered by the public widget contain a visible source filename, chunk identifier, or "Źródła"/"Sources" label, while the same underlying API responses retain their existing source metadata unchanged.
- **SC-005**: Visitors asking directly whether they are speaking to a human receive, within the same interaction, a clear statement that they are speaking with a virtual Albertos assistant, with no case in testing where the assistant claims or implies to be human.
- **SC-006**: The chat widget presents a consistent, recognizable assistant identity (name and avatar) across the launcher and assistant messages on all public pages, with the avatar accessible to screen-reader users as decorative and the widget remaining fully functional if the avatar fails to load.
- **SC-007**: The existing Feature 006 transcript persistence (survives same-tab navigation, panel starts closed on fresh load, history restorable on reopen) continues to pass its existing verification unchanged, including for small-talk messages.
- **SC-008**: 100% of this project's pre-existing automated test suite (security, cost-control, provider-neutrality, and RAG behavior tests) continues to pass unmodified in behavior, alongside the new tests added for this feature.
- **SC-009**: A small-talk message that would otherwise be rejected by an existing pre-LLM safeguard (rate limit, kill switch, budget check, concurrency guard, question-length/size validation) is still rejected the same way it is today — small-talk classification never bypasses these safeguards for any message.

## Assumptions

- The production public site's primary language is Polish; small-talk phrase coverage is scoped to Polish and English at minimum, per the feature description, using the specific example phrases given plus their most common everyday variants (e.g. "cześć"/"witam"/"hej" for greetings, "dzięki"/"dziękuję" for thanks, "pa"/"do zobaczenia"/"żegnaj" for goodbyes).
- "Deterministic" small-talk matching means explicit rule-/keyword-based matching (e.g. normalized phrase/keyword lookup), not statistical or model-based intent detection, per the feature description's explicit prohibition on an LLM-based classifier.
- Where a message's intent is genuinely ambiguous between small talk and a real question, falling through to the existing RAG pipeline (rather than to a small-talk reply) is the safer default, since the RAG pipeline already has a safe "insufficient information" fallback and cannot fabricate facts, whereas an incorrect small-talk classification could silently swallow a real question.
- The exact wording of each small-talk reply, and the exact visual design of the avatar, are implementation/content decisions to be finalized during planning and content authoring, consistent with the tone and examples given in this spec; this spec fixes required behavior, not final copy or pixel design.
- No new backend API endpoint or request field is required to implement server-side small-talk short-circuiting; it is implemented as a pre-processing step ahead of the existing chat request handling, reusing the existing request contract and response fields (`answer`, `sources`, correlation id) unchanged, with only one additive `small_talk` outcome value added to the response's outcome enum (see Clarifications).
- The "Asystent Albertos" identity name is a suggested default consistent with the feature description; the final visitor-facing name is a content decision that must remain non-technical and non-human-implying, but need not be the literal string "Asystent Albertos".
