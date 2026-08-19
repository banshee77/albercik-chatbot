# Data Model: Shiruno Repository & Product Architecture

This feature introduces no new persisted entities and makes no change to
`persistence/models.py`, the PostgreSQL schema, or any Alembic migration.
"Data model" here instead means the architectural/module boundary the
refactor establishes — the structural entities a reader (or a future
Feature 009 plan) needs to reason about.

## Architectural entities

### Shiruno Platform (reusable)

The installable Python package, importable as `shiruno`. Contains every
module that is customer-agnostic:

| Module | Responsibility | Reusable? |
|---|---|---|
| `shiruno.api` | FastAPI routers, request/response schemas, error mapping | Yes |
| `shiruno.application` | Use-case orchestration (`ask_question`, upload/list/delete document) | Yes |
| `shiruno.domain` | Chunking, retrieval, prompting, scope, small-talk classification | Yes |
| `shiruno.persistence` | SQLAlchemy models, session, repositories | Yes |
| `shiruno.providers.llm` / `shiruno.providers.embedding` | Provider `Protocol`s + concrete implementations (Anthropic, Ollama, local sentence-transformers) | Yes |
| `shiruno.infra` | Security, logging, audit, rate limiting, budget, concurrency | Yes |
| `shiruno.cli` | `create-admin` out-of-band provisioning | Yes |
| `shiruno.config` | Settings (env-driven) | Yes |
| `shiruno.main` | FastAPI app factory — the one place that wires reusable modules *and* mounts the Albertos reference implementation | Yes (composition root) |

### Albertos Reference Implementation (customer-specific)

| Module | Responsibility | Reusable? |
|---|---|---|
| `shiruno.public_site` | Albertos public website: club pages, trainers, schedule, sections, history, news, contact, Albertos branding/templates/static assets, plus the currently-coupled chat widget front-end assets | No — customer-specific; see research.md §2 for why it stays physically nested here rather than moving to a separate top-level tree |

`shiruno.public_site` depends only on `shiruno.api`'s existing `/api/v1/chat`
contract (via the widget's client-side JS calling the public HTTP
endpoint) and on nothing else from the reusable modules — it does not
import `domain/`, `application/`, or `providers/` directly (unchanged from
before this feature; this boundary already existed and is preserved, not
introduced, by Feature 008).

### Shiruno Widget (future, documentation only)

Not a code entity in this feature. Represents the eventual standalone,
embeddable script (`<script src="https://cdn.shiruno.com/widget.js">`)
that would let the *current* `public_site`-embedded chat widget's
functionality be reused by other customer sites without depending on
`public_site` at all. No module, package, or directory is created for it
in this feature (FR-021).

### Shiruno Platform / Customer Admin (future, documentation only)

Not a code entity in this feature. Represents the eventual tenant-aware
administration application (React/TypeScript) that would replace/extend
today's single-tier CLI-provisioned admin auth. No module, package,
directory, tenant model, or endpoint is created for it in this feature
(FR-022), and is explicitly deferred to Feature 009.

## Relationships

```text
shiruno (installable package)
├── api, application, domain, persistence, providers, infra, cli, config, main
│     (Shiruno Platform — reusable, customer-agnostic)
│
└── public_site
      (Albertos Reference Implementation — customer-specific,
       depends on the platform's public /api/v1/chat contract only)

docs/architecture.md
      (documents, but does not implement:)
      ├── Shiruno Widget (future)
      └── Shiruno Platform / Customer Admin (future)
```

## State transitions

None — this is a structural refactor with no entity lifecycle changes.
