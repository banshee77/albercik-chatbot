"""Feature 009-admin-platform-foundation, spec Testing Requirements
#18-#20: proves the two Alembic migrations that introduce `Tenant` are
additive, reversible, and correctly backfill pre-existing data.

Runs against a dedicated, throwaway database created and dropped for this
test alone (not the shared `db-test` schema `db_engine`/`db_session`
build via `Base.metadata.create_all` — running real Alembic migrations
against that same schema would collide with tables it already created).
No real Ollama/GPU/Anthropic/network access is used (pure schema/DB work).
"""

import uuid

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from shiruno.config import get_settings
from shiruno.persistence import database

REPO_ROOT_ENV_DATABASE_URL = "postgresql+psycopg://albercik:albercik@localhost:5433"


@pytest.fixture
def migration_database_url(monkeypatch):
    admin_engine = create_engine(
        f"{REPO_ROOT_ENV_DATABASE_URL}/albercik_test", isolation_level="AUTOCOMMIT"
    )
    db_name = f"tenant_migration_test_{uuid.uuid4().hex}"
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    database_url = f"{REPO_ROOT_ENV_DATABASE_URL}/{db_name}"
    # pgvector is required by the schema's own tables (document_chunks);
    # the migration chain assumes it's already available, same as the
    # real `db`/`db-test` services (persistence/database.py::ensure_pgvector_extension).
    setup_engine = create_engine(database_url)
    with setup_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    setup_engine.dispose()

    # alembic/env.py always sets sqlalchemy.url from get_settings().DATABASE_URL
    # itself (the one source of truth the real app also uses) — so the test
    # database is selected via the same env var, not Config.set_main_option.
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    database.get_engine.cache_clear()

    yield database_url

    get_settings.cache_clear()
    database.get_engine.cache_clear()
    cleanup_engine = create_engine(
        f"{REPO_ROOT_ENV_DATABASE_URL}/albercik_test", isolation_level="AUTOCOMMIT"
    )
    with cleanup_engine.connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :db_name AND pid <> pg_backend_pid()"
            ),
            {"db_name": db_name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    cleanup_engine.dispose()


def test_upgrade_bootstraps_albertos_and_downgrade_is_reversible(
    migration_database_url, monkeypatch
) -> None:
    config = Config("alembic.ini")
    # alembic/env.py does `from logging.config import fileConfig` then
    # calls it whenever `config.config_file_name` is set (true here, since
    # `script_location` etc. must still be read from alembic.ini) — that
    # resets the *global* Python logging configuration as a side effect,
    # which silently breaks `caplog` for every other test in this same
    # pytest process for the rest of the session. env.py is re-imported
    # fresh on every alembic command (`util.load_python_file`), so
    # patching the stdlib function it imports from is enough to no-op
    # just that one call without touching `script_location` resolution.
    monkeypatch.setattr("logging.config.fileConfig", lambda *a, **kw: None)

    # Upgrade to just before the tenant migrations, seed pre-existing rows
    # the way a real deployment would have them before this feature.
    command.upgrade(config, "9e3393cc9c93")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO administrators (id, username, password_hash, is_active) "
                "VALUES (gen_random_uuid(), 'pre-existing-admin', 'x', true)"
            )
        )
        admin_id = connection.execute(
            text("SELECT id FROM administrators WHERE username = 'pre-existing-admin'")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO knowledge_documents "
                "(id, original_filename, uploaded_by_admin_id, status) "
                "VALUES (gen_random_uuid(), 'pre-existing.txt', :admin_id, 'ready')"
            ),
            {"admin_id": admin_id},
        )
    engine.dispose()

    # Full upgrade: this is where Albertos is bootstrapped and pre-existing
    # rows are backfilled (data-model.md "Migration plan").
    command.upgrade(config, "head")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        tenants = connection.execute(text("SELECT name, slug, status FROM tenants")).all()
        assert len(tenants) == 1
        assert tenants[0] == ("Albertos", "albertos", "active")

        admin_tenant_id = connection.execute(
            text("SELECT tenant_id FROM administrators WHERE username = 'pre-existing-admin'")
        ).scalar_one()
        document_tenant_id = connection.execute(
            text(
                "SELECT tenant_id FROM knowledge_documents "
                "WHERE original_filename = 'pre-existing.txt'"
            )
        ).scalar_one()
        albertos_id = connection.execute(
            text("SELECT id FROM tenants WHERE slug = 'albertos'")
        ).scalar_one()

        assert admin_tenant_id == albertos_id
        assert document_tenant_id == albertos_id

        null_admin_tenants = connection.execute(
            text("SELECT count(*) FROM administrators WHERE tenant_id IS NULL")
        ).scalar_one()
        null_document_tenants = connection.execute(
            text("SELECT count(*) FROM knowledge_documents WHERE tenant_id IS NULL")
        ).scalar_one()
        assert null_admin_tenants == 0
        assert null_document_tenants == 0
    engine.dispose()

    # Feature 010-knowledge-base-admin chains two more migrations after
    # e3406f01e5ec — skip past those first so the two relative "-1" steps
    # below still land exactly where this test (predates Feature 010)
    # originally intended: reverting the tenant migrations one at a time.
    command.downgrade(config, "e3406f01e5ec")

    # Downgrade both migrations, in order, and confirm each step succeeds.
    command.downgrade(config, "-1")  # revert knowledge_documents.tenant_id
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'knowledge_documents' AND column_name = 'tenant_id'"
            )
        ).scalar_one()
        assert exists == 0
        # tenants + administrators.tenant_id must still be intact.
        assert connection.execute(text("SELECT count(*) FROM tenants")).scalar_one() == 1
    engine.dispose()

    command.downgrade(config, "-1")  # revert tenants + administrators.tenant_id
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        tenants_table_exists = connection.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_name = 'tenants'")
        ).scalar_one()
        admin_tenant_column_exists = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'administrators' AND column_name = 'tenant_id'"
            )
        ).scalar_one()
        assert tenants_table_exists == 0
        assert admin_tenant_column_exists == 0
        # Pre-existing data itself (not the tenant columns) survived both downgrades.
        remaining_admin = connection.execute(
            text("SELECT username FROM administrators WHERE username = 'pre-existing-admin'")
        ).scalar_one()
        assert remaining_admin == "pre-existing-admin"
    engine.dispose()

    # Re-upgrading to head after a full downgrade must succeed cleanly.
    command.upgrade(config, "head")
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        tenants = connection.execute(text("SELECT slug FROM tenants")).all()
        assert [row[0] for row in tenants] == ["albertos"]
    engine.dispose()
