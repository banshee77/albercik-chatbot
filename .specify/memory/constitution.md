<!--
Sync Impact Report
Version change: 3.0.0 → 3.1.0
Rationale: MINOR bump — this amendment adds substantial new mandatory
  guidance (an Engineering Quality Principles principle, a Separation of
  Concerns architecture section, a Decision Priority section, and elevating
  cost/abuse protection to its own NON-NEGOTIABLE principle) and materially
  expands Testing Discipline and Simplicity for MVP. Nothing NON-NEGOTIABLE
  is weakened or removed — Tenancy Posture (Principle II) is refined with
  more detail (diagram, explicit "later as a separate architectural change"
  framing) but its substance from v3.0.0 (single-tenant MVP, no speculative
  multi-tenancy) is unchanged. Per the versioning policy, additive/expansive
  changes that don't remove or weaken a principle are MINOR, not MAJOR.
Modified principles:
  - II. Tenancy Posture (Single-Tenant MVP) — unchanged in substance; added
    the single-knowledge-base data-flow diagram, an explicit "multi-tenancy
    may be introduced later as a separate architectural change" framing, and
    replaced the vaguer "avoid unnecessary coupling" line with a concrete
    tie to the new Separation of Concerns section (clean layer boundaries
    are what actually keeps a future multi-tenancy migration from requiring
    a RAG-pipeline rewrite).
  - V. LLM Provider Neutrality — now names Python `Protocol` (or an
    equivalent small interface) as the expected mechanism, and adds "do not
    build a complex provider framework for the MVP."
  - VI. Embedding Provider Neutrality — same `Protocol` clarification, plus
    "do not introduce provider abstractions beyond what is necessary for
    replaceability and testing."
  - VII. Cloud & Infrastructure Neutrality — renamed "Provider and Cloud
    Neutrality" to match the new terminology used elsewhere; substance
    unchanged, now explicitly lists Bedrock / another hosted provider /
    self-hosted model as the anticipated future alternatives.
  - X (was part of VIII/deferred). Testing Discipline — materially expanded
    with a prioritized list of mandatory test areas (cost/budget/kill-switch
    behavior, bounded retries, prompt injection, etc.) and a preference for
    testing behavior/invariants over implementation details. Renumbered from
    former Principle X to XI to make room for the new Cost Safety principle.
  - Simplicity for MVP — materially expanded "do not introduce unless
    justified" list (factories, repositories, ABCs, dependency layers,
    generic frameworks, plugin systems, event buses, domain abstractions,
    event-driven architecture, complex DDD layers, multiple deployment
    platforms at once). Renumbered from former Principle XI to XIII.
  - Approved MVP Technology Stack — unchanged in substance. Renumbered from
    former Principle XII to XIV.
Added principles/sections:
  - X. Cost Safety Is a Security Requirement (NEW, NON-NEGOTIABLE) — elevates
    what was previously scattered across API Security and MVP Scope
    Boundaries into its own principle, matching the project's explicit
    stance that public-endpoint cost exposure is a security invariant, not
    an operational nice-to-have.
  - XII. Engineering Quality Principles (NEW) — SOLID/KISS/YAGNI/DRY as
    guidelines (not goals in themselves), explicit dependencies, type hints,
    mockable I/O, boundary validation, composition over inheritance, no
    hidden global mutable state, centralized+tested security-sensitive
    behavior.
  - "## Separation of Concerns" (NEW top-level section) — the layered
    architecture diagram and per-layer responsibility list (API layer,
    Application/service layer, RAG/domain logic, Persistence layer, LLM
    provider boundary, Embedding provider boundary).
  - "## Decision Priority" (NEW top-level section) — the 8-level conflict
    resolution order (security > cost control > correctness > simplicity >
    testability/maintainability > provider replaceability > performance >
    architectural elegance).
Removed sections: none.
Deferred TODOs: none.
-->

# Albercik Chatbot Constitution

Albercik Chatbot is a security-first, single-tenant, cloud-neutral
Retrieval-Augmented Generation (RAG) customer support chatbot built
exclusively for Albertos. This constitution defines the non-negotiable
engineering rules for the project. It governs every feature spec,
implementation plan, and task list produced by the Spec Kit workflow.

## Core Principles

### I. Security by Default (NON-NEGOTIABLE)
All user input, retrieved documents, and LLM output MUST be treated as
untrusted. The LLM MUST NOT be relied upon for authentication or
authorization decisions of any kind. Credentials, API keys, secrets, and
tokens MUST NEVER be committed to source code. Local development MUST use
environment variables or a local `.env` file excluded from Git; production
secrets management MUST be selected based on the eventual hosting platform
(e.g., AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, HashiCorp
Vault) once that platform is chosen. All service and infrastructure
permissions MUST follow least-privilege. Security MUST be enforced by
application and infrastructure controls, not by prompts alone.
**Rationale**: The chatbot sits between untrusted external input (users,
documents, model output) and the Albertos knowledge base. Defaulting to
"untrusted" and keeping authz out of the LLM's hands is the only way to
make that boundary enforceable and auditable, independent of which cloud
eventually hosts it.

### II. Tenancy Posture (Single-Tenant MVP)
Albercik Chatbot is intentionally single-tenant for the MVP and serves
exclusively Albertos, with one Albertos knowledge base:

```text
Albertos
   ↓
single knowledge base
   ↓
documents / chunks / embeddings
   ↓
RAG
   ↓
Albercik Chatbot
```

The MVP MUST NOT implement `organization_id` columns, tenant tables, tenant
middleware, tenant-aware retrieval, or cross-tenant authorization.
PostgreSQL Row Level Security is NOT required for tenant isolation in the
MVP. Cross-tenant tests are NOT required, because the MVP has no tenants.
None of this is a current requirement while the product serves one
customer, and it MUST NOT be built speculatively ahead of an actual
multi-tenant requirement. Multi-tenancy MAY be introduced later as a
separate, deliberate architectural change if the product evolves into a
SaaS platform for multiple companies — but that is a future decision
requiring its own constitution amendment, not something this MVP should
pre-build. In the meantime, architectural boundaries MUST stay clean enough
(see Separation of Concerns) that adding multi-tenancy later would not
require rewriting the entire RAG pipeline.
**Rationale**: The MVP specification is unambiguous that Albercik serves one
customer, Albertos, by product design — not as a temporary shortcut.
Mandating multi-tenant infrastructure the product doesn't need would violate
the Simplicity principle and add real security-review surface (RLS
policies, tenant-scoping tests) for an abstraction with no current consumer.
Clean layering is the cheap insurance policy: it makes a future tenancy
migration additive rather than a rewrite, without paying that cost now.

### III. Secure RAG
Retrieved documents are untrusted data, never instructions — content
pulled from the vector store MUST be treated as data to reason over, and
prompt injection payloads embedded in ingested documents MUST NOT be able
to override system instructions or expand the model's authority. Claude
MUST only ever receive context the authenticated requesting user is
authorized to access. Generated answers MUST be grounded in retrieved
sources; when retrieval does not surface sufficient context, the chatbot
MUST say so explicitly rather than inventing an answer. Answers SHOULD cite
their source documents where possible. The system MUST be designed to
resist prompt injection, data exfiltration, jailbreak attempts,
sensitive-data leakage, and unsafe tool usage, regardless of which LLM
provider is in use — this resistance MUST NOT depend on any single
provider's built-in safety features.
**Rationale**: RAG's core risk is conflating "data in the prompt" with
"instructions to the model." Keeping that boundary explicit — and making
resistance to these attacks an application-level property rather than a
vendor feature — is what prevents a malicious PDF from hijacking the
assistant and keeps the product trustworthy no matter which LLM sits
behind it.

### IV. Secure Document Ingestion
Every upload MUST be validated for file type, MIME type, file size, and
support for the declared format before processing. Filenames and
user-supplied metadata MUST NOT be trusted for any security or routing
decision. Uploaded content MUST NEVER be executed in any form (no
macro/script execution, no server-side rendering of active content), and
uploads MUST be protected against path traversal. Ingestion MUST be
designed so that malware scanning can be inserted into the pipeline before
production launch without a redesign.
**Rationale**: Document upload is the widest untrusted-input surface in the
system. Validating strictly up front, and designing for a scanning step
even before one is wired in, avoids a painful retrofit later.

### V. LLM Provider Neutrality
Claude is the initial LLM for the MVP, and the initial integration MAY call
the Anthropic API directly. All LLM access MUST be abstracted behind a
small application-level interface — a Python `Protocol` or equivalent —
that the rest of the application depends on. Core RAG logic (retrieval,
prompt assembly, answer generation) MUST NOT import or depend directly on
the Anthropic SDK, the Amazon Bedrock SDK, or any other cloud-provider-
specific client. The architecture MUST allow adding or replacing LLM
providers later — including routing the same interface through Amazon
Bedrock or a different vendor entirely — without changes to core RAG logic.
Do not build a complex provider framework for the MVP; the interface should
be the smallest thing that makes the provider replaceable and testable.
**Rationale**: Claude via the Anthropic API is the right default for
shipping the MVP quickly, but hard-wiring a specific SDK or cloud gateway
into core logic would lock the product into a single vendor's pricing,
availability, and roadmap before that tradeoff has been evaluated.

### VI. Embedding Provider Neutrality
Embedding generation MUST be abstracted behind a small application-level
interface — a Python `Protocol` or equivalent — mirroring Principle V. Core
retrieval logic (chunking, vector storage, similarity search) MUST NOT
depend on a single embedding vendor's SDK or API shape. The system SHOULD
be able to switch between hosted embedding APIs and self-hosted/open-source
embedding models by swapping the implementation behind that interface,
without changing retrieval logic or the `pgvector` schema contract. Do not
introduce provider abstractions beyond what is necessary for replaceability
and testing.
**Rationale**: `pgvector` storage is already provider-agnostic; embedding
*generation* is the one place vendor lock-in would otherwise creep in
unnoticed, since the vector dimensionality and API shape differ by vendor.

### VII. Provider and Cloud Neutrality
No hosting provider is decided at the MVP stage. The application MUST
remain deployable to multiple environments — including AWS, Azure, GCP,
Hetzner, Render, Fly.io, or self-hosted infrastructure — without changes to
core application logic. Cloud-specific integrations (secrets managers,
managed LLM gateways, managed queues, managed vector services, etc.) MUST
be isolated behind interfaces, following the same pattern as Principles V
and VI, rather than woven directly into core logic. AWS-specific (or any
single-cloud-specific) dependencies MUST NOT be introduced unless required
by a concrete, currently-needed feature. The design MUST permit future LLM
alternatives such as Amazon Bedrock, another hosted LLM provider, or a
self-hosted model, and embedding implementations MUST likewise remain
replaceable. Cloud-specific infrastructure decisions are deferred until
deployment requirements are known.
**Rationale**: Deferring the hosting decision is only safe if the codebase
doesn't quietly accumulate cloud-specific assumptions while nobody is
looking; isolating cloud integrations behind interfaces keeps the eventual
choice reversible.

### VIII. API Security
All API input MUST be validated at the boundary. Authentication and
authorization MUST be resolved before any protected resource is touched —
never after or interleaved with business logic. Production deployments
MUST apply rate limiting. Stack traces, internal prompts, secrets, and
infrastructure details MUST NEVER be exposed to end users in API responses
or error messages.
**Rationale**: The API is the contract boundary; validating and
authorizing at the edge, and scrubbing internal detail from responses,
keeps failures from becoming information disclosure.

### IX. Privacy and Logging
Logs MUST NOT contain secrets, authentication tokens, full sensitive
documents, or unnecessary PII. Security-sensitive actions (auth events,
unauthorized access attempts, document access, admin actions) MUST be
auditable. Logs MUST retain enough context to debug an issue without
exposing customer content. Logging MUST be privacy-conscious by default,
not as an afterthought.
**Rationale**: Logs are frequently the least-protected data store in a
system; treating them with the same care as the primary database prevents
them from becoming the leak vector.

### X. Cost Safety Is a Security Requirement (NON-NEGOTIABLE)
The public chatbot endpoint creates direct financial exposure, because
requests may invoke paid LLM and embedding providers. Cost controls are
therefore mandatory security invariants, not an optional operational
nicety. A public user MUST NOT be able to control: model selection, maximum
output tokens, system prompt, retrieval Top-K, maximum retrieved context,
provider configuration, retry count, cost limits, or concurrency limits.
The application MUST support: request rate limits, question-size limits,
context-size limits, output-token limits, bounded provider retries,
provider timeouts, concurrent-call limits, usage accounting, configurable
usage budgets, and a server-side LLM kill switch. Rejected requests MUST be
stopped before invoking paid providers whenever possible. If usage/budget
state needed to enforce a limit cannot be verified, the system MUST fail
closed rather than proceed with an unverified call.
**Rationale**: An internet-facing endpoint with no login and a paid model
behind it is a direct line from anonymous traffic to the company's bill.
Treating cost protection with the same non-negotiable weight as
authentication is what keeps "validate the RAG architecture publicly" from
becoming "fund an attacker's LLM usage."

### XI. Testing Discipline (NON-NEGOTIABLE)
Security-sensitive behavior MUST have automated test coverage. Role-based
access-control tests are mandatory: every knowledge-base management
operation (upload, list, delete) MUST be tested to prove a Public User can
never perform it and that only an authenticated Administrator can. External
provider integrations (LLM, embeddings) MUST be mockable, and tests MUST
NOT require paid provider calls by default. Priority test areas include:
document upload validation, RAG retrieval and source preservation,
insufficient-context behavior, Albertos-only scope behavior, prompt-
injection handling, rate limiting, token/request limits, budget
enforcement, kill-switch behavior, bounded retries, document deletion, and
safe error responses. Tests SHOULD verify behavior and security invariants
rather than internal implementation details whenever possible.
**Rationale**: Authorization and cost-safety are correctness properties
that must be continuously verified — manual review alone will eventually
miss a regression. Mockable providers keep the suite fast, deterministic,
and free of accidental paid usage.

### XII. Engineering Quality Principles
Prefer clear, maintainable, testable code over clever code. Apply SOLID
where it improves maintainability and separation of concerns, follow KISS
and YAGNI (especially for the MVP), and apply DRY when duplication creates
meaningful maintenance risk — these are engineering guidelines in service
of clarity, not goals to satisfy for their own sake. Do not introduce an
abstraction solely to satisfy a design pattern. Prefer composition over
inheritance. Keep modules cohesive, and keep functions and classes focused
on a clear responsibility. Avoid hidden global mutable state; prefer
explicit dependencies. Use Python type hints throughout application code
where practical. Validate data at system boundaries and handle errors
explicitly at appropriate boundaries. External I/O and side effects MUST be
easy to mock during tests. Security-sensitive behavior MUST be explicit,
centralized where practical, and covered by automated tests (see Principle
XI). For this MVP, simplicity and clarity take precedence over unnecessary
architectural complexity.
**Rationale**: These practices exist to keep a small codebase reviewable
and safe to change quickly — a security-first MVP with one developer
benefits far more from clarity and explicitness than from architectural
sophistication it doesn't yet need.

### XIII. Simplicity for MVP
Prefer simple, explicit Python code over unnecessary abstraction. Do not
create unnecessary factories, repositories, abstract base classes,
dependency-injection layers, generic frameworks, plugin systems, event
buses, or domain abstractions unless they solve a concrete current
requirement. Do not introduce LangGraph, autonomous agents, microservices,
Kubernetes, Kafka, Celery, Redis, distributed workflows, event-driven
architecture, complex domain-driven-design layers, or multiple deployment
platforms at once, unless a concrete future requirement justifies them. New
dependencies MUST solve an immediate, present requirement — not a
hypothetical future one. The MVP MUST remain understandable and
maintainable by one developer, built from explicit Python code and a small
number of well-defined modules. This principle bounds Principles V–VII:
provider/cloud abstraction MUST stay at the level of a small interface, not
a plugin framework or speculative multi-provider implementation.
**Rationale**: Security and correctness are easier to reason about, review,
and test in a simple, explicit codebase. Provider neutrality and clean
layering are achieved through disciplined interface boundaries, not through
building out infrastructure for scenarios the project doesn't yet have.

### XIV. Approved MVP Technology Stack
The MVP is built on: Python, FastAPI, PostgreSQL, pgvector, SQLAlchemy,
Alembic, Claude (via the Anthropic API as the likely initial LLM transport,
behind the Principle V interface), Docker / Docker Compose, and `uv` for
Python dependency management. No cloud hosting provider is fixed for the
MVP. Introducing a technology outside this list, or committing to a
specific cloud provider, requires an explicit amendment to this
constitution (see Governance), justified by a concrete requirement this
stack cannot meet.
**Rationale**: A fixed, named stack keeps the MVP's surface area small and
predictable, which directly supports Principle XIII (Simplicity) and makes
security review tractable, while leaving LLM/embedding/hosting choices
open per Principles V–VII.

## Separation of Concerns

Architectural boundaries between the following responsibilities MUST be
maintained, even though the exact directory structure may be determined
during technical planning:

```text
API / HTTP layer
        ↓
Application / service layer
        ↓
RAG / domain logic
      ↙     ↘
Retrieval   Provider interfaces
   ↓         ↙        ↘
Database   LLM     Embeddings
```

### API layer
Responsible for HTTP request parsing, authentication enforcement, request
validation, HTTP response formatting, and mapping application errors to
appropriate HTTP responses. The API layer MUST NOT contain core RAG logic
or direct provider-specific logic.

### Application / service layer
Responsible for orchestrating use cases such as uploading knowledge,
deleting knowledge, and answering chatbot questions. It coordinates domain
logic and infrastructure without embedding provider-specific implementation
details.

### RAG / domain logic
Responsible for chunking, retrieval decisions, relevance evaluation,
grounded-answer flow, insufficient-context decisions, and Albertos scope
behavior. Core RAG logic MUST remain independently testable.

### Persistence layer
Responsible for interaction with PostgreSQL, pgvector, document metadata,
chunks, embeddings, and usage records where applicable. Persistence
concerns MUST NOT leak unnecessarily into API or LLM code.

### LLM provider boundary
LLM access MUST be exposed through a small application-level interface or
Python `Protocol` (Principle V). Core application logic MUST NOT import or
depend directly on Anthropic-specific SDK types. A future implementation
such as Amazon Bedrock SHOULD be addable without rewriting the core RAG
workflow. Do not build a complex provider framework for the MVP.

### Embedding provider boundary
Embedding generation MUST likewise be behind a small application-level
interface or Python `Protocol` (Principle VI). Core retrieval logic MUST
NOT depend directly on one embedding vendor or model implementation. Hosted
and local/open-source embedding implementations SHOULD remain possible. Do
not introduce provider abstractions beyond what is necessary for
replaceability and testing.

## MVP Scope Boundaries

Mandatory now, from the first commit (never postponed):
- Treating retrieved documents as data, not instructions, and resisting
  prompt injection / exfiltration / jailbreak / unsafe tool usage
  (Principle III).
- Upload validation (type/MIME/size) and non-execution of uploaded content
  (Principle IV).
- No secrets in source code; environment variables or a git-ignored `.env`
  locally (Principle I).
- LLM access and embedding generation both isolated behind application-level
  interfaces — core RAG/retrieval code MUST NOT import the Anthropic SDK,
  Bedrock SDK, or any embedding vendor SDK directly (Principles V, VI).
- Role-based access control (Public User vs. Administrator) enforced
  server-side for every knowledge-base management operation, with
  corresponding automated test coverage (Principles I, XI).
- Public-endpoint cost and abuse controls: rate limiting, request/question
  size limits, bounded retries, usage accounting, configurable budgets, and
  a server-side kill switch (Principle X). The controls themselves are
  mandatory now; tuning their thresholds for real production traffic MAY
  follow (see deferrable list below).

Explicitly not built for the MVP (MUST NOT be speculatively implemented):
- Multi-tenancy / organization abstractions (Principle II): no
  `organization_id` column, no tenant tables, no tenant middleware, no
  tenant-aware retrieval, no cross-tenant authorization or tests, no
  tenant-specific PostgreSQL Row Level Security. The product currently
  serves one customer, Albertos; building this ahead of an actual
  multi-tenant requirement is speculative infrastructure the MVP does not
  need and MUST NOT carry.
- Unnecessary architectural abstractions (Principle XII, XIII): factories,
  repositories, abstract base classes, dependency-injection layers, generic
  frameworks, plugin systems, event buses, or domain abstractions not
  justified by a concrete current requirement.

Explicitly deferrable (MUST be designed for or kept swappable, MAY be
decided/implemented later):
- Choice of hosting/cloud provider (Principle VII) — the app must stay
  deployable to more than one, but the actual choice is not an MVP
  decision.
- Production secrets manager, selected once the hosting platform is chosen
  (Principle I).
- Amazon Bedrock as an LLM transport — optional; may be added later as an
  alternate implementation behind the Principle V interface. It is never
  mandatory.
- Bedrock Guardrails or any equivalent managed guardrail service — optional
  defense-in-depth only; MUST NOT be treated as a required or primary
  security control (Principle III already requires that resistance be
  achieved independent of any such service).
- Malware/AV scanning of uploaded documents (Principle IV) — ingestion
  pipeline must have a slot for it, but it need not be wired in for MVP.
- Production-tuned rate-limit thresholds and horizontal scaling of the
  rate-limiting mechanism (Principle X) — the control itself is mandatory
  now; tuning it for real production traffic load is not.
- Kubernetes, Redis, Celery, microservices, LangGraph, autonomous agents,
  event-driven architecture, complex domain-driven-design layers, and other
  cloud-specific or distributed infrastructure (Principle XIII) —
  explicitly out of scope for the MVP unless a concrete requirement
  justifies them.

Anything not listed above as deferrable is a mandatory invariant and MUST
NOT be postponed by a feature plan or task list.

## Decision Priority

When engineering principles conflict, resolve using this priority order:

1. Security and protection of customer data.
2. Prevention of uncontrolled financial exposure.
3. Correctness.
4. Simplicity.
5. Testability and maintainability.
6. Provider replaceability.
7. Performance optimization.
8. Architectural elegance.

Security or simplicity MUST NOT be sacrificed merely to apply a design
pattern. The MVP MUST solve the current Albertos chatbot requirements
cleanly before optimizing for hypothetical future requirements.

## Development Workflow & Quality Gates

Every feature spec, plan, and task list produced under this constitution
MUST be checked against the Core Principles before implementation begins.
Pull requests touching knowledge-base data, retrieval, ingestion, or LLM/
embedding integration MUST include or update the corresponding security
tests from Principle XI. A reviewer MUST be able to point to where
role-based access control (Public User vs. Administrator) is enforced for
any new or modified knowledge-base management endpoint, and MUST verify
that core RAG/retrieval code has no direct import of the Anthropic SDK,
Bedrock SDK, or an embedding vendor's SDK — only the application-level
interfaces from Principles V and VI. A reviewer MUST also flag any pull
request that introduces `organization_id` columns, tenant tables, or
tenant-scoped middleware without a corresponding constitution amendment
reinstating multi-tenancy as a requirement (Principle II), and any pull
request touching the public chat endpoint MUST demonstrate that cost/abuse
controls (Principle X) remain intact. Complexity that deviates from
Principle XII (Engineering Quality), Principle XIII (Simplicity), or
Principle XIV (Approved Technology Stack) MUST be explicitly justified in
the PR description or plan, referencing the concrete requirement that
demands it.

## Governance

This constitution supersedes any conflicting practice, template default, or
prior informal convention. Amendments are made by editing this file via the
`/speckit-constitution` workflow.

**Versioning policy** (semantic versioning applied to governance):
- MAJOR: Backward-incompatible removal or redefinition of a principle
  (e.g., relaxing a NON-NEGOTIABLE rule, or replacing a provider mandate
  with a neutrality requirement).
- MINOR: A new principle or materially expanded section is added.
- PATCH: Wording clarifications, typo fixes, non-semantic refinements.

**Compliance review**: Every `/speckit-plan` and `/speckit-tasks` output for
this project MUST be evaluated against these principles, with particular
scrutiny on Principles I, III, V, VI, X, and XI, since violations there
(secrets exposure, prompt-injection escalation, core logic coupled directly
to a specific LLM/embedding/cloud SDK, uncontrolled cost exposure, missing
access-control tests) are treated as critical severity. Principle II
(Tenancy Posture) requires scrutiny in the opposite direction from the
others: reviewers MUST flag any speculative multi-tenancy infrastructure
(organization_id columns, tenant tables, tenant-scoped RLS, cross-tenant
tests) introduced without a corresponding constitution amendment. Any
exception MUST be documented in the relevant plan's Complexity Tracking
section with a concrete justification, not merely noted and left
unresolved.

**Version**: 3.1.0 | **Ratified**: 2026-08-17 | **Last Amended**: 2026-08-17
