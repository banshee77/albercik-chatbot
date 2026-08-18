from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Populated in Foundational (T008 config.py, T010 models.py). Imported here
# so `alembic revision --autogenerate` and `alembic upgrade` share the same
# Settings/metadata the application itself uses — one source of truth for
# DATABASE_URL (FR-051) and the schema (data-model.md).
from albercik_chatbot.config import get_settings
from albercik_chatbot.persistence.models import Base
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# NOTE: alembic autogenerate does not add third-party column-type imports
# automatically. Any future `alembic revision --autogenerate` that touches
# `document_chunks.embedding` will need `import pgvector.sqlalchemy` added
# to the generated script by hand (see the initial migration for the
# pattern) — not worth a custom render_item hook for one column (Principle
# XIII, Simplicity for MVP).

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
