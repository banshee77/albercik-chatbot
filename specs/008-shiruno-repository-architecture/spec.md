# Feature Specification: Shiruno Repository & Product Architecture

**Feature Branch**: `008-shiruno-repository-architecture`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Feature 008 — Shiruno Repository & Product Architecture. Behavior-preserving repository/product architecture refactor that rebrands the reusable product from Albercik/albercik_chatbot to Shiruno ('Knowledge that answers.' / 'Turn your organization's knowledge into an assistant your customers can simply ask.'), makes the repository clearly distinguish reusable Shiruno platform code from Albertos-specific customer/reference website code, documents (without implementing) future Admin Platform and standalone Widget boundaries, and prepares the repository for Feature 009 — Admin Platform Foundation & Tenant Boundary — all while preserving every existing runtime behavior, API contract, RAG behavior, website behavior, test outcome, and evaluation baseline."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
-->

### User Story 1 - Existing customer behavior is completely unaffected (Priority: P1)

Albertos site visitors, and anything already integrated against the chatbot (the public website, the chat widget, admin document management, evaluation tooling), must experience zero behavior change. A visitor browsing the Albertos site and chatting with the assistant today must get identical answers, identical outcomes (`grounded`, `small_talk`, `insufficient_information`, `out_of_scope`, `unavailable`), identical source-hiding behavior, and identical performance characteristics after this refactor as before it — even though the code underneath has been reorganized and renamed.

**Why this priority**: This is a behavior-preservation refactor by explicit mandate. If anything a real user or existing integration depends on changes, the feature has failed regardless of how clean the new structure is.

**Independent Test**: Run the full existing automated test suite (unit, contract, integration) unmodified in assertion semantics against the refactored codebase and confirm it passes. Separately, exercise the public website and `POST /api/v1/chat` end to end (small talk, grounded answer, insufficient information, out-of-scope, unavailable) and confirm responses are unchanged from pre-refactor behavior.

**Acceptance Scenarios**:

1. **Given** the refactored repository, **When** the full existing automated test suite is run, **Then** every test that existed before the refactor still passes with its original assertion semantics intact (tests may move or be renamed for the new module paths, but must not be weakened to force a pass).
2. **Given** the refactored repository running the API and public website, **When** a visitor sends a chat message that previously produced a `grounded`, `small_talk`, `insufficient_information`, `out_of_scope`, or `unavailable` outcome, **Then** the same message produces the same outcome, the same source-hiding behavior in the public widget, and the same assistant identity/avatar presentation as before the refactor.
3. **Given** the refactored repository, **When** an administrator uses the existing document upload/list/delete admin API, **Then** authentication, authorization, and functional behavior are unchanged from before the refactor.
4. **Given** the refactored repository, **When** the existing evaluation tooling is run against `eval/questions.jsonl`, **Then** it runs successfully from its new location/import paths and produces the same benchmark outcomes as before the refactor.

---

### User Story 2 - A new engineer immediately understands the product boundary (Priority: P1)

A new engineer joining the project opens the repository for the first time. Within minutes of reading the README and browsing the top-level structure, they must understand: Shiruno is the reusable product/platform (chat API, RAG, retrieval, embeddings, LLM providers, persistence); Albertos is the first customer, implemented as a reference/example on top of that platform; and there is a clear line between code that is part of the reusable platform versus code that is specific to the Albertos reference implementation.

**Why this priority**: This is the core deliverable of the feature — an architecture and naming refactor whose entire purpose is comprehensibility. Without this outcome, the refactor has not achieved its goal even if all tests pass.

**Independent Test**: Give a new reader only the README and a directory listing (no other context) and ask them to identify (a) what Shiruno is, (b) what Albertos is, (c) which code they would touch to add a second customer website, and (d) which code they would touch to change RAG/retrieval behavior for every customer. Confirm they can answer correctly without additional explanation.

**Acceptance Scenarios**:

1. **Given** the root README, **When** a new engineer reads it, **Then** they can state that Shiruno is the reusable product/platform and Albertos is the first customer/reference implementation, including the product tagline and supporting message.
2. **Given** the repository's top-level structure, **When** a new engineer browses it, **Then** they can identify which directories contain reusable platform code versus Albertos-specific customer content without needing to read implementation code.
3. **Given** the README's architecture section, **When** a new engineer reads it, **Then** they can distinguish which architectural pieces exist today versus which are documented future direction (Admin Platform, standalone Widget), and understand that neither future piece is implemented yet.

---

### User Story 3 - Product naming is consistent across forward-looking materials (Priority: P2)

Anyone reading current code identifiers, package metadata, forward-looking documentation, or the README encounters the name "Shiruno" consistently wherever the reusable product is referenced, rather than a mix of "Albercik" and "Shiruno". Historical feature specs that documented past decisions under the old name remain untouched as historical record, except where they make a forward-looking claim that is now incorrect.

**Why this priority**: Naming consistency is what makes the rebrand real rather than cosmetic, but it is secondary to behavior preservation (User Story 1) and structural comprehensibility (User Story 2) — a naming-only pass without the architectural boundary would not satisfy the feature's purpose.

**Independent Test**: Search the current (non-historical) codebase, package metadata, configuration, and forward-looking documentation for the old product name and confirm no unintentional occurrences remain in places that describe the current or future product. Confirm historical specs (001–007) are unchanged except where they asserted something about the future that this feature supersedes.

**Acceptance Scenarios**:

1. **Given** the repository's package metadata, configuration files, and forward-looking documentation, **When** searched for the old product name, **Then** no occurrence remains except inside historical specs describing past decisions, or in explicit references to "Albertos" as the customer name (which is unaffected by the rebrand).
2. **Given** historical feature specs 001–007, **When** compared to their pre-refactor versions, **Then** their content describing decisions made at the time is unchanged, except for corrections to forward-looking claims that are no longer accurate.
3. **Given** the root README, **When** read, **Then** it consistently uses "Shiruno", "Shiruno Platform", "Shiruno API", "Shiruno Widget", and "Shiruno Assistant" per their intended meaning, along with the tagline "Knowledge that answers." and the supporting message about turning organizational knowledge into an assistant customers can ask.

---

### User Story 4 - Future boundaries are documented but not built (Priority: P3)

A team planning Feature 009 (Admin Platform Foundation & Tenant Boundary) or a future standalone widget extraction can read documentation that describes the intended shape of the Shiruno Platform/Customer Admin and the Shiruno Widget — their future responsibilities and conceptual usage — without finding any partially-built implementation, placeholder endpoints, or premature abstractions for them in the current code.

**Why this priority**: This sets up Feature 009 and future widget work cleanly, but it is a documentation deliverable, not a functional one — lowest priority because nothing currently depends on it functioning.

**Independent Test**: Read the future-architecture documentation and confirm it describes the Admin Platform and standalone Widget's intended responsibilities and boundaries. Separately, search the codebase for tenant models, admin UI code, login/auth redesign, or a standalone widget distribution artifact and confirm none exist.

**Acceptance Scenarios**:

1. **Given** the repository's architecture documentation, **When** read, **Then** it describes the future Shiruno Platform / Customer Admin (React/TypeScript frontend; authentication, tenant-scoped knowledge management, conversations, analytics, assistant configuration, monitoring) and the future Shiruno Widget (standalone embeddable script usable across plain HTML, WordPress, React, Vue, Angular, and server-rendered sites) as forward-looking, unimplemented direction.
2. **Given** the current codebase, **When** inspected, **Then** no tenant model, multi-tenant data column, admin UI, customer login/authentication redesign, or standalone widget distribution package exists.

---

### Edge Cases

- What happens if a script, Dockerfile, CI config, or piece of documentation still references the old package import path after the rename? → Treated as a defect: the acceptance bar requires no old runtime import path remains required for the application, CLI, Alembic, Docker Compose, or evaluation tooling to run.
- What happens if the planning phase determines the Albertos public-site code cannot be physically relocated without material risk to behavior? → The physical location may stay as-is; the boundary must still be made obvious through directory naming, documentation, or packaging structure rather than forced through a risky move.
- What happens if a historical spec (001–007) contains a statement that was accurate when written but is superseded by this feature (e.g., a claim that the product is permanently single-customer named Albercik)? → The specific superseded claim may be corrected; the rest of the historical spec's content about past decisions remains untouched.
- What happens if the package rename is evaluated during planning and a concrete migration blocker is found? → The rename may be skipped or partially scoped, provided the plan documents the concrete blocker; the rest of the architecture/branding work still proceeds.
- What happens to environment variables, `.env` files, or secrets during any reorganization? → They must not be moved into version control, exposed, or altered in a way that changes runtime configuration behavior.
- How does the refactor handle Docker images or containers built from the old module path? → Docker Compose and any container startup commands must be updated to the new path so builds and runs succeed unchanged from the user's perspective (same ports, same environment variables, same service behavior).

## Requirements *(mandatory)*

### Functional Requirements

**Branding & naming**

- **FR-001**: The reusable product MUST be consistently named "Shiruno" (with "Shiruno Platform", "Shiruno API", "Shiruno Widget", and "Shiruno Assistant" used per their specific meaning) across current package metadata, configuration, and forward-looking documentation.
- **FR-002**: The product tagline "Knowledge that answers." and the supporting message "Turn your organization's knowledge into an assistant your customers can simply ask." MUST appear in the root README's product introduction.
- **FR-003**: Albertos MUST be consistently represented as the first customer / reference implementation of Shiruno, not as the product itself, in all current and forward-looking documentation.
- **FR-004**: Historical feature specifications (001–007) MUST remain historically accurate records of decisions made at the time and MUST NOT be mass-rewritten; they MAY be corrected only where they assert a forward-looking claim that this feature makes incorrect.

**Repository & architectural boundary**

- **FR-005**: The repository structure MUST make it possible for a new reader to distinguish, without reading implementation code, which code is reusable Shiruno platform/backend functionality versus which code is specific to the Albertos customer/reference website.
- **FR-006**: The physical location of the existing public-site package MUST be decided based on migration safety; relocating it is not required if doing so would create material behavior or delivery risk, but the boundary between reusable platform code and Albertos-specific code MUST still be evident from the resulting structure and documentation.
- **FR-007**: The repository MUST NOT gain empty or placeholder directories created merely to mirror the target architecture diagram; structural changes MUST correspond to a meaningful code or documentation move.
- **FR-008**: The existing chat widget (Feature 006/007 behavior) MAY remain physically coupled to the Albertos website if extracting it would require prematurely designing the future standalone widget's public API or protocol.

**Python package naming**

- **FR-009**: The planning phase MUST explicitly evaluate renaming the backend Python package from its current Albercik-branded name to a Shiruno-branded name and its corresponding import path.
- **FR-010**: If the rename is adopted, every affected reference MUST be updated so no part of the application, CLI, Alembic migrations, Docker build/run configuration, test suite, evaluation tooling, or documented developer command depends on the old import path to function.
- **FR-011**: If the rename is adopted, no compatibility alias or re-export of the old package name MUST be retained unless a concrete reason is documented in the implementation plan.
- **FR-012**: If planning identifies a concrete migration blocker to the rename, the plan MUST document that blocker and the rename MAY be deferred or partially scoped without blocking the rest of the feature.

**Behavior preservation**

- **FR-013**: The public chat endpoint's contract and behavior (request/response shape, `grounded`/`small_talk`/`insufficient_information`/`out_of_scope`/`unavailable` outcomes, source metadata, source hiding in the public widget) MUST be unchanged from immediately before this feature.
- **FR-014**: RAG behavior (retrieval, embeddings, chunking, similarity thresholds, context limits, the system prompt, structured answerability, small-talk classification) MUST be unchanged from immediately before this feature.
- **FR-015**: LLM provider behavior and model defaults (including provider-specific generation parameters already in use) MUST be unchanged from immediately before this feature.
- **FR-016**: Usage accounting, budget enforcement, rate limiting, and concurrency-control semantics MUST be unchanged from immediately before this feature.
- **FR-017**: The public website's existing routes and rendered behavior MUST be unchanged from immediately before this feature.
- **FR-018**: Admin authentication and document-management API behavior from prior features MUST be unchanged from immediately before this feature.
- **FR-019**: The evaluation dataset (`eval/questions.jsonl`) and expected benchmark outcomes MUST be unchanged from immediately before this feature; only the tooling's import/run paths may change if the package is renamed.
- **FR-020**: Any automated test whose module path or import changes as a result of this refactor MUST preserve its original assertion semantics; tests MUST NOT be weakened or have assertions removed in order to make the refactor pass.

**Future-boundary documentation**

- **FR-021**: The repository MUST include documentation describing the intended future standalone Shiruno Widget (embeddable script usage, target compatibility with plain HTML, WordPress, React, Vue, Angular, and server-rendered sites) as forward-looking direction, without implementing its final protocol, distribution package, or CDN delivery.
- **FR-022**: The repository MUST include documentation describing the intended future Shiruno Platform / Customer Admin (authentication, tenant-scoped knowledge management, conversations, analytics, assistant configuration, monitoring; anticipated React/TypeScript frontend) as forward-looking direction, without implementing tenant models, login, or admin endpoints/UI.
- **FR-023**: Documentation MUST clearly mark which architectural pieces are implemented today versus planned for a future feature, so a reader cannot mistake documented future direction for current functionality.

**README**

- **FR-024**: The root README MUST be updated so a new engineer can determine, from that document alone: that Shiruno is the reusable product and Albertos is the first customer/reference implementation; the current technology stack; the current repository structure; the current architecture; the target future architecture; how to run development, evaluation/testing, and Docker Compose commands; and which architectural pieces are current versus future.
- **FR-025**: The README MUST include a concise architecture diagram showing the current system and, separately, the target/future direction.

**Infrastructure**

- **FR-026**: Docker Compose MUST remain the development/orchestration approach used by this feature; no container-orchestration platform beyond Docker Compose MUST be introduced.
- **FR-027**: If infrastructure or configuration files are reorganized or renamed as part of this feature, every affected command and piece of documentation MUST be updated to match, and Docker Compose MUST be demonstrated to still build and run the application successfully afterward.
- **FR-028**: Production hosting/deployment architecture MUST NOT be changed as part of this feature.

**Repository hygiene**

- **FR-029**: After the refactor, no duplicate or stale copy of the previously-named package MUST remain in the repository.
- **FR-030**: After the refactor, no generated build artifact MUST be newly tracked in version control, and no environment/secret file MUST be newly added to version control.
- **FR-031**: After the refactor, no current (non-historical) documentation MUST claim the old product name is the current platform name.
- **FR-032**: After the refactor, no script, Dockerfile, Compose file, or documented command MUST reference a broken or nonexistent import/module path.

### Key Entities

- **Shiruno Platform**: The reusable backend product — chat API, RAG orchestration, retrieval, embeddings, prompting, LLM provider abstraction, usage accounting, security controls, persistence, and evaluation tooling — intended to serve multiple customer implementations in the future, though only one exists today.
- **Albertos Reference Implementation**: The first customer of the Shiruno Platform — the existing public website content and behavior (club pages, trainers, schedule, sections, history, news, contact, Albertos branding) plus the chat widget as currently integrated, representing a concrete example of the platform in use rather than the platform itself.
- **Shiruno Widget (future)**: The not-yet-implemented standalone embeddable chat widget intended to be deployable via a script tag across arbitrary frontend stacks, documented in this feature only as forward-looking architecture.
- **Shiruno Platform / Customer Admin (future)**: The not-yet-implemented administrative application intended to give customers authentication, tenant-scoped knowledge management, conversation visibility, analytics, assistant configuration, and monitoring, documented in this feature only as forward-looking architecture and to be delivered starting with Feature 009.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the automated test suite that passed before this refactor still passes after it, with no test's original assertion intent weakened.
- **SC-002**: 100% of sampled chat interactions across all outcome types (`grounded`, `small_talk`, `insufficient_information`, `out_of_scope`, `unavailable`) produce identical outcomes and content before and after the refactor.
- **SC-003**: The evaluation benchmark produces the same pass/fail results on `eval/questions.jsonl` before and after the refactor.
- **SC-004**: A new reader, given only the README and top-level directory listing, correctly identifies Shiruno as the product and Albertos as the customer/reference implementation without further explanation, on first read.
- **SC-005**: Zero unintended occurrences of the old product name remain in current package metadata, configuration, or forward-looking documentation (historical specs and explicit "Albertos" customer references excluded).
- **SC-006**: Docker Compose successfully builds and starts the full application stack after the refactor, with development workflow commands documented in the README working as described.
- **SC-007**: Zero old runtime import paths remain required for the application, CLI, Alembic, Docker Compose, or evaluation tooling to function.
- **SC-008**: The repository contains no empty directory created solely to mirror the target architecture diagram without a corresponding meaningful move.

## Assumptions

- Whether the Python package is physically renamed from its current Albercik-branded path to a Shiruno-branded path is a decision made during the planning phase (`/speckit-plan`), based on evaluating concrete migration risk — this specification requires the evaluation and, absent a documented blocker, the rename; it does not itself mandate a specific outcome beyond that.
- The physical location of the existing public-site package (whether it moves under a customer/reference-implementation directory or stays in place with clearer documentation/naming) is likewise a planning-phase decision, guided by minimizing behavior risk over satisfying the target directory diagram exactly.
- "Behavior unchanged" is measured against the state of the repository immediately before this feature begins (i.e., including the in-progress Feature 007 conversational-UX changes already present in the working tree), not against some earlier baseline.
- No new environment variables, external services, or infrastructure dependencies are introduced by this feature; existing `.env`-driven configuration continues to work by the same variable names unless a rename makes an update strictly necessary (e.g., a module path referenced in an env-driven setting).
- "Forward-looking documentation" refers to documentation that describes the current or future product/architecture (README, new architecture docs, roadmap notes) as distinct from historical feature specs (001–007), which document point-in-time decisions and are not subject to mass renaming.
- This feature does not require access to real Ollama, GPU resources, Anthropic's API, or external network services for its own verification; existing test doubles/mocks remain sufficient.
- Feature 009 (Admin Platform Foundation & Tenant Boundary) is explicitly out of scope and is not started as part of this feature; documentation produced here only describes its anticipated shape.
