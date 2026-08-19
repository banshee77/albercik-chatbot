# Research: Shiruno Repository & Product Architecture

## 1. Python package rename — adopt or defer?

**Decision**: Adopt. Rename `src/albercik_chatbot` → `src/shiruno`, distribution name
`albercik-chatbot` → `shiruno`, console-script entrypoint `albercik-chatbot` →
`shiruno`, and every import of `albercik_chatbot.*` → `shiruno.*`.

**Rationale**: A full-repository scan for non-historical, non-cache references to
`albercik_chatbot` / `Albercik` / `albercik-chatbot` found 118 occurrences,
concentrated in a small, well-understood set of locations:

| Location | File count | Nature |
|---|---|---|
| `src/albercik_chatbot/**` | 29 files | the package itself (directory rename) |
| `tests/**` | ~51 files | import statements, one hardcoded test DB URL |
| `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `alembic/env.py` | 4 files | metadata, build, module path, migration env |
| `scripts/*.py` | 3 files | import statements |
| `README.md`, `eval/README.md` | 2 files | prose/branding |

There is no framework indirection (no dynamic plugin discovery, no
string-based module loading outside the already-factory-based `uvicorn
--factory albercik_chatbot.main:create_app` invocation) and no external
package published under the old name that a third party depends on. Every
occurrence is a straightforward, mechanically verifiable identifier rename.
This is a single-package, single-repository Python project (Approved MVP
Technology Stack, constitution Principle XIV) with no plugin ecosystem —
exactly the shape of rename this size of change is safe for. No concrete
migration blocker exists.

**Alternatives considered**:
- *Keep `albercik_chatbot`, rename only forward-looking docs.* Rejected —
  it satisfies FR-001 nominally but leaves every import statement, the
  installed distribution name, and the Docker/uvicorn module path
  contradicting the product's own README, which fails User Story 2 (a new
  engineer would see "Shiruno" in prose and `albercik_chatbot` in every
  import) and FR-029 (implies keeping a name that is no longer the current
  platform name in code that is very much current).
- *Keep a compatibility shim (`albercik_chatbot` re-exporting `shiruno`).*
  Rejected per FR-011 — no concrete reason for one is identified (single
  deployable service, no external consumers of the package name, no
  published PyPI package), so it would be pure unjustified complexity
  (constitution Principle XIII).

## 2. Physical boundary of `public_site` (Albertos website code)

**Decision**: Do **not** physically relocate `public_site/` out of the
`shiruno` package (e.g. to a top-level `examples/albertos/` tree). It stays
at `src/shiruno/public_site/`. The reusable-vs-customer-specific boundary is
made obvious through documentation and a module docstring, not through a
directory move.

**Rationale**: `public_site/router.py` and `main.py` both resolve template
and static-file directories relative to the module's own file
(`Path(__file__).resolve().parent / "templates"` /
`... / "public_site" / "static"`). That pattern is safe under a rename
(the directory moves with the code that references it) but becomes risky
under a relocation *outside* the installable `shiruno` package: it would
require either (a) turning `public_site` into a second installable
package that `shiruno.main` imports across a package boundary — which
means deciding a public inter-package import contract prematurely, in
direct tension with FR-008's permission to avoid exactly that — or (b) a
`sys.path`/namespace-package hack, which the constitution's Simplicity
principle (XIII) rules out as unjustified complexity. Neither buys any
behavior-preservation or comprehensibility benefit that documentation
doesn't already provide equally well, and both carry real risk of
breaking template/static resolution, `Dockerfile`'s `COPY . .` step, or
`pyproject.toml` packaging — for a feature whose primary mandate is zero
behavior change (FR-013–FR-020).

Per spec FR-006 and the spec's documented edge case ("if the Albertos
public-site code cannot be physically relocated without material risk...
stays as-is, boundary still evident through directory naming,
documentation, or packaging structure"), this is exactly that situation.

The boundary is instead made obvious by:
- `src/shiruno/public_site/__init__.py` gaining a short module docstring
  identifying it as the Albertos customer/reference-implementation content
  (club pages, trainers, schedule, sections, history, news, contact),
  distinct from the reusable platform modules alongside it (`api/`,
  `application/`, `domain/`, `infra/`, `persistence/`, `providers/`).
- The README's repository-layout section and the new `docs/architecture.md`
  both labeling `public_site/` explicitly as "Albertos reference
  implementation," not "the product."

**Alternatives considered**:
- *Rename `public_site/` → `examples/albertos/` inside the package
  (`src/shiruno/examples/albertos/`).* Rejected — touches ~13 import
  statements across `main.py`, `router.py`, and 2 test files for a
  cosmetic depth change with no behavior or comprehensibility benefit
  beyond what documentation already gives; violates FR-007's "no move
  without a meaningful reason" spirit when weighed against the
  documentation-only alternative already satisfying FR-005/FR-006.
- *Move `public_site/` to a genuinely separate top-level `examples/`
  directory, outside `src/`.* Rejected for the reasons in Rationale above
  — real behavior risk for a feature that must not change behavior.

## 3. Target repository structure (this feature's actual scope)

**Decision**: Add one new top-level `docs/` directory
(`docs/architecture.md`) for current + forward-looking architecture
documentation. Do **not** create `apps/`, `packages/`, or `examples/`
skeleton directories — none would contain anything yet, and FR-007
explicitly forbids placeholder directories created only to mirror the
target diagram.

**Rationale**: The target monorepo diagram in the feature description is
explicitly framed as directional ("this is a target architecture, not a
requirement to create meaningless empty directories... prefer meaningful
moves over cosmetic structure"). The only meaningful, safe-to-execute move
available today is the package rename (§1); the `public_site` boundary is
better served by documentation than relocation (§2); and there is no
existing admin app, widget package, or second example site to place under
`apps/`, `packages/`, or `examples/` — creating those directories now would
produce exactly the "meaningless empty directories" the feature explicitly
prohibits. `docs/` is the one new directory that has real, immediate
content (the architecture document FR-021–FR-023 requires) and no prior
existing location.

**Alternatives considered**:
- *Create the full target tree now with `.gitkeep` placeholders.* Rejected
  — directly contradicts FR-007 and the explicit instruction not to create
  meaningless empty directories.

## 4. Postgres service/credential naming (`albercik` user/db/password)

**Decision**: Leave the `albercik` PostgreSQL user, password, and database
names in `docker-compose.yml`, `.env`/`.env.example`
(`DATABASE_URL=postgresql+psycopg://albercik:albercik@...`), and
`tests/conftest.py`'s hardcoded test DB URL unchanged.

**Rationale**: These are internal infrastructure credentials, never shown
to a customer or end user, and not "package metadata" or "documentation" in
any branding sense — they are not in the explicit list of things Feature
008 must rename (Python imports, tests, `pyproject.toml`, package metadata,
Dockerfile, Compose, Alembic config, scripts, CLI entrypoints, uvicorn
module paths, lint/type config, documentation, eval tooling, migration
imports, test fixtures, README commands). Renaming them would touch running
developers' local `.env` files, Docker named volumes
(`db-data`/`ollama-data` are unaffected, but any developer's already-
provisioned Postgres role/database would silently stop matching a freshly
pulled `docker-compose.yml`), and the hardcoded integration-test DB URL —
real behavior-preservation risk (FR-013–FR-020, constitution Decision
Priority: correctness and behavior preservation over architectural
elegance) for zero product-facing benefit. This mirrors §4's reasoning: a
cosmetic rename with real risk and no required-behavior payoff is out of
scope.

**Alternatives considered**:
- *Rename to `shiruno`/`shiruno_test`.* Rejected for the risk/benefit
  reasons above; nothing in the feature's acceptance criteria depends on
  these strings, and the constitution's Decision Priority ranks
  correctness/behavior preservation above architectural elegance.

## 5. Constitution's own use of "Albercik Chatbot"

**Decision**: Do not edit `.specify/memory/constitution.md` as part of this
feature's `tasks.md`. Flag it as a recommended follow-up to be executed via
the dedicated `/speckit-constitution` workflow (governance amendment),
separately from this feature's implementation tasks.

**Rationale**: The constitution's preamble and Principle II both use
"Albercik Chatbot" as the project name (5 occurrences). It is forward-
looking governance documentation, so it is in scope of the *spirit* of
FR-001/FR-003, but the project's own Governance section states amendments
are made "via the `/speckit-constitution` workflow" — not via arbitrary
file edits from an unrelated feature's task list. Editing it inline here
would bypass the versioning/Sync-Impact-Report discipline the constitution
itself mandates for its own changes.

**Alternatives considered**:
- *Edit constitution.md directly in this feature's tasks.* Rejected —
  bypasses the project's own governance process for amending itself.
- *Leave it unmentioned.* Rejected — silently leaving the governance
  document's own branding stale would contradict FR-031 in spirit; better
  to explicitly flag it as a required near-term follow-up.

## 6. Documentation location for future Admin Platform / Widget boundaries

**Decision**: A single new `docs/architecture.md` covers both the current
architecture and the two forward-looking boundaries (Shiruno Widget,
Shiruno Platform / Customer Admin), rather than three separate documents.

**Rationale**: FR-021–FR-023 require the documentation to exist and to
clearly separate "implemented today" from "planned," not to live in any
particular number of files. One document keeps the current-vs-future
distinction easy to present as a single side-by-side narrative (current
architecture diagram directly followed by the future one, per the feature
description's own two diagrams), and avoids the empty-directory-style
over-structuring rejected in §3.

**Alternatives considered**:
- *Separate `docs/widget-roadmap.md` and `docs/admin-platform-roadmap.md`.*
  Rejected — no reader need is served by the split; one document with two
  clearly headed sections is simpler (constitution Principle XIII) and
  README already needs to link to *something* singular for "target
  architecture."
