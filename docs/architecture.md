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
                 └────────┬─────────┘
                          │
                    Public Chat API
                     (/api/v1/chat)
                          │
                          ▼
                 Shiruno Chat Widget
                          │
                          ▼
                       Albertos
              (only customer today)
```

Today, one deployable Python package (`shiruno`, importable from
`src/shiruno/`) contains both the reusable platform and the one customer
reference implementation built on it:

| Module | Layer | Reusable? |
|---|---|---|
| `shiruno.api` | HTTP routing, request/response schemas, error mapping | **Shiruno Platform** — yes |
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
- **Database**: PostgreSQL + `pgvector`, single-tenant (one Albertos
  knowledge base; no `organization_id`/tenant table — see the
  constitution's Tenancy Posture principle).
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

## Future: Shiruno Platform / Customer Admin

Not implemented in Feature 008. No tenant model, authentication redesign,
admin endpoint, or admin UI exists yet — see the Explicit Non-Goals below.

```text
                 ┌──────────────────┐
                 │    Shiruno API   │
                 └────────┬─────────┘
                          │
                      Admin API
                          │
                          ▼
                  Shiruno Platform
                 Customer Admin UI
```

The future **Shiruno Platform / Customer Admin** is a tenant-aware
administration application (anticipated frontend: React + TypeScript)
giving each customer:

- Authentication (replacing today's single-tier, CLI-provisioned admin
  account).
- Tenant-scoped knowledge management.
- Conversation visibility.
- Analytics.
- Assistant configuration.
- Monitoring.

This is the subject of **Feature 009 — Admin Platform Foundation & Tenant
Boundary**, which starts after Feature 008 and is explicitly out of this
feature's scope.

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
