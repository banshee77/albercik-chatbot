# Shiruno Architecture

**Shiruno** — *Knowledge that answers.*

Turn your organization's knowledge into an assistant your customers can
simply ask.

Shiruno is the reusable RAG (Retrieval-Augmented Generation) chatbot
platform. **Albertos**, a karate club, is its first customer — everything
Albertos-specific (club pages, trainers, schedule, sections, history,
news, contact, branding) is a *reference implementation* built on top of
the platform, not the platform itself.

This document describes the current architecture, then the target
direction. Sections explicitly marked **(future)** are documented intent
only — nothing under a **(future)** heading is implemented yet.

## Current architecture

```text
                         SHIRUNO

                 ┌──────────────────┐
                 │   Shiruno API    │
                 │                  │
                 │ FastAPI          │
                 │ RAG              │
                 │ Retrieval        │
                 │ Embeddings       │
                 │ LLM providers    │
                 │ Persistence      │
                 │ Tenant           │
                 │ Admin API        │
                 │  foundation      │
                 └────────┬─────────┘
                     ┌────┴────┐
              Public Chat API   Admin API
               (/api/v1/chat)  (/api/v1/admin/me)
                     │              │
                     ▼              ▼
             Shiruno Chat Widget   authenticated
                     │              Administrator
                     ▼              (tenant-scoped)
                  Albertos
        (tenant #1 / reference implementation)
```

Today, one deployable Python package (`shiruno`, importable from
`src/shiruno/`) contains both the reusable platform and the one customer
reference implementation built on it:

| Module | Layer | Reusable? |
|---|---|---|
| `shiruno.api` | HTTP routing, request/response schemas, error mapping, including the authenticated admin API foundation (`/api/v1/admin/me`) | **Shiruno Platform** — yes |
| `shiruno.application` | Use-case orchestration (ask question, upload/list/delete document) | **Shiruno Platform** — yes |
| `shiruno.domain` | Chunking, retrieval, prompting, scope, small-talk classification | **Shiruno Platform** — yes |
| `shiruno.persistence` | SQLAlchemy models, session, repositories | **Shiruno Platform** — yes |
| `shiruno.providers` | LLM/embedding `Protocol`s + concrete implementations (Anthropic, Ollama, local sentence-transformers) | **Shiruno Platform** — yes |
| `shiruno.infra` | Security, logging, audit, rate limiting, budget, concurrency | **Shiruno Platform** — yes |
| `shiruno.cli`, `shiruno.config`, `shiruno.main` | Provisioning, settings, FastAPI app factory (composition root) | **Shiruno Platform** — yes |
| `shiruno.public_site` | Albertos public website, templates, static assets, embedded chat widget front-end | **Albertos Reference Implementation** — no |

`shiruno.public_site` depends only on the platform's public
`/api/v1/chat` HTTP contract (via the widget's client-side JS) — it does
not import `domain/`, `application/`, or `providers/` directly. This
boundary already exists; Feature 008 makes it explicit rather than
introducing it.

### Why `public_site` stays physically nested

The target monorepo direction (below) shows Albertos as an `examples/`
entry alongside the platform. Today, `public_site/` remains inside
`src/shiruno/` rather than moving to a separate top-level tree: its
templates and static assets are resolved relative to the module's own
file path, and relocating it outside the installable package would mean
designing a public inter-package/widget contract prematurely — exactly
what Feature 008 is explicit about *not* doing yet. See
`specs/008-shiruno-repository-architecture/research.md` §2 for the full
reasoning. The boundary is enforced by module docstring and this document
instead of by directory location.

### Runtime stack (current)

- **API**: FastAPI (Python 3.14), single backend service.
- **Database**: PostgreSQL + `pgvector`. Multi-tenant as of Feature 009
  (Admin Platform Foundation & Tenant Boundary): a first-class `Tenant`
  table, with `Administrator` and `KnowledgeDocument` each owned by
  exactly one tenant — see the constitution's Multi-Tenant Isolation by
  Default principle (amended 2026-08-19, v4.0.0). Albertos is tenant #1;
  the Albertos knowledge base is the only tenant-owned knowledge base with
  real production data today. `DocumentChunk`, `UsageRecord`, and
  `RateLimitWindow` remain tenant-unaware for now (not yet part of the
  customer-facing administration boundary).
- **Embeddings**: local `sentence-transformers`
  (`intfloat/multilingual-e5-small`), pre-baked into the Docker image.
- **LLM**: `ollama` (local, default) or `anthropic` (Claude), selected
  server-side only, behind a shared `LLMProvider` `Protocol`.
- **Orchestration**: Docker Compose (`db`, `db-test`, `ollama`,
  `ollama-init`, `app`). No Kubernetes.

See the root [`README.md`](../README.md) for full setup and command
details.

## Target direction (monorepo, aspirational)

```text
shiruno/
├── apps/
│   ├── api/                 # today's src/shiruno platform code
│   └── admin/                (future — see below)
│
├── packages/
│   └── widget/                (future — see below)
│
├── examples/
│   ├── albertos/             # today's src/shiruno/public_site
│   ├── static-demo/           (future)
│   └── react-demo/            (future)
│
├── infra/
├── docs/
├── specs/
└── tests/
```

This is *directional*, not a requirement to pre-create empty
directories. Feature 008 deliberately does not restructure into this
exact tree — see research.md §3 for why — because doing so today would
mean creating placeholder directories with no real content. The tree
exists here to make the destination legible, so a future feature (widget
extraction, admin platform work) has a clear target to move toward
incrementally.

## Future: Shiruno Widget

Not implemented in Feature 008. No module, package, or protocol exists
for this yet.

Today's chat widget is served as part of the Albertos website
(`public_site/static/`, `public_site/templates/`) and is coupled to that
one site. The intended future direction is a standalone, embeddable
**Shiruno Widget** distributed independently of any one customer site:

```html
<script
    src="https://cdn.shiruno.com/widget.js"
    data-assistant="...">
</script>
```

Target compatibility (future): plain HTML, WordPress, React, Vue,
Angular, and other server-rendered or client-rendered sites — any
frontend stack able to load a `<script>` tag and call the existing public
`/api/v1/chat` contract. Extracting today's widget into this form
requires designing a stable, versioned public widget protocol/CDN
distribution — a deliberate, separate future feature, not a byproduct of
Feature 008's rename.

## Current: Admin Platform Foundation

Feature 009 (Admin Platform Foundation & Tenant Boundary) implemented the
backend/security foundation the future Shiruno Platform / Customer Admin
frontend (below) will consume:

```text
                 ┌──────────────────┐
                 │    Shiruno API   │
                 └────────┬─────────┘
                          │
                      Admin API
                    (/api/v1/admin/me)
                          │
                          ▼
              authenticated Administrator
                  (tenant-scoped)
```

What exists today:

- `Tenant` as a first-class, persisted entity — Albertos is tenant #1,
  bootstrapped by an Alembic migration.
- Every `Administrator` belongs to exactly one tenant (`tenant_id`, required).
- Authentication (`POST /api/v1/auth/login`, unchanged) resolves tenant
  context server-side afterward — never from client-supplied input.
- A reusable `get_current_administrator` → `get_current_tenant` FastAPI
  dependency boundary, ready for future admin routes to depend on without
  reimplementing tenant lookup.
- `GET /api/v1/admin/me` — a minimal authenticated endpoint proving that
  boundary, returning only the caller's own safe administrator/tenant
  identity.
- Existing admin document upload/list/delete are tenant-scoped: an
  administrator only ever sees, and can only ever affect, their own
  tenant's documents.
- `shiruno.cli create-tenant` / `create-admin --tenant <slug>` —
  out-of-band, no HTTP endpoint provisions either.
- Cross-tenant isolation is proven by automated tests (see
  `specs/009-admin-platform-foundation/`), consistent with the
  constitution's Multi-Tenant Isolation by Default principle.

What is still future — **not** implemented by Feature 009:

- Knowledge Base Administration UI (tenant-scoped document management
  beyond the existing upload/list/delete — Feature 010).
- Conversations & Analytics.
- The React + TypeScript Customer Admin frontend itself (`admin.shiruno.com`).
- Multi-customer public chat widget routing (`/api/v1/chat` stays
  Albertos-only and tenant-unaware, unchanged).
- Platform-wide super-admin.
- Billing, subscriptions, usage plans.

## Future: Shiruno Platform / Customer Admin (frontend)

The future **Shiruno Platform / Customer Admin** is the not-yet-built
React + TypeScript frontend that will consume the Admin API foundation
above, giving each customer:

- Sign-in through the existing/extended authentication.
- Tenant-scoped knowledge management (Feature 010).
- Conversation visibility.
- Analytics.
- Assistant configuration.
- Monitoring.

No frontend code, admin UI, or additional admin endpoints beyond
`GET /api/v1/admin/me` exist yet — this remains forward-looking direction
only, to be delivered incrementally starting with Feature 010.

## Explicit non-goals of Feature 008

Feature 008 is a naming/architecture-boundary/documentation refactor. It
does **not** implement: a tenant model, multi-tenancy, customer
authentication redesign, an admin portal, React, a knowledge-base
administration UI, conversations & analytics, observability integration,
OpenRouter, a hosted LLM change, AWS Lightsail deployment, Kubernetes,
billing, subscriptions, standalone widget distribution, a WordPress
plugin, or a second customer onboarding. All of the above remain
documented intent only, in this file, until a dedicated future feature
implements them.
