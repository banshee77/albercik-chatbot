# Feature Specification: Admin Platform Foundation & Tenant Boundary

**Feature Branch**: `009-admin-platform-foundation`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Feature 009 — Admin Platform Foundation & Tenant Boundary. Establish tenants, tenant membership, customer administrator authentication, tenant-scoped authorization, and authenticated admin API foundations, with Albertos becoming tenant #1. Does not implement Knowledge Base Administration UI, Conversations & Analytics, or a React admin application."

## Clarifications

### Session 2026-08-19

- Q: How should a customer organization's status become inactive for this feature — as a real operational capability, or only as test-only setup used to prove the deactivation-blocks-access rule? → A: Status is set only via test fixtures/direct setup for verification; no supported way to deactivate a tenant is exposed by this feature (deferred to a future feature).
- Q: Should administrator usernames stay unique across the whole platform, or only unique within each customer organization? → A: Keep username unique platform-wide (today's existing constraint), unchanged by this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator signs in and is automatically confined to their own organization (Priority: P1)

An Albertos administrator signs in with their existing credentials. Without selecting, typing, or configuring anything about "which customer" they represent, every subsequent authenticated action they take is automatically confined to Albertos's own data. They never see a tenant picker, and they cannot make the system act on behalf of any other customer.

**Why this priority**: This is the entire point of the feature — server-derived tenant context is what every future admin capability (knowledge management, conversations, analytics) will depend on. Without it, nothing downstream can be built safely.

**Independent Test**: Log in as the provisioned Albertos administrator, call the safe "who am I" identity check, and confirm it reports the administrator's own identity and the Albertos organization only — with no way to influence that outcome from the request itself.

**Acceptance Scenarios**:

1. **Given** a provisioned Albertos administrator account, **When** they sign in with valid credentials, **Then** authentication succeeds and their session is tied to their organization membership.
2. **Given** an authenticated administrator, **When** they request their current identity/organization information, **Then** the response shows only their own administrator identity and their own organization (Albertos) — never any other organization's information.
3. **Given** an authenticated administrator, **When** their request includes a different organization identifier in the payload, a query parameter, or a header, **Then** the system disregards the supplied value entirely and uses only the organization derived from their authenticated session.

---

### User Story 2 - Operator provisions a new customer organization and its administrator safely (Priority: P2)

The person setting up Shiruno for a customer needs a repeatable, guided way to create a customer organization and its first administrator account — starting with Albertos — without hand-editing the database. Running the same provisioning step twice must never produce a duplicate or a corrupted state.

**Why this priority**: Provisioning is what turns Albertos into "the first customer" and unblocks Story 1; without a safe mechanism, the tenant foundation cannot be populated at all.

**Independent Test**: Provision the Albertos organization, confirm it exists with a unique identifier; re-run the same provisioning step and confirm no duplicate is created and the outcome is clear (safe no-op or explicit, understandable failure). Then provision an administrator against that organization and confirm the administrator is tied to it.

**Acceptance Scenarios**:

1. **Given** no customer organization exists yet, **When** the operator provisions the Albertos organization, **Then** an organization record is created with a unique identifying name and an active status.
2. **Given** the Albertos organization already exists, **When** the operator re-runs the same provisioning step, **Then** no duplicate organization is created, and the operator receives a clear outcome rather than silent duplication or a crash.
3. **Given** an existing customer organization, **When** the operator provisions an administrator for it, **Then** the administrator account is created and associated with exactly that organization, and the tool's output never displays the password, password hash, or any other secret.
4. **Given** the operator attempts to provision an administrator for an organization that does not exist, **When** they run the provisioning step, **Then** the operation fails clearly and no administrator account is created.

---

### User Story 3 - Cross-customer data access is provably impossible (Priority: P1)

The platform operator needs verifiable proof that an administrator from one customer organization can never read, modify, or delete anything belonging to a different customer organization — even if they deliberately try — because a single gap here would compromise every future customer's trust before the platform has any other customers.

**Why this priority**: Tenant isolation is the non-negotiable security property this whole feature exists to establish. It is proven, not assumed, so it carries the same priority as the authentication story it depends on.

**Independent Test**: With two organizations and one administrator per organization provisioned for testing, confirm that Organization A's administrator cannot retrieve, change, or remove anything belonging to Organization B through any tenant-scoped operation, regardless of what identifiers they supply in the request.

**Acceptance Scenarios**:

1. **Given** two customer organizations each with their own administrator and their own tenant-scoped data, **When** Organization A's administrator attempts to access Organization B's data through a tenant-scoped operation, **Then** the request is denied and no data from Organization B is returned.
2. **Given** an authenticated administrator, **When** they attempt to override which organization a tenant-scoped operation applies to (via payload, query, or header), **Then** the override is ignored and the operation applies only to their own organization.
3. **Given** a customer organization whose status has been set to inactive (via direct test setup, since this feature does not expose a supported way to deactivate a tenant), **When** an administrator belonging to that organization attempts a tenant-scoped operation with an otherwise-valid session, **Then** the operation is denied.

---

### User Story 4 - Unauthenticated or invalid access attempts are consistently rejected (Priority: P2)

Anyone without valid administrator credentials — no token, an expired token, or a malformed token — must be unable to reach any tenant-scoped administrative capability, and the rejection must not reveal anything about what does or doesn't exist behind that boundary.

**Why this priority**: A reusable authorization boundary is only trustworthy if its failure mode is uniform and fails closed; this is what every future admin feature will inherit.

**Independent Test**: Call a tenant-scoped administrative endpoint with no credentials, then with an invalid/expired token, and confirm both are rejected identically without leaking whether the underlying resource exists.

**Acceptance Scenarios**:

1. **Given** no authentication is presented, **When** a tenant-scoped administrative operation is requested, **Then** access is denied.
2. **Given** an invalid or expired token is presented, **When** a tenant-scoped administrative operation is requested, **Then** access is denied.
3. **Given** an authorization failure of any kind above, **When** the response is returned, **Then** it does not reveal whether the targeted resource, administrator, or organization exists.

---

### User Story 5 - Everything that already works keeps working (Priority: P1)

Every visitor chatting with Albertos through the public assistant, and every existing administrator action against the current document management capability, must behave exactly as it did before this feature — nobody outside the project team should be able to tell this change happened.

**Why this priority**: This is a foundational, security-sensitive change layered under a live system; regressing existing public or admin behavior would be a failure regardless of how well the new tenant boundary works.

**Independent Test**: Run the full existing automated suite (public chat outcomes, small-talk behavior, rate-limit/budget/security tests, existing document upload/list/delete) unmodified in intent and confirm every test still passes.

**Acceptance Scenarios**:

1. **Given** the public assistant, **When** a visitor asks a question that previously produced any of the existing outcomes (grounded, insufficient information, out of scope, unavailable, small talk), **Then** the same question produces the same outcome, with no new requirement to supply an organization or assistant identifier.
2. **Given** the existing Albertos administrator, **When** they use the existing document upload, list, or delete capability, **Then** it continues to work exactly as before, still requiring administrator authentication.
3. **Given** the existing rate-limiting, budget, and cost-safety controls, **When** the public assistant is used, **Then** those controls continue to apply exactly as before.

---

### Edge Cases

- What happens when an administrator's organization is deactivated while their session token is still otherwise valid? → Tenant-scoped access must be denied from that point forward, not merely at next login. This feature does not provide a supported operation (CLI or otherwise) to deactivate a tenant; deactivation is exercised only via direct test setup to prove the access-denial rule, and a real deactivation capability is deferred to a future feature.
- What happens when a provisioning attempt targets an organization identifier that does not yet exist? → The attempt must fail clearly; no administrator may be created without a valid, existing organization to belong to.
- What happens when two provisioning attempts for the same organization occur back-to-back (e.g., an operator re-runs a script)? → Exactly one organization record must exist afterward; the mechanism must not silently create a second "Albertos".
- What happens when a client supplies an organization identifier that happens to match their own organization? → Behavior is unaffected either way, since the server never trusts the client-supplied value regardless of whether it matches.
- What happens to a public visitor's experience during and after this feature ships? → Completely unaffected; no new required fields, no new required steps, no behavior change.
- What happens if someone tries to create an administrator account without specifying any organization? → The operation must fail rather than create an orphaned or ambiguously-owned administrator.

## Requirements *(mandatory)*

### Functional Requirements

**Customer organization (tenant) foundation**

- **FR-001**: System MUST persist customer organization records with, at minimum, a unique identifier, a name, a unique short identifying slug, a status, and creation/update timestamps.
- **FR-002**: System MUST reject creating a customer organization whose slug duplicates an existing organization's slug.
- **FR-003**: System MUST provide a safe, repeatable provisioning mechanism for creating a customer organization that does not require manual database editing.
- **FR-004**: Re-running provisioning for a customer organization that already exists MUST NOT create a duplicate record; it MUST either be a safe no-op or fail with a clear, actionable outcome.
- **FR-005**: System MUST provision Albertos as the platform's first customer organization through this mechanism.
- **FR-006**: System MUST NOT create a new customer organization automatically as a side effect of ordinary application startup.

**Administrator membership**

- **FR-007**: Every administrator account MUST be associated with exactly one customer organization.
- **FR-008**: A customer organization MAY have more than one administrator account.
- **FR-009**: The provisioning mechanism for creating an administrator MUST require the operator to explicitly specify the target organization and MUST fail clearly if that organization does not exist.
- **FR-010**: Administrator accounts that existed before this feature MUST be assigned to the Albertos organization as part of adopting the tenant-aware model, with no administrator left unassociated with an organization.
- **FR-010a**: Administrator usernames MUST remain unique across the entire platform (not merely within a single organization), preserving the existing uniqueness rule unchanged by this feature.

**Authentication and tenant context**

- **FR-011**: Administrator sign-in MUST continue to work using the existing credential-based mechanism.
- **FR-012**: After authentication, the system MUST derive the administrator's organization from their authenticated identity — never from a value the client supplies.
- **FR-013**: System MUST disregard any client-supplied organization identifier appearing in a request payload, query parameter, or header when determining which organization's data a request may access.

**Tenant-scoped authorization boundary**

- **FR-014**: System MUST provide a single, reusable way for any current or future authenticated administrative operation to obtain "the current administrator" and "the current administrator's organization," so individual operations do not each reimplement that lookup.
- **FR-015**: An authenticated administrator MUST NOT be able to read, modify, or delete data belonging to a customer organization other than their own, for any tenant-scoped operation this feature introduces.
- **FR-016**: A request with missing, invalid, or expired authentication MUST be denied access to any tenant-scoped administrative operation.
- **FR-017**: If a customer organization's status is inactive, administrators belonging to it MUST be denied access to tenant-scoped administrative operations, even with an otherwise-valid session.
- **FR-018**: Authorization failures and cross-organization access attempts MUST return a response that does not reveal whether the targeted resource, administrator, or organization exists.

**Minimal authenticated identity endpoint**

- **FR-019**: System MUST provide an authenticated capability that returns the current administrator's own safe identity information together with their own organization's safe identity information (at minimum, the organization's name and slug), and MUST NOT return another organization's information under any circumstance.
- **FR-020**: The identity capability's response MUST NOT include passwords, password hashes, authentication-token internals, or other sensitive internal details.

**Preserving existing public and administrative behavior**

- **FR-021**: The public assistant's request/response contract and all of its existing outcome types MUST remain unchanged by this feature.
- **FR-022**: The public assistant MUST NOT require an organization identifier or assistant identifier from the client as a result of this feature.
- **FR-023**: Existing administrator document upload, list, and delete capabilities MUST continue to function for the Albertos administrator after this feature.
- **FR-024**: This feature's data model and authorization changes MUST NOT create a state in which a future second customer organization's documents would be reachable by today's Albertos administrator once a second organization exists.

**Auditability**

- **FR-025**: Where administrative actions are already recorded for audit purposes, those records MUST include which organization the action was performed under.
- **FR-026**: Logs and audit records MUST NOT include credentials, authentication tokens, or password hashes.

**Data migration safety**

- **FR-027**: The change that introduces organization membership MUST NOT delete or silently rewrite existing administrator data; it MUST explicitly assign every pre-existing administrator to the Albertos organization.
- **FR-028**: After this change, it MUST NOT be possible for an administrator record to exist without an organization association.

**Provisioning tool safety**

- **FR-029**: Provisioning tool output MUST NOT print passwords, password hashes, authentication secrets, or database credentials.

### Key Entities

- **Customer Organization (Tenant)**: Represents one customer of the Shiruno platform. Minimum attributes: unique identifier, name, unique slug, status (e.g., active/inactive), created/updated timestamps. Albertos is the first customer organization. Future organization-owned resources (knowledge base, conversations, usage, assistant configuration, branding) are out of scope for this feature.
- **Administrator**: A customer's authenticated management-console user. Belongs to exactly one customer organization. Retains its existing identity attributes from prior features, plus a required organization association. Username uniqueness remains platform-wide, not per-organization.
- **Tenant Context**: The server-derived, authenticated notion of "which organization this request is allowed to act on." Never settable or overridable by the client; always resolved from the authenticated administrator.
- **Tenant-Scoped Test Resource**: A minimal, test-only resource introduced solely to prove the cross-organization isolation guarantee at this new authorization boundary, since the existing knowledge base and conversation data are not yet organization-aware.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of automated tests proving cross-organization access is blocked pass — an administrator from one organization can never read, modify, or delete another organization's tenant-scoped data.
- **SC-002**: 100% of the pre-existing automated test suite (public assistant outcomes, small-talk behavior, rate-limit/budget/cost-safety behavior, and existing document upload/list/delete behavior) continues to pass, unmodified in intent, after this feature.
- **SC-003**: 100% of administrator accounts in the system belong to exactly one customer organization after this feature ships, with zero exceptions.
- **SC-004**: An authenticated administrator's identity check returns their own identity and their own organization 100% of the time, and never returns another organization's information in any tested scenario.
- **SC-005**: 100% of requests that attempt to supply a different organization identifier than the authenticated administrator's own are denied access to that other organization's data.
- **SC-006**: 100% of requests with missing or invalid authentication are denied access to tenant-scoped administrative operations.
- **SC-007**: The Albertos customer organization can be provisioned through a single supported operation with no manual database editing, and repeating that operation never produces a duplicate.
- **SC-008**: An administrator can be provisioned for a named customer organization through a single supported operation, with zero secrets printed to console output.
- **SC-009**: Public visitors experience zero required changes — every previously supported outcome (grounded, insufficient information, out of scope, unavailable, small talk) behaves identically before and after this feature.

## Assumptions

- The example "safe identity" response shape in the feature request (including an email field) is illustrative. The current administrator identity model is username-based with no email field; this feature does not require adding email as an identity attribute — the identity capability returns whatever safe identity fields already exist (e.g., username) alongside the organization's safe fields (name, slug).
- Only Albertos will hold real production data during this feature. Cross-organization isolation (User Story 3) is proven using a second, test-only customer organization and a minimal test-only tenant-scoped resource rather than a second real customer's data, since the existing knowledge base and conversation data are not yet organization-aware.
- Whether the existing document records themselves gain an explicit organization-ownership column now, versus that being deferred to the next feature, is a technical decision made during planning; either way, this feature must not leave a state where a future second organization's documents could be reached by today's administrator.
- No self-registration exists or is introduced for administrators; provisioning remains an out-of-band action performed by a trusted operator, not exposed as a public or self-service endpoint.
- No platform-wide super-administrator role or endpoint is introduced; organization and administrator provisioning happen through trusted, direct tooling rather than an authenticated HTTP API.
- Customer organization status supports at least "active" and "inactive" values, sufficient to prove that deactivation blocks access; richer lifecycle states are not required by this feature. No supported operation (CLI or API) to change an existing tenant's status is introduced by this feature — status is set to "active" at provisioning, and "inactive" is exercised only via direct test setup to prove FR-017; a real deactivation capability is deferred to a future feature.
- This feature's own verification does not require real Ollama, GPU resources, Anthropic credentials, or external network access.
- The future React admin application, knowledge-base administration UI, and conversations/analytics capabilities are explicitly out of scope; this feature only establishes the organization and administrator identity/authorization foundation those future capabilities will depend on.
