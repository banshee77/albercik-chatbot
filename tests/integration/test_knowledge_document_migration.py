"""T030 — proves the two Alembic migrations feature 010-knowledge-base-admin
adds (`add_knowledge_document_lifecycle_metadata`,
`add_knowledge_document_replaces_document_id`) are additive, reversible,
and backfill pre-existing rows correctly (data-model.md "Migration plan").

Mirrors `specs/009-admin-platform-foundation`'s `test_tenant_migration.py`
pattern: a dedicated, throwaway database created and dropped for this test
alone, since running real Alembic migrations against the shared
`Base.metadata.create_all` `db_engine`/`db_session` schema would collide
with tables it already created.
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
    db_name = f"kb_admin_migration_test_{uuid.uuid4().hex}"
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    database_url = f"{REPO_ROOT_ENV_DATABASE_URL}/{db_name}"
    setup_engine = create_engine(database_url)
    with setup_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    setup_engine.dispose()

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


def test_upgrade_backfills_pre_existing_rows_and_downgrade_is_reversible(
    migration_database_url, monkeypatch
) -> None:
    config = Config("alembic.ini")
    # See test_tenant_migration.py's identical comment: alembic/env.py's
    # fileConfig() call resets global Python logging as a side effect,
    # silently breaking caplog for the rest of this pytest process.
    monkeypatch.setattr("logging.config.fileConfig", lambda *a, **kw: None)

    # Upgrade to just before this feature's two migrations, seed
    # pre-existing rows the way a real deployment would have them —
    # including one already-`ready` and one non-`ready` document, to
    # exercise indexed_at's conditional backfill.
    command.upgrade(config, "e3406f01e5ec")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        # bacc16af8815 (already applied, on the way to e3406f01e5ec) bootstraps
        # the Albertos tenant itself — reuse it rather than inserting a
        # second, colliding row.
        tenant_id = connection.execute(
            text("SELECT id FROM tenants WHERE slug = 'albertos'")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO administrators (id, username, password_hash, is_active, tenant_id) "
                "VALUES (gen_random_uuid(), 'pre-existing-admin', 'x', true, :tenant_id)"
            ),
            {"tenant_id": tenant_id},
        )
        admin_id = connection.execute(
            text("SELECT id FROM administrators WHERE username = 'pre-existing-admin'")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO knowledge_documents "
                "(id, original_filename, uploaded_by_admin_id, tenant_id, status) "
                "VALUES (gen_random_uuid(), 'ready-doc.txt', :admin_id, :tenant_id, 'ready')"
            ),
            {"admin_id": admin_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO knowledge_documents "
                "(id, original_filename, uploaded_by_admin_id, tenant_id, status) "
                "VALUES (gen_random_uuid(), 'failed-doc.txt', :admin_id, :tenant_id, 'failed')"
            ),
            {"admin_id": admin_id, "tenant_id": tenant_id},
        )
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT original_filename, status, uploaded_at, updated_at, indexed_at, "
                "safe_error_message, replaces_document_id FROM knowledge_documents "
                "ORDER BY original_filename"
            )
        ).all()
        assert len(rows) == 2
        failed_row, ready_row = rows

        assert failed_row.original_filename == "failed-doc.txt"
        assert failed_row.updated_at == failed_row.uploaded_at
        assert failed_row.indexed_at is None
        assert failed_row.safe_error_message is None
        assert failed_row.replaces_document_id is None

        assert ready_row.original_filename == "ready-doc.txt"
        assert ready_row.updated_at == ready_row.uploaded_at
        assert ready_row.indexed_at == ready_row.uploaded_at
        assert ready_row.safe_error_message is None
        assert ready_row.replaces_document_id is None

        null_updated_at = connection.execute(
            text("SELECT count(*) FROM knowledge_documents WHERE updated_at IS NULL")
        ).scalar_one()
        assert null_updated_at == 0
    engine.dispose()

    # Downgrade both migrations, in order, and confirm each step succeeds
    # and pre-existing data survives.
    command.downgrade(config, "-1")  # revert replaces_document_id
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'knowledge_documents' AND column_name = 'replaces_document_id'"
            )
        ).scalar_one()
        assert exists == 0
        remaining = connection.execute(
            text("SELECT count(*) FROM knowledge_documents")
        ).scalar_one()
        assert remaining == 2
    engine.dispose()

    command.downgrade(config, "-1")  # revert updated_at/indexed_at/safe_error_message
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        for column in ("updated_at", "indexed_at", "safe_error_message"):
            exists = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'knowledge_documents' AND column_name = :column"
                ),
                {"column": column},
            ).scalar_one()
            assert exists == 0
        remaining_filenames = connection.execute(
            text("SELECT original_filename FROM knowledge_documents ORDER BY original_filename")
        ).all()
        assert [row[0] for row in remaining_filenames] == ["failed-doc.txt", "ready-doc.txt"]
    engine.dispose()

    # Re-upgrading to head after a full downgrade must succeed cleanly.
    command.upgrade(config, "head")
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM knowledge_documents WHERE updated_at IS NOT NULL")
        ).scalar_one()
        assert count == 2
    engine.dispose()
