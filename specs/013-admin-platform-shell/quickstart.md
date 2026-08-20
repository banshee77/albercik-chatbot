# Quickstart: Shiruno Admin Platform Shell

**Feature**: `013-admin-platform-shell` | **Spec**: [spec.md](./spec.md)

Manual/live validation against the real local stack. Automated coverage
(component tests, backend route tests) lives in the test suite per
research.md R10-R11 and does not require any of the steps below — this
guide proves the shell end-to-end for a human, not the automated gate.

## Prerequisites

- Backend running: `docker compose up -d` (unchanged from every prior
  feature's own quickstart).
- Backend `.env` has `CORS_ALLOWED_ORIGINS=http://localhost:5173` set
  (research.md R8) — otherwise the browser will block every request from
  the Vite dev server.
- A tenant administrator account exists. If none does yet:
  ```sh
  uv run python -m shiruno.cli create-tenant --name "Quickstart Co" --slug quickstart
  uv run python -m shiruno.cli create-admin --tenant quickstart --username admin --password <a-real-password>
  ```

## 1. Start the Admin frontend

```sh
cd apps/admin
cp .env.example .env   # first time only; VITE_SHIRUNO_API_URL=http://localhost:8000 by default
npm install             # first time only
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`).

## 2. Confirm unauthenticated access is blocked

Navigate directly to `http://localhost:5173/app`. Expected: immediate
redirect to `/login` (US2) — no flash of any application content first.

## 3. Log in

At `/login`, enter the administrator credentials from Prerequisites and
submit.

Expected: a brief loading state, then the application shell loads with
"Quickstart Co" (the tenant's name, not its UUID) visible in the header
(US1, US3).

## 4. Confirm organization identity

Confirm the header shows the organization name and, where present, the
signed-in administrator's username — and confirm no tenant UUID appears as
primary text anywhere on screen (FR-008).

## 5. Navigate Knowledge

Select "Knowledge" from primary navigation. Expected: `/app/knowledge`
loads with placeholder content — no document list, no upload UI (FR-011).

## 6. Navigate Conversations

Select "Conversations". Expected: `/app/conversations` loads with
placeholder content only.

## 7. Navigate Analytics

Select "Analytics". Expected: `/app/analytics` loads with placeholder
content only.

## 8. Confirm no tenant switcher exists

Inspect the header and navigation. Expected: no dropdown, search box, or
any other control that would let this administrator pick a different
organization (US3).

## 9. Simulate a session expiring mid-use

With the shell open, revoke validity out from under the current token —
the simplest local way is to wait past `AUTH_JWT_EXPIRE_MINUTES` (60 by
default), or restart the backend with a different `AUTH_JWT_SECRET`, then
navigate to another `/app` route.

Expected: the frontend clears its state and redirects to `/login` with a
generic "your session has expired" style message (US6) — not a frozen
page, not a raw 401 shown anywhere.

## 10. Log out

Log back in, then use the logout action.

Expected: immediate return to `/login`; using the browser's back button
afterward does not reveal any previously visible organization data (US5).

## 11. Confirm protected routes require login again

Navigate directly to `/app/analytics` once more, logged out. Expected:
redirect to `/login`, exactly as in step 2.

## Cleanup

```sh
# apps/admin/: Ctrl-C the `npm run dev` process
docker compose down   # only if you also want to stop the backend
```

No real LLM call, Ollama, Phoenix, or Anthropic credential is needed at
any point in this walkthrough — the shell never invokes `/api/v1/chat` or
any observability path.
