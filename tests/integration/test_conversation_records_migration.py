"""T013 — proves the `add_conversation_records` Alembic migration (feature
011-conversations-analytics, data-model.md "Migration plan") is additive,
fully reversible, and creates the expected table/types/indexes. No
backfill to verify — the table has no historical rows by construction.

Mirrors `specs/010-knowledge-base-admin`'s `test_knowledge_document_migration.py`
pattern: a dedicated, throwaway database created and dropped for this test
alone.
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
    db_name = f"conversation_records_migration_test_{uuid.uuid4().hex}"
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


def test_upgrade_creates_table_and_downgrade_is_reversible(
    migration_database_url, monkeypatch
) -> None:
    config = Config("alembic.ini")
    # See test_tenant_migration.py's identical comment: alembic/env.py's
    # fileConfig() call resets global Python logging as a side effect,
    # silently breaking caplog for the rest of this pytest process.
    monkeypatch.setattr("logging.config.fileConfig", lambda *a, **kw: None)

    command.upgrade(config, "7a4d6c1e8b2f")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        table_exists = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name = 'conversation_records'"
            )
        ).scalar_one()
        assert table_exists == 0
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        columns = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'conversation_records'"
            )
        ).all()
        column_names = {row[0] for row in columns}
        assert column_names == {
            "id",
            "tenant_id",
            "request_id",
            "question",
            "normalized_question",
            "outcome",
            "answer",
            "sources",
            "safe_failure_category",
            "provider_name",
            "provider_model",
            "input_tokens",
            "output_tokens",
            "provider_metrics",
            "latency_ms",
            "created_at",
        }

        indexes = connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'conversation_records'")
        ).all()
        index_names = {row[0] for row in indexes}
        assert "ix_conversation_records_tenant_id_created_at" in index_names
        assert "ix_conversation_records_tenant_id_outcome_created_at" in index_names
        assert "ix_conversation_records_tenant_id_normalized_question" in index_names

        unique_constraint = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.table_constraints "
                "WHERE table_name = 'conversation_records' "
                "AND constraint_name = 'uq_conversation_records_request_id'"
            )
        ).scalar_one()
        assert unique_constraint == 1

        enum_types = connection.execute(
            text(
                "SELECT typname FROM pg_type "
                "WHERE typname IN ('conversation_outcome', 'conversation_failure_category')"
            )
        ).all()
        assert {row[0] for row in enum_types} == {
            "conversation_outcome",
            "conversation_failure_category",
        }

        row_count = connection.execute(
            text("SELECT count(*) FROM conversation_records")
        ).scalar_one()
        assert row_count == 0
    engine.dispose()

    command.downgrade(config, "-1")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        table_exists = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name = 'conversation_records'"
            )
        ).scalar_one()
        assert table_exists == 0

        enum_types = connection.execute(
            text(
                "SELECT typname FROM pg_type "
                "WHERE typname IN ('conversation_outcome', 'conversation_failure_category')"
            )
        ).all()
        assert enum_types == []

        # provider_name (the reused, pre-existing enum type) must survive —
        # this migration must never drop a type it doesn't own.
        provider_name_exists = connection.execute(
            text("SELECT count(*) FROM pg_type WHERE typname = 'provider_name'")
        ).scalar_one()
        assert provider_name_exists == 1
    engine.dispose()

    # Re-upgrading to head after a full downgrade must succeed cleanly.
    command.upgrade(config, "head")
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        table_exists = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name = 'conversation_records'"
            )
        ).scalar_one()
        assert table_exists == 1
    engine.dispose()
