# Contract: Runtime & Developer-Facing Paths (new, established by this feature)

This is the contract Feature 008 *introduces*: the set of paths, commands,
and identifiers that every script, config file, and piece of documentation
must agree on after the package rename (research.md §1) is adopted. Every
row is a "must all say the same thing" checkable pair.

| Concern | Before this feature | After this feature |
|---|---|---|
| Installable package / import root | `albercik_chatbot` | `shiruno` |
| Distribution name (`pyproject.toml` `[project].name`) | `albercik-chatbot` | `shiruno` |
| Console script | `albercik-chatbot = "albercik_chatbot:main"` | `shiruno = "shiruno:main"` |
| CLI invocation | `uv run python -m albercik_chatbot.cli create-admin ...` | `uv run python -m shiruno.cli create-admin ...` |
| ASGI factory target (Dockerfile `CMD`, local `uvicorn` invocation) | `albercik_chatbot.main:create_app` | `shiruno.main:create_app` |
| Alembic env imports (`alembic/env.py`) | `from albercik_chatbot.config import get_settings`, `from albercik_chatbot.persistence.models import Base` | `from shiruno.config import get_settings`, `from shiruno.persistence.models import Base` |
| `mypy`/`ruff` target paths | `src`, `src/albercik_chatbot` implied by `src` layout | `src`, `src/shiruno` implied by `src` layout (no config value literally names the old package, so no change needed beyond the directory itself) |
| Eval tooling imports (`scripts/run_eval.py`, `scripts/rag_calibration.py`) | `from albercik_chatbot....` | `from shiruno....` |
| Eval subprocess CLI reference (`scripts/run_eval.py`'s `"albercik_chatbot.cli"` arg) | `albercik_chatbot.cli` | `shiruno.cli` |
| Test imports/fixtures (`tests/**`) | `from albercik_chatbot....` | `from shiruno....` |
| Docker image build context | `COPY . .` (path-agnostic — unaffected) | unchanged |

## Explicitly NOT part of this contract (unchanged, see research.md §4)

- PostgreSQL user/password/database names (`albercik`, `albercik_test`) in
  `docker-compose.yml`, `.env`/`.env.example`'s `DATABASE_URL`, and
  `tests/conftest.py`'s hardcoded test DB URL.
- Docker Compose service names (`db`, `db-test`, `ollama`, `ollama-init`,
  `app`) and named volumes (`db-data`, `ollama-data`).
- Any environment variable name (`DATABASE_URL`, `LLM_PROVIDER`,
  `OLLAMA_MODEL`, `ANTHROPIC_API_KEY`, etc.) — only their *values* referring
  to the old module path (none currently do) would be in scope, and none
  do.

## Verification

- `grep -rn "albercik_chatbot" --include='*.py' --include='*.toml' --include='*.ini' --include='*.yml' --include='Dockerfile'` (excluding `specs/00[1-7]` historical specs) returns zero matches after the refactor (SC-007).
- `docker compose config` validates successfully.
- `docker compose up -d` brings up the full stack and `GET /health` returns 200 (quickstart.md).
- `uv run alembic upgrade head` succeeds against a fresh `db-test` database.
- `uv run python -m shiruno.cli create-admin --username <x>` succeeds.
