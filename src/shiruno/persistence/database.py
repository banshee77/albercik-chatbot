from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    """One engine per process (one per distinct URL, in practice one)."""
    from albercik_chatbot.config import get_settings

    url = database_url or get_settings().DATABASE_URL
    return create_engine(url, pool_pre_ping=True)


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session]:
    """FastAPI dependency: one session per request, one transaction per
    request — commits once the route completes successfully, rolls back
    if any exception propagates (including our own `AppError` subclasses),
    then always closes.

    Pre-Phase-5 finding: this used to only `close()`, never `commit()`.
    Every automated test overrides this dependency with a hand-managed,
    never-committing session (`tests/conftest.py::db_session`), so nothing
    ever exercised the real code path — in an actual deployment, every
    write in the entire app (document uploads/deletes, and now rate-limit
    counters, usage records, budget-relevant rows) would have been
    silently discarded the moment each request's session closed, since a
    SQLAlchemy transaction is not durable until `commit()` is called.
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_pgvector_extension(engine: Engine) -> None:
    """Enable the pgvector extension (idempotent) — data-model.md."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
