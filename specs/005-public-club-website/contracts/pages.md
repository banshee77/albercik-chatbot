# Contract: Public Website Routes

Phase 1 output for `/speckit-plan`. This feature's only external interface
is a set of unauthenticated `GET` routes returning server-rendered HTML
(`text/html`), plus one new static-asset mount. All routes are additive and
registered in `src/albercik_chatbot/public_site/router.py`, included by
`main.py::create_app()` alongside (never replacing) the existing
`/api/v1/*` and `/health` routers. None of the existing contracts in
`specs/004-.../contracts/chat-endpoint-delta.md` or any prior feature's
contract are touched.

## Page routes

| Method | Path | Query params | Response | Notes |
|---|---|---|---|---|
| GET | `/` | — | 200, `text/html` | Home page (User Story 1). |
| GET | `/karate-do` | — | 200, `text/html` | Traditional Karate-Do page, including the terminology glossary (User Story 5). |
| GET | `/o-klubie` | — | 200, `text/html` | Club history (User Story 6). |
| GET | `/trenerzy` | — | 200, `text/html` | Trainers (User Story 4). |
| GET | `/sekcje` | — | 200, `text/html` | Sections/locations (User Story 3). |
| GET | `/grafik` | `location`, `day`, `level` (all optional, repeatable-free — each is a single string) | 200, `text/html` | Training schedule (User Story 2). Unsupplied params = no filter on that axis. An unrecognized value for a supplied param yields the same empty-state UI as a valid-but-non-matching combination (FR-025) — never a 400, since these are UI filters, not a strict API contract with a required enum. |
| GET | `/aktualnosci` | `category` (optional) | 200, `text/html` | News list (User Story 7), newest-first. Empty/unrecognized category → empty-state UI (FR-029a). |
| GET | `/aktualnosci/{slug}` | — | 200, `text/html` on match; 404 on unknown slug | News detail (deep-link Edge Case). The 404 uses the existing app-wide error handling (`api/errors.py`'s registered handlers) — no new error-response shape is introduced. |
| GET | `/kontakt` | — | 200, `text/html` | Contact (User Story 8). The page's contact form (if rendered) has **no `action` route on this server** — see "Negative contract" below. |

All page routes are read-only `GET`s; none of them read or write any
database table, call any provider, or touch session/auth state. `HEAD` on
any of the above is handled automatically by Starlette's default `GET`
behavior (unchanged from the rest of the app).

## Static asset mount

| Mount | Path prefix | Notes |
|---|---|---|
| `StaticFiles(directory="src/albercik_chatbot/public_site/static")` | `/static/site/*` | CSS (`/static/site/css/site.css`) and the progressive-enhancement JS (`/static/site/js/site.js`). Chosen prefix avoids any collision with a future, separate static mount for anything else. |

## Negative contract: the contact form has no backend

Per spec FR-033, the contact page's form (if rendered) is static/
non-functional. This feature registers **no** `POST`/`PUT`/`PATCH` route
under `/kontakt` or any related path. A test asserts this directly:
`POST /kontakt` (and any path the rendered form's `action`, if set, would
point to) returns the application's standard 404/405 — proving by
construction that submitting the form cannot reach any backend logic,
rather than relying on trusting the client-side markup alone.

## Non-goals (explicitly not part of this contract)

- No JSON API is added for this feature's own data (research.md §2 — the
  schedule/news filters are plain server-rendered `GET`s with query
  params, not a separate `/api/...` JSON endpoint).
- No change to any existing `/api/v1/*` route's request/response shape.
- No change to `/health`.
