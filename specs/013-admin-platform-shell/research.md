# Phase 0 Research: Shiruno Admin Platform Shell

**Feature**: `013-admin-platform-shell` | **Spec**: [spec.md](./spec.md)

## R1. Token storage — in-memory only, not `localStorage`/`sessionStorage`

**Decision**: The administrator's bearer token lives only in a JavaScript
variable held by the frontend's auth state (a React Context/provider,
research.md R6) for the lifetime of the page. It is never written to
`localStorage`, `sessionStorage`, or any other persistent Web Storage. A
full page reload — including the browser's own refresh — loses the
in-memory token, and the app returns to `initializing` → (no stored
session found) → `unauthenticated`, requiring the administrator to log in
again.

**Rationale**: The spec (FR-019, Assumptions) requires this decision be
made explicitly here, evaluating the existing bearer-token mechanism
against `localStorage`, `sessionStorage`, and an HttpOnly-cookie
adaptation, with security taking priority over convenience.

- **`localStorage`/`sessionStorage` — rejected.** Both are fully readable
  by any JavaScript executing on the page. A single XSS bug — in this
  application's own code, or in any of its npm dependencies — is enough to
  exfiltrate the token outright, and a *stored* XSS payload could keep
  stealing tokens from every future visit for as long as it remains
  reachable. `sessionStorage` narrows the window slightly (cleared on tab
  close) but does not fix the fundamental script-readability problem the
  brief specifically warns against defaulting into.
- **HttpOnly secure cookie — rejected for this feature, not forever.**
  This is the strongest option against token theft via XSS (JavaScript
  cannot read an HttpOnly cookie at all), but adopting it here is a real
  backend redesign, not a narrow browser-integration change: `POST
  /auth/login` would need to `Set-Cookie` instead of/alongside returning
  the token in the JSON body; `get_current_administrator`'s
  `HTTPBearer(auto_error=False)` dependency (`api/deps.py`) would need a
  cookie-reading path; CORS would need
  `Access-Control-Allow-Credentials: true` plus a `credentials: "include"`
  fetch mode; and a cross-origin cookie realistically needs an explicit
  CSRF defense (a double-submit token or a same-registrable-domain
  `SameSite=Lax` deployment topology) that doesn't exist today. The spec's
  own instruction — document the tradeoff and choose the safest
  *reasonable MVP* approach if the cookie migration would substantially
  expand scope — applies exactly here; this is deferred, not ruled out
  forever.
- **In-memory — chosen.** JavaScript-readable in principle (nothing
  running in the page is ever fully immune to XSS), but there is no
  persistent copy sitting in `Storage` for a later or unrelated bug to
  find — the exposure window is bounded to "this tab, this page load."
  This is the standard security-literature recommendation for a bearer-
  token SPA that cannot yet move to HttpOnly cookies. The real cost is
  UX: a refresh means re-authenticating. Given `AUTH_JWT_EXPIRE_MINUTES`
  already defaults to 60 and there is no refresh-token mechanism today
  (`infra/security.py::issue_access_token` mints a single fixed-lifetime
  token, nothing else), a session that also doesn't survive a manual
  reload is a real but bounded regression on top of an already-short-
  lived credential — not a new category of inconvenience.

**Alternatives considered**: `sessionStorage` as a "practical middle
ground" — rejected because it shares `localStorage`'s core weakness
(script-readable) and the spec explicitly asks for the safer choice over
convenience, not a compromise between them.

## R2. Logout semantics — frontend-only, no server-side revocation claim

**Decision**: Logout clears the in-memory token and all cached
administrator/tenant state, and navigates to `/login`. It does not call
any backend "invalidate this token" endpoint, because none exists —
`infra/security.py` issues stateless, self-expiring JWTs (`exp` claim
only) with no blocklist/revocation table anywhere in
`persistence/models.py`. The previously-issued token remains
cryptographically valid until its own `exp` elapses; the frontend simply
stops holding or sending it.

**Rationale**: FR-015 explicitly forbids claiming revocation the system
doesn't provide. This is stated plainly in the UI copy and in
`quickstart.md` rather than glossed over.

## R3. Repository structure — `apps/admin/`, matching the project's own documented target direction

**Decision**: `apps/admin/` as a new top-level directory, sibling to
`src/shiruno/` (the existing backend). Nothing under `src/shiruno/` moves.

**Rationale**: `docs/architecture.md`'s own "Target direction (monorepo,
aspirational)" section — written during Feature 008, before any frontend
existed — already names exactly this tree (`apps/api/`, `apps/admin/`,
`packages/widget/`, `examples/`), explicitly as *directional, not a
requirement to pre-create empty directories… so a future feature… has a
clear target to move toward incrementally.* Feature 013 is that future
feature: creating `apps/admin/` now is executing already-documented
intent, not new speculative infrastructure (the spec's own Assumptions
section, and the brief itself, both caution against the latter). No other
structure was seriously considered — a `frontend/` top-level directory
would work equally well mechanically, but would abandon a naming
convention this project already committed to on the record.

## R4. Frontend stack

**Decision**: React + TypeScript, built and served in development with
Vite; `npm` as the package manager (already present in this environment,
no additional tooling to install or document); plain CSS with a small set
of shared tokens (colors, spacing, type scale) rather than a component
library, CSS-in-JS runtime, or Tailwind.

**Rationale**: This is the brief's own stated preference, and each part
is independently justified: React/TypeScript is a well-understood,
widely-supported baseline requiring no framework-specific new mental
model; Vite gives fast local dev and a standard static `dist/` production
build (R9) with zero SSR/SEO machinery the brief explicitly says this
authenticated SPA doesn't need; `npm` avoids introducing a second package
manager's lockfile format and CI tooling for no functional gain over the
one already available. Plain CSS keeps the "do not build a full design
system" instruction literal — a component library would be exactly that.
**Alternatives considered**: Next.js — explicitly rejected per the brief
unless a concrete requirement demonstrates it; none does (no SSR/SEO need
for an authenticated internal tool). Tailwind/MUI/Chakra — rejected for
this feature as more than the "clean, restrained" shell requires; revisit
if Features 014-016's actual screens demand richer components.

## R5. Routing

**Decision**: `react-router` (v6/v7 data-router API — `createBrowserRouter`
+ route `loader`/`element` composition), the standard minimal client-side
router for a React SPA with nested/protected routes.

**Rationale**: The spec needs exactly what this library does well: nested
routes (`/app` → `/app/knowledge` etc.), a redirect-on-unauthenticated
guard, and no more. It is not a framework, has no server-rendering
opinions, and is the de facto standard choice — introducing anything
larger (or hand-rolling routing) would violate Principle XIII (Simplicity)
for no benefit.

## R6. Authentication state boundary

**Decision**: A single `AuthProvider` React Context exposing a status of
exactly `"initializing" | "unauthenticated" | "authenticated" |
"error"` (matching spec.md's Key Entities exactly), plus the current
administrator/tenant identity when `"authenticated"`, plus `login()`/
`logout()` actions. Every protected route reads this context (never
re-derives auth state itself); the API client (R7) reports authentication
failures back into it via one registered callback rather than each
component handling `401`s independently.

**Rationale**: This is exactly the "small explicit authentication state
boundary… React-native mechanisms… unless a stronger requirement appears"
the spec calls for (FR-016/FR-017, Assumptions). No stronger requirement
appeared during this research: the state shape is small, has one writer
(the provider itself), and doesn't need cross-cutting middleware, so
Redux (or any other external state library) would be unjustified
complexity per Principle XIII.

## R7. API access boundary

**Decision**: One small module set under `apps/admin/src/api/` —
`client.ts` (base URL from `import.meta.env.VITE_SHIRUNO_API_URL`, attaches
the in-memory bearer token, parses JSON, maps any non-2xx response to a
typed, safe error, and — specifically for `401`/`403` — invokes the
`AuthProvider`'s registered "session invalidated" callback before
rejecting), `auth.ts` (`login(username, password)`), `admin.ts` (`getMe()`).
No other module performs a raw `fetch` call.

**Rationale**: Directly what FR-020 requires ("one clean architectural
boundary… not scattered raw fetch calls"). Keeping `401` handling
centralized here — rather than in each route/component — is what makes
US6 (session expiration) a single, testable code path instead of a
per-page convention every future page has to remember to follow.

## R8. CORS

**Decision**: A new, off-by-default `Settings.CORS_ALLOWED_ORIGINS: str =
""` (comma-separated origin list, following this project's existing
comma-separated-list convention — see `OTEL_EXPORTER_OTLP_HEADERS`,
research.md R4 of Feature 012). `main.py::create_app()` adds FastAPI's
`CORSMiddleware` only when this list is non-empty, with
`allow_origins=<parsed list>` (never `["*"]`), `allow_credentials=False`
(no cookies are used — R1 — so credentialed CORS is never needed),
`allow_methods` and `allow_headers` scoped to what the admin frontend
actually sends (`GET`, `POST`, `Authorization`, `Content-Type`). No
CORS middleware exists in this codebase today (confirmed: no
`CORSMiddleware` reference anywhere under `src/shiruno/`) — every route
so far has been either same-origin (the public site) or a first-party
non-browser-CORS caller.

**Rationale**: FR-024 requires narrow, server-configured origins, never a
wildcard, precisely when frontend and backend are cross-origin — true for
local development (Vite dev server on `:5173` vs. the backend on `:8000`)
and plausibly true in production depending on how the two are eventually
deployed (out of scope to decide here — Production Build, R9). Because R1
already ruled out cookies, `allow_credentials` can stay `False`, which
keeps the CORS configuration itself simpler and avoids the CSRF exposure
a credentialed cross-origin cookie setup would otherwise reopen.

## R9. Production build & local development workflow

**Decision**: `vite build` produces a static `apps/admin/dist/` directory
(HTML/CSS/JS, no server component) — deployable behind any static
host/CDN/reverse-proxy; how it's actually hosted in production is
explicitly deferred (spec: "Production infrastructure belongs to a later
feature"). Local development: the existing `docker compose up -d` backend
workflow is unchanged; `apps/admin/.env` (git-ignored, with a committed
`.env.example`) sets `VITE_SHIRUNO_API_URL=http://localhost:8000`, and
`npm run dev` (inside `apps/admin/`) starts Vite's dev server — no source
file edits needed to point at the local backend, satisfying FR-030.

**Rationale**: This is the smallest artifact/workflow that satisfies
FR-029/FR-030 without pre-deciding production hosting, matching the
brief's explicit "do not implement the final AWS production deployment in
this feature."

## R10. Testing stack

**Decision**: Vitest (Vite-native test runner, shares Vite's config and
transform pipeline — no separate Jest/Babel setup needed) + `jsdom` +
`@testing-library/react` + `@testing-library/user-event` (for realistic
keyboard-interaction tests, SC-010) + `@testing-library/jest-dom` matcher
extensions. The centralized API client (R7) is mocked at the module
boundary (`vi.mock("../api/client")` or an injected fetch implementation)
for every test that needs a specific login/`/admin/me` outcome — no real
network call, no Mock Service Worker dependency added for this feature's
scope.

**Rationale**: Matches the spec's own constraint (no real Ollama, Phoenix,
network, or production backend) and "choose the minimum necessary
tools." Vitest avoids a second test-runner configuration living
alongside Vite's; mocking the API client module directly (rather than
adding MSW's network-level interception) is the smaller dependency for a
shell this size — revisit MSW if a future feature's richer data-fetching
surface makes module-mocking unwieldy.
**Alternatives considered**: Playwright/Cypress (real-browser E2E) —
deferred; valuable once Features 014-016 add real interactive screens
worth exercising end-to-end, not needed to prove this shell's
authentication/routing/accessibility behavior, which component-level
testing already covers per spec.md's Acceptance Scenarios and Success
Criteria.

## R11. Accessibility verification

**Decision**: Rely primarily on Testing Library's own query semantics
(`getByLabelText`, `getByRole`, `getByRole("navigation")`, etc. — a query
that only succeeds when the underlying markup is genuinely accessible),
plus explicit `user-event` keyboard-only interaction tests for the login
form and primary navigation (FR-025, FR-026, SC-010). No
automated axe-style linter is added as a new dependency for this feature;
Testing Library's accessible-query-first style already structurally
prevents the most common failures (unlabeled inputs, non-semantic
navigation) because such tests simply cannot be written against
inaccessible markup in the first place.

**Rationale**: Keeps the dependency list minimal (Principle XIII) while
still making accessibility a first-class, non-deferrable part of every
component test rather than a separate audit step — consistent with the
spec's "do not defer basic accessibility to a later polish feature."
