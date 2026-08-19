# Quickstart: Validating Feature 008 (Shiruno Repository & Product Architecture)

This is a behavior-preservation refactor. There is no new feature to
"try" — the validation goal is proving nothing changed except names,
structure, and documentation. Run this after the refactor is implemented.

## Prerequisites

- `uv` installed, Docker + Docker Compose installed.
- A `.env` populated from `.env.example` (unchanged variable names — see
  `contracts/runtime-paths.md`).

## 1. No stale import paths remain

```bash
grep -rn "albercik_chatbot" \
  --include='*.py' --include='*.toml' --include='*.ini' \
  --include='*.yml' --include='*.yaml' --include='Dockerfile' \
  --include='*.cfg' --include='*.sh' . \
  | grep -v -E '^\./(\.git|\.venv|\.mypy_cache|\.pytest_cache|\.ruff_cache|specs/00[1-7])' \
  | grep -v 'tests/unit/test_no_stale_import_paths.py'
```

(The one expected exception is `tests/unit/test_no_stale_import_paths.py`
itself — the regression test added by this feature necessarily names the
string it checks for the *absence* of everywhere else.)

**Expected**: no output. (SC-007, FR-029, FR-032)

## 2. Package imports correctly from its new path

```bash
uv sync
uv run python -c "from shiruno.main import create_app; create_app; print('OK')"
```

**Expected**: prints `OK` with no import error. (Testing minimum: "the
renamed package imports correctly")

## 3. Full automated test suite passes unmodified in assertion semantics

```bash
uv run pytest
```

**Expected**: same pass count and same test identities (module-relative
names may differ if files moved, but no test was deleted or had an
assertion removed) as immediately before the refactor. (SC-001, FR-020)

## 4. Lint, format, and type-check gates pass

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

**Expected**: all three succeed against the new `src/shiruno` path.
(Acceptance criterion 14)

## 5. CLI works from the new package path

```bash
docker compose up -d db
uv run alembic upgrade head
uv run python -m shiruno.cli create-admin --username quickstart-admin
```

**Expected**: `Administrator 'quickstart-admin' created.` (Testing
minimum: "CLI commands still work from the new package path")

## 6. Alembic imports metadata correctly

```bash
uv run alembic current
uv run alembic history
```

**Expected**: both succeed; `alembic/env.py` resolves
`shiruno.config.get_settings` and `shiruno.persistence.models.Base`
without error. (Testing minimum: "Alembic imports metadata correctly")

## 7. Docker Compose builds and runs the full stack

```bash
docker compose config          # validates syntax
docker compose up -d           # db, ollama, ollama-init, app
curl -sf localhost:8000/health
```

**Expected**: `docker compose config` succeeds; the stack starts; `/health`
returns 200. Confirms `Dockerfile`'s `CMD` correctly targets
`shiruno.main:create_app`. (SC-006, Acceptance criterion 11)

## 8. Public website routes still work

```bash
curl -sf localhost:8000/ | grep -qi "albertos" && echo "home OK"
curl -sf localhost:8000/trenerzy | grep -qi "trener" && echo "trainers OK"
curl -sf localhost:8000/grafik | grep -qi "grafik\|harmonogram" && echo "schedule OK"
```

**Expected**: all three print their `OK` line. (Acceptance criterion 6)

## 9. `POST /api/v1/chat` behaves unchanged across outcome types

Exercise the existing contract test suite (already covers this more
thoroughly than a manual curl) or, ad hoc:

```bash
curl -s localhost:8000/api/v1/chat -H 'Content-Type: application/json' \
  -d '{"question": "Cześć"}' | python -m json.tool     # expect outcome: small_talk
curl -s localhost:8000/api/v1/chat -H 'Content-Type: application/json' \
  -d '{"question": "Jakie są ceny akcji Apple?"}' | python -m json.tool  # expect outcome: out_of_scope
```

**Expected**: outcomes match pre-refactor behavior exactly; public
responses never include a `sources` field. (SC-002, Acceptance criterion
7, FR-013)

## 10. Evaluation tooling runs from its new import paths

```bash
uv run python scripts/run_eval.py --help
```

**Expected**: runs without an import error, still referencing
`shiruno.cli` internally rather than `albercik_chatbot.cli` (contracts/
runtime-paths.md). Full benchmark re-run against `eval/questions.jsonl` is
optional for this quickstart (requires a real LLM backend) but, if run,
must reproduce the frozen baseline in `eval/README.md`. (SC-003, FR-019)

## 11. New engineer comprehension check

Hand a colleague (or re-read cold) only `README.md` and a `tree -L 2 src
docs`. Confirm they can state, unprompted: Shiruno is the reusable
product; Albertos is the first customer/reference implementation; and
which top-level modules are which. (SC-004, User Story 2)

## Cleanup

```bash
docker compose down
```
