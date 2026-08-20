# Feature Specification: Shiruno Admin Platform Shell

**Feature Branch**: `013-admin-platform-shell`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Feature 013 — Shiruno Admin Platform Shell: the customer-facing frontend application foundation for the Shiruno Admin Platform — authentication using the existing administrator authentication mechanism, an authenticated application shell showing the administrator's own organization identity, protected routing, safe logout and session-expiration handling, and placeholder navigation for the future Knowledge, Conversations, and Analytics modules. Frontend-only foundation; does not implement the full Knowledge, Conversations, or Analytics product experiences."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator logs in and reaches the authenticated shell (Priority: P1)

A customer administrator opens the Shiruno Admin Platform, enters their username and password, and — once accepted by the existing Shiruno administrator authentication — arrives at an application shell that already knows who they are and which organization they represent.

**Why this priority**: Without this, nothing else in the feature is reachable — it is the single entry point every other story depends on.

**Independent Test**: With a valid administrator account, submit correct credentials at the login page and confirm the application shell loads with the administrator's own organization identity visible.

**Acceptance Scenarios**:

1. **Given** a customer administrator with valid credentials, **When** they submit those credentials on the login page, **Then** they are authenticated and taken to the application shell.
2. **Given** a successful login, **When** the shell loads, **Then** the administrator's own organization name is visible without any further action.
3. **Given** a customer administrator, **When** they submit incorrect credentials, **Then** they see one generic authentication-failure message that does not reveal whether the username, the tenant, or the account itself exists.
4. **Given** the login page, **When** an administrator submits an empty username or password, **Then** the form prevents submission and shows an accessible, field-associated error rather than contacting the backend with an incomplete request.

---

### User Story 2 - Unauthenticated access to protected routes redirects to login (Priority: P1)

Anyone who is not authenticated, or whose authentication has not yet been confirmed, is kept out of every application route that would otherwise show tenant-scoped information.

**Why this priority**: This is the core access-control guarantee of the shell; without it, the "authenticated" application is authenticated in name only.

**Independent Test**: Without ever logging in, attempt to open `/app`, `/app/knowledge`, `/app/conversations`, and `/app/analytics` directly, and confirm each one redirects to `/login`.

**Acceptance Scenarios**:

1. **Given** no active session, **When** a visitor navigates directly to `/app` or any of its sub-routes, **Then** they are redirected to `/login`.
2. **Given** a session that has not yet finished being confirmed (bootstrap in progress), **When** a protected route is requested, **Then** no tenant-scoped content is rendered until that confirmation completes — the visitor sees a loading state, not a flash of authenticated content followed by a redirect.
3. **Given** an authenticated administrator, **When** they navigate to any `/app` route, **Then** access succeeds without being redirected to `/login`.

---

### User Story 3 - Administrator's own organization identity is always visible and correct (Priority: P1)

Everywhere the shell shows "which organization is this," that information comes from the same authoritative source and is never something the browser guessed, cached from elsewhere, or let the administrator pick.

**Why this priority**: This is the customer-trust-critical property of a multi-tenant admin product — showing (or acting on behalf of) the wrong organization, even in read-only UI, would be a serious trust failure.

**Independent Test**: Log in as an administrator belonging to a specific tenant, confirm the organization name shown in the header and application home matches that tenant, and confirm no request the frontend sends carries a client-chosen tenant identifier.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator, **When** the application header renders, **Then** it shows their own organization's human-readable name — never a raw internal tenant identifier as the primary label.
2. **Given** an authenticated administrator, **When** any API request is made on their behalf, **Then** no request includes a client-supplied tenant identifier used to select which organization's data is returned.
3. **Given** the application, **When** it is inspected for tenant-selection controls, **Then** no dropdown, switcher, or similar control exists that would let an administrator choose a different organization.

---

### User Story 4 - Administrator navigates the placeholder Knowledge, Conversations, and Analytics sections (Priority: P1)

From the application shell, an administrator can reach each of the three future product sections through primary navigation, and each one loads a clear placeholder rather than an error or a blank page.

**Why this priority**: This is what proves the shell is genuinely the foundation subsequent features build on, not just a login screen.

**Independent Test**: While authenticated, use primary navigation to reach Knowledge, then Conversations, then Analytics, confirming each loads successfully with placeholder content and no functional document/conversation/analytics behavior.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator on the application shell, **When** they select Knowledge from primary navigation, **Then** `/app/knowledge` loads with placeholder content.
2. **Given** the same administrator, **When** they select Conversations, **Then** `/app/conversations` loads with placeholder content.
3. **Given** the same administrator, **When** they select Analytics, **Then** `/app/analytics` loads with placeholder content.
4. **Given** primary navigation, **When** it is inspected, **Then** it contains only Knowledge, Conversations, and Analytics — no placeholder entries for sections not yet built (e.g., Settings, Sites, Assistants, Billing).

---

### User Story 5 - Administrator logs out and the session is fully cleared (Priority: P1)

An administrator who is done using the Admin Platform can log out with one deliberate action, after which no previously visible organization or administrator data remains accessible without logging in again.

**Why this priority**: A logout that leaves stale authenticated state visible, or that fails to fully clear session data, would be a real security and trust problem on a shared or public machine.

**Independent Test**: While authenticated, trigger logout and confirm the administrator lands back on `/login`, and that navigating back to any `/app` route afterward redirects to `/login` rather than showing cached data.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator, **When** they choose the logout action, **Then** their frontend session/token state and any cached organization/administrator data are cleared and they are returned to `/login`.
2. **Given** a just-completed logout, **When** the administrator attempts to return to a previously visited `/app` route (e.g., via back navigation), **Then** they are redirected to `/login`, not shown stale content.

---

### User Story 6 - An expired or invalidated session is handled safely mid-use (Priority: P1)

If the administrator's session stops being valid while they are actively using the application — not just at initial load — the shell notices on the next authenticated request, clears its state, and returns them to login instead of continuing to act as if nothing changed.

**Why this priority**: Sessions can become invalid at any time (expiry, account deactivation); silently continuing to show tenant data as if the session were still good would be a safety failure this feature must not allow.

**Independent Test**: While authenticated and viewing a protected route, simulate the backend rejecting the next authenticated request with an authentication failure, and confirm the frontend clears its session state and redirects to `/login` with a safe, generic message.

**Acceptance Scenarios**:

1. **Given** an authenticated administrator using the shell, **When** an authenticated API request comes back rejected for authentication reasons, **Then** the frontend clears its authenticated state and redirects to `/login`.
2. **Given** that redirect, **When** the login page appears, **Then** it shows a safe, generic session-expired indication rather than silently returning to an empty login form with no explanation.
3. **Given** a session invalidated mid-use, **When** the redirect happens, **Then** no previously loaded organization-scoped data remains visible on screen afterward.

---

### User Story 7 - Administrator gets safe, clear feedback during loading and error conditions (Priority: P2)

Whether the backend is slow, briefly unreachable, or returns an error, the administrator always sees an honest, non-technical indication of what's happening — never a blank screen, never raw backend detail, and never authenticated-looking UI before identity is actually confirmed.

**Why this priority**: This materially affects trust and usability, but the shell already has correctness/security value from Stories 1–6 without it; it refines the experience rather than gating access.

**Independent Test**: Simulate a backend-unavailable condition during login and during `/admin/me` retrieval, and confirm both produce a clear, non-technical message rather than a blank screen, a stuck spinner, or raw error text.

**Acceptance Scenarios**:

1. **Given** the backend is unreachable, **When** an administrator attempts to log in, **Then** they see a clear, generic "can't reach the service right now" style message, not a raw network/HTTP error.
2. **Given** a successful login, **When** the follow-up identity lookup is in progress, **Then** the administrator sees an explicit loading state, not a blank or partially-rendered shell.
3. **Given** any backend error surfaced to the administrator, **When** it is displayed, **Then** it never includes raw exception text, a stack trace, HTTP internals, a token value, or an internal identifier.

---

### Edge Cases

- What happens when the backend is completely unreachable at the moment of login? → A safe, generic "service unavailable" message is shown; no partial or misleading authenticated state is created (US7).
- What happens when `/admin/me` itself fails right after an otherwise-successful login? → Treated the same as a session that failed to establish: no authenticated shell is shown, and the administrator sees a safe error rather than a half-authenticated state.
- What happens when an administrator's account or tenant becomes inactive while they are already using the shell? → The next authenticated request fails the same generic way any other authentication failure does (Feature 009's existing fail-closed behavior); the frontend treats it exactly like session expiration (US6) — it cannot and does not distinguish "deactivated" from "expired" from "revoked," by design.
- What happens if something attempts to alter which organization the frontend believes it belongs to (e.g., a modified stored value, a crafted URL)? → It has no effect; tenant identity is re-derived from `/admin/me` every time it matters, never trusted from a stored or URL-supplied value (US3).
- What happens when an administrator opens the Admin Platform in two browser tabs and logs out in one? → The other tab is not required to immediately notice; it will be caught the next time it makes an authenticated request and is treated per Story 6. Cross-tab immediate synchronization is not required for this feature.
- What happens when a visitor submits the login form with only whitespace in a field? → Treated the same as empty (US1 Scenario 4) — prevented client-side with an accessible error, never sent to the backend as if it were meaningful input.

## Requirements *(mandatory)*

### Functional Requirements

**Authentication**

- **FR-001**: The system MUST provide a login page accepting a username and password, authenticated exclusively through the existing Shiruno administrator authentication mechanism — no second or parallel authentication system.
- **FR-002**: Invalid credentials MUST produce exactly one generic, user-facing authentication-failure message that does not reveal whether the submitted username exists, whether a tenant exists, or which organization an account belongs to.
- **FR-003**: An authenticated frontend session MUST NOT be considered established until the backend has confirmed the credentials.
- **FR-004**: The frontend MUST NOT implement its own credential-correctness logic beyond basic client-side presence validation (e.g., non-empty fields) — whether credentials are correct is decided exclusively by the backend.

**Identity**

- **FR-005**: After authenticating, the frontend MUST obtain administrator and tenant identity exclusively from the existing `GET /api/v1/admin/me` endpoint.
- **FR-006**: The frontend MUST NOT derive or accept tenant identity from a URL parameter, a stored client-side value, build/runtime configuration, or any user-selectable control.
- **FR-007**: The frontend MUST NOT provide any control that lets an administrator select or switch between tenants.
- **FR-008**: The application header MUST display the current organization's human-readable name; it MUST NOT display a raw internal tenant identifier as primary UI text.

**Routing and route protection**

- **FR-009**: The application MUST provide, at minimum, routes for `/login`, `/app`, `/app/knowledge`, `/app/conversations`, and `/app/analytics`.
- **FR-010**: Every route under `/app` MUST require an authenticated administrator session; an unauthenticated visitor accessing any such route MUST be redirected to `/login`.
- **FR-011**: The Knowledge, Conversations, and Analytics routes MAY contain placeholder/coming-soon content only in this feature — no functional document, conversation, or analytics behavior is implemented here.
- **FR-012**: Primary navigation MUST NOT include a link or entry for any section not yet implemented (e.g., Settings, Sites, Assistants, Billing) merely as a placeholder.

**Session lifecycle**

- **FR-013**: When an authenticated request returns an authentication failure, the frontend MUST clear its authenticated session state, prevent further display of tenant-scoped data, and redirect to `/login` with a safe, generic session-expired indication.
- **FR-014**: Logging out MUST clear all frontend-held session/token state and any cached organization/administrator data, and MUST return the administrator to `/login`.
- **FR-015**: Logout MUST NOT claim or imply server-side revocation of a token beyond what the selected authentication mechanism actually provides.

**Loading and error states**

- **FR-016**: The frontend MUST show an explicit loading state during initial session bootstrap and MUST NOT render authenticated tenant-scoped UI before that bootstrap completes.
- **FR-017**: The frontend MUST show an explicit loading state during login submission and during `/admin/me` retrieval.
- **FR-018**: The frontend MUST handle a completely unreachable backend safely, showing a generic, non-technical failure message.
- **FR-019**: The frontend MUST NOT display raw backend exception text, stack traces, HTTP internals, token values, or internal identifiers to the administrator.

**API access boundary**

- **FR-020**: All backend communication MUST go through one centralized frontend API access boundary, not calls scattered individually through UI components.
- **FR-021**: The frontend MUST NOT send a client-supplied tenant identifier on any request used to select or authorize access to tenant-scoped data.
- **FR-022**: The backend base URL MUST be configurable through build/deploy-time configuration; it MUST NOT be hardcoded for production use.
- **FR-023**: No secret credential MUST be required in, or embedded into, frontend build configuration.

**Cross-origin access**

- **FR-024**: If the frontend and backend are served from different origins, the backend MUST allow only explicitly configured, narrow frontend origin(s) for authenticated Admin Platform traffic — never an unrestricted wildcard origin.

**Accessibility and usability**

- **FR-025**: The login form's fields MUST be properly labeled and keyboard-operable, with form errors associated with their relevant fields.
- **FR-026**: Primary navigation MUST be keyboard-accessible, with visible focus states and a sensible heading hierarchy throughout the shell.
- **FR-027**: Pages MUST have meaningful, distinct titles.
- **FR-028**: The application MUST remain usable at common desktop/laptop viewport widths (approximately 1280–1920px) and MUST NOT become unusable at tablet-sized widths (approximately 768–1024px); a dedicated mobile experience (below ~768px) is not required.

**Build and workflow**

- **FR-029**: The frontend MUST be able to produce a static production build artifact.
- **FR-030**: Local development MUST allow the frontend to connect to a locally running Shiruno backend without requiring a developer to hand-edit source files to switch target environments.

**Non-regression**

- **FR-031**: This feature MUST NOT change the semantics, behavior, or contract of the existing public chat endpoint, Knowledge API, Conversations/Analytics API, or observability behavior.
- **FR-032**: This feature MUST NOT introduce a platform-level or cross-tenant administrator capability, tenant switching, or customer impersonation.

### Key Entities

- **Administrator Session**: The frontend's own record of authentication status at a point in time — one of initializing, unauthenticated, authenticated, or authentication-error/session-expired. Exists only in the browser; never a source of truth about whether a token is actually valid.
- **Administrator Identity**: The signed-in administrator's own safe identity fields (e.g., username), obtained exclusively from `/api/v1/admin/me` — never entered, guessed, or cached from anywhere else.
- **Organization (Tenant) Identity**: The administrator's own organization's human-readable name/status, obtained the same way as Administrator Identity — display-only in this feature, never a selectable value.
- **Application Route**: One of the shell's navigable destinations (`/login`, `/app`, `/app/knowledge`, `/app/conversations`, `/app/analytics`) — the latter three are placeholders in this feature, not functional product sections.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A customer administrator can go from the login page to a fully loaded, identity-confirmed application shell in a single submit action, with no additional required step, verified by an automated test.
- **SC-002**: 100% of protected-route access attempts by an unauthenticated visitor result in a redirect to the login page, verified by automated tests across every route in FR-009.
- **SC-003**: 100% of displayed organization names come from the authenticated administrator's own `/admin/me` response — never a client-supplied or cached value — verified by automated tests.
- **SC-004**: 0% of invalid-login attempts reveal whether a username, tenant, or account exists, verified by automated tests across at least two distinct invalid-credential scenarios.
- **SC-005**: 100% of mid-session authentication failures result in the administrator being returned to the login page with previously visible organization data no longer present on screen, verified by automated tests.
- **SC-006**: After logout, 0% of previously visible organization/administrator data remains reachable without re-authenticating, verified by an automated test that logs out and re-attempts protected navigation.
- **SC-007**: An administrator can reach each of the Knowledge, Conversations, and Analytics placeholder sections from the shell in a single navigation action, verified by automated tests.
- **SC-008**: The production frontend build completes successfully with zero lint or type errors, verified by an automated build gate.
- **SC-009**: The full pre-existing backend automated test suite (tenant isolation, Knowledge, Conversations/Analytics, observability, public chat contract) continues to pass unmodified in intent.
- **SC-010**: Every interactive element in the login-through-navigation-through-logout journey is operable using the keyboard alone, verified by automated tests.

## Assumptions

- The browser token/session storage mechanism (e.g., in-memory plus a refresh strategy, `sessionStorage`, or an adapted secure cookie) is deliberately left to the planning phase, per the brief's own instruction to inspect the existing bearer-token mechanism and choose the safest reasonable MVP approach — this specification only requires that whatever is chosen keeps credential values out of rendered UI (FR-019) and supports the session-expiration and logout behaviors above (FR-013, FR-014).
- The existing Feature 009 bearer-token administrator authentication mechanism is reused as-is; this feature does not redesign it unless the planning phase's storage-mechanism decision specifically requires a narrow backend adaptation.
- The frontend technology stack (a modern React/TypeScript/Vite single-page application) and its placement in the repository (e.g., an `apps/admin/` directory alongside the existing `src/shiruno/` backend) reflect the brief's stated preference; the planning phase confirms or refines the exact structure after inspecting the current repository, consistent with keeping the smallest clean structure rather than pre-building speculative monorepo infrastructure.
- Backend changes are limited to what browser integration strictly requires (e.g., narrowly configured CORS for the frontend's origin, and any minimal session-mechanism adaptation the planning phase's storage decision calls for) — no change to Knowledge, Conversations, Analytics, public chat, RAG, or observability behavior.
- No cross-tab session synchronization is required for this feature; each browser tab independently discovers an invalidated session the next time it makes an authenticated request (Edge Cases).
- "Organization" in user-facing copy and "tenant" in the existing backend/data model refer to the same concept; this specification uses "organization" for anything user-facing and "tenant" only when referring to the existing backend concept directly.
