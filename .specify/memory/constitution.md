<!--
Sync Impact Report
Version change: 4.1.0 → 4.2.0
Rationale: MINOR — seven existing principles (I, II, VII, VIII, XI, XIII,
  XIV) are materially expanded, none redefined or weakened: Feature 013
  (Shiruno Admin Platform Shell) is Shiruno's first browser-based/customer-
  facing frontend application, and the constitution previously had no
  approved frontend technology at all. Every addition below extends an
  existing principle's already-stated rule to a new surface (the browser)
  this project didn't have before — the same pattern v4.1.0 used for
  OpenTelemetry/Phoenix — which the versioning policy classifies as MINOR
  ("a new principle or materially expanded section is added"), not MAJOR
  (no prior rule is relaxed, reversed, or removed).
Modified principles:
  - XIV. Approved MVP Technology Stack — expanded. TypeScript, React,
    Vite, and React Router added to the approved stack, scoped narrowly to
    browser-based Shiruno applications under `apps/*` (the first being
    `apps/admin/`); a new "Approved frontend stack" paragraph explicitly
    declines to approve Next.js, Redux, Zustand, GraphQL, Tailwind,
    Material UI, Chakra, shadcn, Storybook, Nx, Turborepo, or any
    server-side-rendering framework at this time.
  - I. Security by Default — expanded. New "Browser authentication and
    frontend configuration" paragraph: browser apps authenticate only
    through the existing server-side mechanism; for Feature 013 the token
    is held in memory only (never `localStorage`/`sessionStorage`, never
    in a URL, never embedded in frontend build configuration), with
    weakening that decision requiring a future, explicitly
    security-reviewed feature rather than an incidental side effect; and
    frontend build-time environment variables are confirmed public
    configuration that must never carry a secret.
  - II. Multi-Tenant Isolation by Default — expanded. New "Frontend is
    never a security boundary" paragraph applying this principle's
    existing Rules 3-4 explicitly to browser clients: a frontend must
    never select/submit tenant identity, and hiding UI is never an
    authorization control.
  - VII. Provider and Cloud Neutrality — expanded. New "Frontend
    deployment neutrality" paragraph: approving a frontend build tool
    under Principle XIV does not commit Shiruno to any specific hosting
    provider; production frontend hosting is deferred exactly as backend
    hosting already is.
  - VIII. API Security — expanded. New "Browser/API integration"
    paragraph: cross-origin access for a browser-based Shiruno application
    requires an explicit, narrow, server-configured origin allow-list —
    never a wildcard — for authenticated Admin Platform traffic.
  - XI. Testing Discipline — expanded. New "Frontend quality gates"
    paragraph: customer-facing frontend features require automated
    component/behavior tests, type checking, linting, and a production
    build gate, none depending on a real LLM/Ollama/Phoenix/network;
    backend security/tenant-isolation tests remain independently
    authoritative regardless.
  - XIII. Simplicity for MVP — expanded. New "Frontend simplicity"
    paragraph: frontend libraries only for a concrete current need; no
    speculative design system, state-management architecture beyond
    React's own, SSR layer, or monorepo tooling; React's built-in
    state/context preferred until demonstrably insufficient.
Other sections updated for consistency with the above (no other
  principle's substance changed):
  - Separation of Concerns — added a new "Frontend application boundary"
    subsection describing the `apps/*` (frontend) / `src/shiruno/`
    (backend) split, matching Feature 013's own architecture direction.
  - MVP Scope Boundaries — added an "Explicitly not built" bullet naming
    the frontend technologies this amendment declines to approve; added an
    "Explicitly deferrable" bullet for production frontend hosting.
  - Development Workflow & Quality Gates — added an instruction that a
    reviewer touching frontend code MUST verify no client-controlled
    tenant identifier is sent, the token-storage rule (Principle I) is
    intact, CORS stays narrow (Principle VIII), and TypeScript/lint/build
    gates (Principle XI) pass.
  - Governance / Compliance review — Principle VIII added to the
    critical-severity scrutiny list (now I, II, III, V, VI, VIII, IX, X,
    XI), since browser/CORS integration is a new, concrete leak-relevant
    surface this constitution now governs; added frontend-specific
    reviewer instructions under Principles I and II.
Added principles/sections: none (principle count unchanged at XIV).
Removed sections: none.
Deferred TODOs: none.
-->

# Shiruno Constitution

**Shiruno — Knowledge that answers.** Shiruno turns an organization's
knowledge into an assistant its customers can simply ask. Shiruno is the
reusable security-first, cloud-neutral Retrieval-Augmented Generation (RAG)
product/platform; Albertos is Shiruno's first customer and reference
implementation, not the name of the platform itself. This constitution
defines the non-negotiable engineering rules for Shiruno. It governs every
feature spec, implementation plan, and task list produced by the Spec Kit
workflow.

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

**Browser authentication and frontend configuration** (added by this
amendment, Feature 013-admin-platform-shell): a browser-based Shiruno
application (e.g. `apps/admin/`) MUST authenticate through the existing
server-side administrator authentication mechanism — never a second,
frontend-only authentication scheme. For Feature 013, the authentication
token MUST be held in memory only; it MUST NOT be persisted in
`localStorage`, `sessionStorage`, or any other durable browser storage,
MUST NOT appear in a URL, and MUST NOT be embedded in frontend build-time
configuration. Weakening this specific token-storage decision (for
example, adopting HttpOnly cookie sessions) MAY happen through a future,
explicitly security-reviewed feature; it MUST NOT happen as an incidental
side effect of an unrelated change. Frontend build-time environment
variables (e.g. `VITE_SHIRUNO_API_URL`) are public configuration by
construction — they MUST NEVER contain a secret, applying this
principle's existing "no secrets in source code" rule to the browser
build pipeline specifically.
**Rationale**: The chatbot sits between untrusted external input (users,
documents, model output) and the Albertos knowledge base. Defaulting to
"untrusted" and keeping authz out of the LLM's hands is the only way to
make that boundary enforceable and auditable, independent of which cloud
eventually hosts it.

### II. Multi-Tenant Isolation by Default (NON-NEGOTIABLE)
Shiruno is a multi-tenant platform. Tenant is a first-class security
boundary, not an incidental data attribute or something deferred until a
hypothetical future SaaS pivot. Albertos remains Shiruno's first tenant and
reference implementation, but no reusable Shiruno platform code MUST assume
Albertos is the only tenant that exists or will ever exist. The following
rules govern every tenant-owned resource and every tenant-scoped operation:

1. Tenant MUST be treated as a first-class security boundary in the
   platform's architecture, not an incidental column bolted on later.
2. Every tenant-owned resource MUST be structurally associated with a
   tenant wherever that resource is, or becomes, part of the reusable
   platform/customer boundary (see Rule 10 for what this does not yet
   require).
3. Tenant context for authenticated administrative operations MUST be
   derived from the authenticated server-side identity/session/token —
   never inferred, guessed, or accepted from client-controlled input.
4. Clients MUST NEVER be trusted to select or override tenant ownership
   through a request body field, a query parameter, an arbitrary header,
   or a resource identifier alone.
5. Every tenant-scoped query and mutation MUST enforce tenant isolation;
   an authenticated principal belonging to one tenant MUST NOT be able to
   read, modify, or delete another tenant's data.
6. Cross-tenant access MUST fail closed: when tenant identity cannot be
   verified or does not match, the default outcome MUST be denial, never
   silent success.
7. Error responses MUST NOT leak the existence or contents of another
   tenant's resources — a response MUST NOT let a caller distinguish
   "this resource does not exist" from "this resource exists but belongs
   to another tenant."
8. Automated tests MUST explicitly cover cross-tenant isolation for every
   security-sensitive, tenant-scoped resource, consistent with the
   mandatory coverage already required by Testing Discipline
   (Principle XI).
9. Albertos remains tenant #1 and Shiruno's reference implementation, but
   no reusable Shiruno platform code MUST assume Albertos is the only
   tenant.
10. This principle does NOT require every future product entity to become
    multi-tenant prematurely. Tenant ownership MUST be introduced for an
    entity when that entity becomes part of the reusable platform/customer
    boundary, not speculatively ahead of that need — consistent with
    Simplicity (Principle XIII). Pre-existing single-tenant entities are
    not retroactively tenant-owned merely because this principle exists.
11. Platform-level administration is conceptually distinct from tenant
    administration. A future Shiruno Platform Admin capability MAY operate
    across tenants, but any such capability MUST be explicitly authorized
    as platform-level and MUST NOT arise accidentally from bypassing
    tenant filters in tenant-scoped code paths. No feature is required to
    implement full platform-admin capability unless its own specification
    explicitly requires it.

**Frontend is never a security boundary** (added by this amendment,
Feature 013-admin-platform-shell): Rules 3 and 4 above apply to
browser-based Shiruno applications exactly as they apply to any other
client — a frontend MUST NOT select, submit, or influence which tenant's
data a request returns via a client-controlled `tenant_id` (or
equivalent) value, and hiding a UI element MUST NEVER be treated as an
authorization control. Tenant identity available to a browser application
MUST be treated as informational/display-only, sourced exclusively from
the authenticated administrator's own server-derived identity (e.g. the
existing `GET /api/v1/admin/me` contract) — a frontend MUST NOT cache,
infer, or accept a tenant identity from any other source and present it
as authoritative.

**Rationale**: Shiruno now has a real second architectural boundary — the
tenant — because a concrete, near-term feature (Feature 009) introduces
Albertos's first sibling tenants rather than a hypothetical one. Making
tenant isolation a NON-NEGOTIABLE default, instead of something forbidden
until "actually needed," is what prevents the exact class of bug this
principle exists to rule out: an admin route that silently trusts a
client-supplied tenant id, or a query that forgets a
`WHERE tenant_id = :current_tenant` clause. This mirrors the reasoning
already applied to Security by Default (Principle I) and Cost Safety
(Principle X) — a security invariant needs to be a default, not an opt-in
per endpoint, or it will eventually be forgotten under deadline pressure.
Rule 10 keeps this from becoming exactly the kind of speculative
infrastructure Simplicity (Principle XIII) warns against: existing
single-tenant entities are not force-migrated by this amendment alone —
they become tenant-owned when a feature spec actually makes them part of
the platform/customer boundary.

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

**Frontend deployment neutrality** (added by this amendment, Feature
013-admin-platform-shell): a browser-based Shiruno application's build
MUST produce a deployment-neutral static artifact (e.g. Vite's own
production build output) rather than one committing to a specific hosting
provider's runtime. Approving a frontend build tool under Principle XIV
MUST NOT be read as committing Shiruno to AWS, Vercel, Cloudflare,
Netlify, or any other hosting provider — production frontend hosting
remains a separate, deliberately deferred architectural decision, exactly
as backend hosting already is under this principle.
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

**Browser/API integration** (added by this amendment, Feature
013-admin-platform-shell): when a browser-based Shiruno application and
the API are served from different origins, cross-origin access MUST be
enabled only through an explicit, narrowly server-configured allow-list of
origins — an unrestricted wildcard origin
(`Access-Control-Allow-Origin: *`) MUST NEVER be used for authenticated
Shiruno Admin Platform traffic. Allowed origins are server configuration,
never client-supplied or inferred.
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

**Observability data** (added by this amendment, Feature
012-rag-observability): the same privacy-by-default posture applies to any
data exported through OpenTelemetry/OTLP (Principle XIV), not only to
conventional application logs. Observability instrumentation MUST NOT
automatically export secrets, credentials, authentication tokens, raw
embedding vector values, or hidden model reasoning / chain-of-thought
content, under any configuration. The full text of a visitor's question, an
assistant's answer, retrieved document/chunk content, or assembled prompt
content MUST NOT be exported by default; enabling richer content capture
for controlled development diagnostics MUST require explicit, separate,
off-by-default configuration — never an implicit consequence of enabling
tracing itself.
**Rationale**: Logs are frequently the least-protected data store in a
system; treating them with the same care as the primary database prevents
them from becoming the leak vector. A trace exported to an external
observability backend is exactly this same risk in a new shape — often
leaving the system boundary entirely — so it inherits this principle's
rules rather than being treated as a separate, unregulated data channel.

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

**Frontend quality gates** (added by this amendment, Feature
013-admin-platform-shell): a customer-facing Shiruno frontend feature MUST
have automated component/behavior test coverage, MUST pass TypeScript type
checking and linting, and MUST pass a production build verification — the
frontend analogue of this principle's existing pytest/mockable-provider
requirements. Frontend tests MUST NOT depend on a real LLM provider, real
Ollama, Phoenix, or external network access, mirroring this principle's
existing "mockable, no paid provider calls by default" rule. Backend
security and tenant isolation remain authoritative regardless of any
frontend test coverage — a frontend test proves frontend behavior, never a
substitute for the backend tests this principle already requires.
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

**Frontend simplicity** (added by this amendment, Feature
013-admin-platform-shell): frontend libraries and infrastructure MUST only
be introduced when a concrete, currently-needed feature requires them —
the same "immediate, present requirement" standard this principle already
applies to backend dependencies. Do not speculatively build a
general-purpose design system, a state-management architecture beyond
React's own built-in mechanisms, a server-side-rendering layer, or
monorepo build tooling (e.g. Nx, Turborepo) ahead of a concrete need.
React's built-in state/context mechanisms MUST be preferred until they are
demonstrably insufficient for a real, currently-in-scope requirement.
**Rationale**: Security and correctness are easier to reason about, review,
and test in a simple, explicit codebase. Provider neutrality and clean
layering are achieved through disciplined interface boundaries, not through
building out infrastructure for scenarios the project doesn't yet have.

### XIV. Approved MVP Technology Stack
The MVP is built on: Python, FastAPI, PostgreSQL, pgvector, SQLAlchemy,
Alembic, Claude (via the Anthropic API as the likely initial LLM transport,
behind the Principle V interface), Docker / Docker Compose, `uv` for Python
dependency management, OpenTelemetry as the vendor-neutral standard for
application/LLM-pipeline tracing and observability, and — for browser-based
Shiruno applications under `apps/*` only — TypeScript, React, Vite, and
React Router. No cloud hosting provider is fixed for the MVP. Introducing a
technology outside this list, or committing to a specific cloud provider,
requires an explicit amendment to this constitution (see Governance),
justified by a concrete requirement this stack cannot meet.

**Observability boundary** (added by this amendment, Feature
012-rag-observability): OpenTelemetry MAY be used for distributed/
application tracing, LLM/RAG pipeline tracing, span attributes and events,
OTLP export, and request correlation via `request_id`/`trace_id`. It MUST
remain strictly an observation mechanism: no RAG, security, authorization,
tenant-resolution, answerability, provider-selection, or cost/abuse-
enforcement decision MUST depend on, or be influenced by, whether tracing
is enabled or whether its backend is reachable — that behavior MUST be
identical in every case. Telemetry-backend availability MUST NEVER become
a runtime dependency for the public chat endpoint: an unavailable or
misconfigured observability backend MUST NOT make `/api/v1/chat`
unavailable, trigger a retry of an LLM call, cause an additional paid
provider call, or alter the public response in any way. Tracing/export
failures MUST fail open with respect to telemetry — the trace is simply
lost — while every other application, security, and business behavior
proceeds exactly as if the observability backend did not exist.

Phoenix is approved narrowly as the initial optional operator/developer
local-development observability backend, reached only through
OpenTelemetry's OTLP export — never through a Phoenix-specific SDK or API
called from domain/application code. Phoenix MUST remain: optional (never
required for `docker compose up` or any other normal development or
production path), operator- and developer-facing only (never part of the
public API, never part of the tenant-admin API, never customer-facing), and
replaceable by any other OTLP-compatible backend without an
application/domain-code change. This amendment does not approve Langfuse,
or any other tracing backend, as a required dependency; a future alternate
or additional OTLP backend remains an implementation-level choice, not a
constitutional one, precisely because application code only ever depends on
the OpenTelemetry/OTLP boundary. No vendor-specific tracing SDK — Phoenix-
specific, Langfuse-specific, or otherwise — MUST be imported or called from
application/domain-layer code; only the OpenTelemetry API MUST be used
there.

**Approved frontend stack** (added by this amendment, Feature
013-admin-platform-shell): TypeScript, React, Vite, and React Router are
approved specifically for browser-based Shiruno applications living under
`apps/*` (the first being `apps/admin/`, the customer-facing Shiruno Admin
Platform) — never as a basis for restructuring or replacing the existing
`src/shiruno/` Python/FastAPI backend. TypeScript MUST be used for Shiruno
frontend application code; React is the approved UI framework; Vite is
approved as the development server, build tool, and static
production-build mechanism; React Router is approved for client-side
routing. This amendment does NOT approve Next.js, Redux, Zustand, GraphQL,
Tailwind, Material UI, Chakra, shadcn, Storybook, Nx, Turborepo, or any
server-side-rendering framework — each remains a possible future,
separately-justified addition (per this principle's own amendment
requirement), not part of the current approved stack, precisely because
none is required by Feature 013's actual scope.
**Rationale**: A fixed, named stack keeps the MVP's surface area small and
predictable, which directly supports Principle XIII (Simplicity) and makes
security review tractable, while leaving LLM/embedding/hosting choices
open per Principles V–VII. OpenTelemetry is added under the same logic
that already governs Principles V–VII: it is a vendor-neutral standard, not
a specific backend, so approving it does not commit the project to Phoenix,
Langfuse, or any other vendor any more than approving "an LLM Protocol
interface" commits the project to Anthropic. Phoenix is approved only as
narrowly as the current concrete need (local RAG-trace visualization for
one developer) actually requires, exactly as Principle XIII demands of any
new dependency — and the explicit "must never affect chat" and "must never
become a runtime dependency" rules exist because this is the first
dependency this constitution has approved that sits on the request path of
every single `/chat` call without being one of the things that call
actually needs to succeed. The frontend stack is approved under the exact
same discipline: TypeScript/React/Vite/React Router are what Feature 013's
actual shell needs, narrowly, and the explicit not-approved list exists so
"we already have a frontend" never becomes an unreviewed license to add
arbitrary frontend infrastructure later.

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

### Frontend application boundary (added by this amendment, Feature 013-admin-platform-shell)
Browser-based Shiruno applications live under `apps/*` (the first being
`apps/admin/`, the customer-facing Shiruno Admin Platform), entirely
separate from the existing `src/shiruno/` Python/FastAPI backend. A
frontend application MUST communicate with Shiruno exclusively through the
existing authenticated REST API — it MUST NOT import backend Python code,
reach the database directly, or otherwise bypass the API boundary. Adding
a frontend application MUST NOT require restructuring or moving existing
backend code; the two remain independent deployable units sharing only the
REST contract between them (Principle XIV's Approved frontend stack,
Principle II's Frontend is never a security boundary).

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
- Tenant isolation for every tenant-owned resource and tenant-scoped
  operation (Principle II): server-derived tenant context, fail-closed
  cross-tenant denial, and automated cross-tenant isolation test coverage
  are mandatory as soon as a resource or operation is tenant-owned or
  tenant-scoped — beginning with the Tenant and Administrator entities
  introduced by Feature 009.

Explicitly not built for the MVP (MUST NOT be speculatively implemented):
- Unnecessary architectural abstractions (Principle XII, XIII): factories,
  repositories, abstract base classes, dependency-injection layers, generic
  frameworks, plugin systems, event buses, or domain abstractions not
  justified by a concrete current requirement.
- LangChain, LangGraph, Grafana, Prometheus, Langfuse as a required
  platform, production alerting infrastructure, and customer-facing or
  tenant-admin-facing trace access (Principle XIV's Observability
  boundary) — none of these are approved by the Feature 012 amendment;
  each remains a possible future, separately-justified addition, not part
  of the current approved stack.
- Next.js, Redux, Zustand, GraphQL, Tailwind, Material UI, Chakra, shadcn,
  Storybook, Nx, Turborepo, and any server-side-rendering framework
  (Principle XIV's Approved frontend stack) — none of these are approved
  by the Feature 013 amendment; each remains a possible future,
  separately-justified addition, not part of the current approved stack.

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
- Retroactive tenant ownership of pre-existing single-tenant resources
  (Principle II, Rule 10): Knowledge documents/chunks, conversations, and
  usage records are not made tenant-owned merely because Principle II now
  exists. Each becomes tenant-owned only when the feature that turns it
  into customer-facing, tenant-scoped administration says so (e.g., a
  future Knowledge Base Administration feature) — this amendment mandates
  the isolation *rule*, not an immediate migration of every table.
- The optional local observability backend (Phoenix, Principle XIV) — it
  is never required for `docker compose up`, any other normal development
  path, or any production path; running it is a deliberate, separate,
  opt-in operator action, not a default.
- Production frontend hosting/deployment provider (Principle VII's
  Frontend deployment neutrality) — a browser-based Shiruno application's
  static build output must remain deployable to more than one host; the
  actual choice is deferred, exactly like backend hosting.

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
pattern. The MVP MUST solve the current Albertos deployment's requirements
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
interfaces from Principles V and VI. A reviewer MUST also verify that any
pull request introducing or touching a tenant-owned resource or
tenant-scoped operation derives tenant context server-side, enforces
tenant isolation on every affected query and mutation, fails closed on
cross-tenant access, and includes automated cross-tenant isolation test
coverage (Principle II) — and MUST flag any tenant-scoped code path that
trusts a client-supplied tenant identifier from a request body, query
parameter, or header. Any pull request touching the public chat endpoint
MUST demonstrate that cost/abuse controls (Principle X) remain intact. A
reviewer touching tracing/observability code MUST verify the Principle XIV
Observability boundary — no application decision is influenced by whether
tracing is enabled or reachable, and no observability-backend failure can
affect `/api/v1/chat` — and MUST verify Principle IX's observability
export-content defaults (no secrets, credentials, raw embedding vectors,
hidden model reasoning, or full question/answer/document/prompt content
exported unless a separate, explicit, off-by-default setting was
deliberately enabled) are intact. A reviewer touching a browser-based
Shiruno application (`apps/*`) MUST verify no client-controlled tenant
identifier is ever sent on a request that selects tenant-scoped data
(Principle II), that the authentication token is never written to
`localStorage`/`sessionStorage`/a URL/frontend build configuration
(Principle I), that any cross-origin configuration uses a narrow
server-configured allow-list rather than a wildcard (Principle VIII), and
that TypeScript type-checking, linting, and the production build all pass
(Principle XI). Complexity that deviates from Principle
XII (Engineering Quality), Principle XIII (Simplicity), or Principle XIV
(Approved Technology Stack) MUST be explicitly justified in the PR
description or plan, referencing the concrete requirement that demands it.

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
scrutiny on Principles I, II, III, V, VI, VIII, IX, X, and XI, since
violations there (secrets exposure, tenant-isolation bypass, prompt-
injection escalation, core logic coupled directly to a specific
LLM/embedding/cloud SDK, unsafe cross-origin browser access, uncontrolled
cost exposure, missing access-control tests, observability data leaking
sensitive content) are treated as critical severity. For Principle II
(Multi-Tenant Isolation by Default) specifically, reviewers MUST verify
that tenant context is always derived server-side, that every
tenant-scoped query and mutation enforces isolation, that cross-tenant
access fails closed, and that automated cross-tenant isolation tests exist
for every tenant-owned resource — and MUST flag any code path that would
let a client-supplied tenant identifier influence which tenant's data a
request can reach, including from a browser-based Shiruno application
(Principle II's Frontend is never a security boundary). For Principle I's
Browser authentication paragraph specifically, reviewers MUST flag any
code that persists an authentication token in `localStorage`,
`sessionStorage`, a URL, or frontend build configuration. For Principle
XIV's Observability boundary specifically, reviewers MUST flag any
application/domain-layer import of a vendor-specific tracing SDK (Phoenix,
Langfuse, or otherwise) in place of the OpenTelemetry API, and any code
path where an application decision or the public chat response could
differ depending on whether tracing is enabled or its backend is
reachable. For Principle XIV's Approved frontend stack specifically,
reviewers MUST flag the introduction of any frontend technology not on
that list without an accompanying constitution amendment. Any exception
MUST be documented in the relevant plan's Complexity Tracking section with
a concrete justification, not merely noted and left unresolved.

**Version**: 4.2.0 | **Ratified**: 2026-08-17 | **Last Amended**: 2026-08-20
