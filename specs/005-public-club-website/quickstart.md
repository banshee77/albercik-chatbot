# Quickstart: Validating the Public Website

Validates this feature end-to-end against the running stack. See
`contracts/pages.md` for the exact route list and `data-model.md` for the
static-content entities referenced below.

## Prerequisites

```bash
docker compose build app
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/health   # expect 200
```

No new `.env` variables, no new `docker-compose.yml` service, and no
database migration are required for this feature (research.md §3, §9).

## Scenario 1 — Every primary page is reachable, unauthenticated (SC-003, SC-004, FR-001)

```bash
for path in / /karate-do /o-klubie /trenerzy /sekcje /grafik /aktualnosci /kontakt; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "localhost:8000${path}")
  echo "${path} -> ${code}"
done
```

Expected: every path returns `200`, with no `Authorization` header sent.
Each response body contains `<nav`/navigation links to the other 7 primary
pages (FR-003) — spot-check with:

```bash
curl -s localhost:8000/ | grep -o 'href="/[a-z-]*"' | sort -u
```

Expected: at least one link to each of `/karate-do`, `/o-klubie`,
`/trenerzy`, `/sekcje`, `/grafik`, `/aktualnosci`, `/kontakt`.

## Scenario 2 — Schedule filtering, including the empty state (User Story 2, FR-024/025)

```bash
# Unfiltered: all sessions present
curl -s localhost:8000/grafik | grep -c "training-session"   # > 0

# A real filter narrows the list
curl -s "localhost:8000/grafik?location=Wierzbin" | grep -c "training-session"

# A combination that can't match anything shows the empty state, not a broken page
curl -s "localhost:8000/grafik?location=Wierzbin&day=Poniedzialek&level=nonexistent-level" \
  | grep -qi "brak zajęć" && echo "empty-state OK"
```

## Scenario 3 — News filtering, listing, and detail deep-link (User Story 7, FR-027–031, FR-029a)

```bash
curl -s localhost:8000/aktualnosci | grep -c "news-post"       # >= 5 (FR-027)

# Category filter narrows the list
curl -s "localhost:8000/aktualnosci?category=Obóz" | grep -c "news-post"

# Empty-state for a non-matching category
curl -s "localhost:8000/aktualnosci?category=nieistniejaca-kategoria" \
  | grep -qi "brak aktualności" && echo "empty-state OK"

# A specific post is directly reachable (deep link, Edge Cases)
slug=$(curl -s localhost:8000/aktualnosci | grep -o 'href="/aktualnosci/[a-z0-9-]*"' | head -1 | grep -o '[a-z0-9-]*"$' | tr -d '"')
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/aktualnosci/${slug}"   # expect 200

# Unknown slug is a clean 404, not a 500
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/aktualnosci/does-not-exist"   # expect 404
```

## Scenario 4 — Trainers and glossary content completeness (User Story 4, User Story 5, SC-006, SC-009)

```bash
curl -s localhost:8000/trenerzy | grep -c "trainer-card"     # >= 3 (SC-006)
curl -s localhost:8000/karate-do | grep -c "glossary-term"   # >= 8 (SC-009)
curl -s localhost:8000/karate-do | grep -io "mokuso\|seiza\|gyaku tsuki" | sort -u
```

## Scenario 5 — Contact form is genuinely non-functional (FR-033)

```bash
# No backend route exists for the form to submit to
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/kontakt   # expect 404 or 405
```

Automated equivalent: `tests/contract/test_public_site_pages.py` asserts
this directly rather than relying on inspecting the rendered markup alone.

## Scenario 6 — Works with JavaScript disabled (SC-008, Edge Cases)

Because every page is server-rendered (research.md §1), any of the `curl`
checks above already *is* the JS-disabled scenario — `curl` never executes
JavaScript. For a manual/visual confirmation, disable JavaScript in a
browser's dev tools and re-load `/grafik` and `/aktualnosci`: the
unfiltered lists and the `<form method="get">` filter controls must remain
fully visible and usable (a filter selection triggers a normal full-page
navigation instead of an in-place update).

## Scenario 7 — Page-load performance (FR-002a, SC-010)

```bash
for path in / /grafik /aktualnosci; do
  curl -s -o /dev/null -w "${path}: %{time_total}s\n" "localhost:8000${path}"
done
```

Expected: well under 2 seconds each (research.md §9 — no DB/LLM calls on
this path, so this should measure in tens of milliseconds locally; the
2-second budget exists for real network conditions, not local loopback).

## Scenario 8 — Existing application is unaffected (FR-037/038, SC-007)

```bash
uv run pytest
```

Expected: the entire pre-existing suite still passes, with the only new
additions being this feature's own new test files
(`tests/contract/test_public_site_pages.py`,
`tests/unit/test_public_site_filters.py`,
`tests/unit/test_public_site_data.py`) — no existing test file is modified
to make this feature pass (a modified existing test would itself be a
signal something regressed).

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
docker compose config
```

Expected: all clean, matching the project's standard gate.
