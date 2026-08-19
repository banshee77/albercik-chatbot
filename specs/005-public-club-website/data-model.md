# Data Model: Public Website for ALBERTOS Traditional Karate-Do Club

Phase 1 output for `/speckit-plan`. All entities are static, in-memory
Python `@dataclass(frozen=True)` instances defined in
`src/albercik_chatbot/public_site/models.py` (types) and
`src/albercik_chatbot/public_site/data/*.py` (the actual static values) —
no database table, no migration, no ORM model (per spec FR-035/036 and
research.md §3). Field names below match the dataclass field names exactly.

## Location (Training Location / Section)

Spec source: Key Entities "Training Location / Section"; FR-022.

| Field | Type | Notes |
|---|---|---|
| `slug` | `str` | Stable, unique, kebab-case identifier (research.md §4). |
| `name` | `str` | e.g. "Grodzin — SP-2". |
| `address` | `str` | Street address shown on the sections/locations page. |
| `groups` | `tuple[str, ...]` | Human-readable group labels trained at this location (e.g., "Początkujący", "Zielone i wyższe pasy"). |
| `age_level` | `str` | Age/skill-level summary shown alongside the location (e.g., "Dzieci i młodzież, początkujący–pomarańczowy pas"). |
| `days_hours` | `str` | Human-readable schedule summary for display on the location card (the authoritative, filterable per-session data lives in `TrainingSession`, not here). |
| `trainer_slug` | `str` | FK-by-convention to `Trainer.slug` (no DB, so this is a plain string reference validated by a unit test, not a foreign key constraint). |

**Validation rules** (enforced by `test_public_site_data.py`, not at
runtime — this is fixed project content, not user input):
- `slug` is unique across all locations.
- `trainer_slug` matches exactly one entry in `TRAINERS`.
- `groups` is non-empty.

## Trainer

Spec source: Key Entities "Trainer"; FR-020, FR-021.

| Field | Type | Notes |
|---|---|---|
| `slug` | `str` | Stable, unique, kebab-case identifier. |
| `name` | `str` | Full name. |
| `role` | `str` | e.g. "Główny instruktor", "Instruktor". |
| `grade` | `str` | Karate grade/rank, e.g. "3 Dan". |
| `specialization` | `str` | e.g. "Kata i technika stójki". |
| `bio` | `str` | Short biography (a few sentences). |
| `location_slugs` | `tuple[str, ...]` | Locations/sections this trainer teaches at — FK-by-convention to `Location.slug`. |
| `has_photo` | `bool` | Always `False` for this feature (research.md §7 — CSS/SVG placeholder only); kept as an explicit field, not a hardcoded template assumption, so a future feature can add real photos without a data-model change. |

**Validation rules**:
- `slug` unique.
- Every entry in `location_slugs` matches exactly one `Location.slug`.
- `bio` non-empty.

## TrainingSession

Spec source: Key Entities "Training Session"; FR-023–FR-026.

| Field | Type | Notes |
|---|---|---|
| `location_slug` | `str` | FK-by-convention to `Location.slug`. |
| `day` | `str` | One value from a small fixed enum-like set used consistently across the site, e.g. `"Poniedziałek"`, `"Wtorek"`, ... — the exact literal strings the schedule filter's `day` query param matches against (research.md §2). |
| `time_range` | `str` | e.g. `"17:30–18:25"`. |
| `age_level` | `str` | One value from a small fixed set (e.g. `"Początkujący"`, `"Zielony–niebieski pas"`) — the literal strings the schedule filter's `level` query param matches against. |

**Validation rules**:
- `location_slug` matches exactly one `Location.slug`.
- `day` and `age_level` values are drawn from the same small fixed
  vocabularies the filter UI's `<select>` options are generated from (a
  single source of truth: the distinct values actually present across
  `SESSIONS`, so the filter dropdowns can never offer a choice that
  matches zero sessions by construction, except through the empty-state
  path deliberately covered by FR-025/FR-029a for a *combination* of
  otherwise-valid filters).

**Behavior**: `public_site/filters.py::filter_sessions(sessions, *,
location=None, day=None, level=None)` returns the subset matching every
supplied (non-`None`) criterion; an unrecognized filter value simply
matches nothing (safe empty result, never an error).

## NewsPost

Spec source: Key Entities "News Post"; FR-027–FR-031, FR-029a.

| Field | Type | Notes |
|---|---|---|
| `slug` | `str` | Stable, unique, kebab-case identifier — used in the `/aktualnosci/{slug}` detail URL (research.md §4). |
| `title` | `str` | |
| `date` | `datetime.date` | Publication date; list view is sorted newest-first. |
| `category` | `str` | One value from a small fixed set (e.g. `"Sezon"`, `"Obóz"`, `"Egzaminy"`, `"Wydarzenia"`, `"Nowa grupa"`) — the literal strings the news filter's `category` query param matches against. |
| `summary` | `str` | Short summary shown in the list view and the home-page preview. |
| `image_alt` | `str \| None` | If present, an SVG/CSS placeholder is rendered with this `alt` text (research.md §7); `None` means no image block is rendered for this post. |
| `body` | `str` | Full article content (list of paragraph strings, or a single multi-paragraph string — implementation detail for tasks.md), shown only on the detail page. |

**Validation rules**:
- `slug` unique.
- At least 5 posts exist, covering the 5 example topics FR-027 names (new
  season, camp, exam, tournament/event, new beginners group) — asserted in
  `test_public_site_data.py`, not enforced at runtime (fixed content).
- `category` values are drawn from the same fixed vocabulary the filter
  UI's category options are generated from (mirrors `TrainingSession`'s
  approach for `day`/`age_level`).

**Behavior**: `public_site/filters.py::filter_news(posts, *,
category=None)` returns the subset matching the supplied category (or all
posts if `category` is `None`); an unrecognized category matches nothing.

## GlossaryTerm

Spec source: Key Entities "Glossary Term"; FR-018a/FR-018b.

| Field | Type | Notes |
|---|---|---|
| `term` | `str` | The Japanese term as commonly romanized, e.g. `"Mokuso"`. |
| `category` | `str` | e.g. `"Komenda/etykieta"` or `"Technika"` — used to group the glossary for FR-018b's "find without reading top to bottom" requirement. |
| `explanation` | `str` | Plain-language meaning, and where relevant, when/how it's used. |

**Validation rules**:
- At least 8 distinct terms exist (SC-009).
- No duplicate `term` values.

## Relationships (summary)

```text
Location ──trainer_slug──> Trainer
Trainer ──location_slugs──> Location (many-to-many, expressed as two
                              independent string-slug lists rather than a
                              join table — there is no database)
TrainingSession ──location_slug──> Location
NewsPost, GlossaryTerm — standalone, no relationships to other entities
```

All "FK-by-convention" references are plain Python `str` fields matched
against another module's `slug` values — there is no referential-integrity
enforcement at runtime (this is fixed, reviewed project content, not user
input), only at test time via `test_public_site_data.py`.
