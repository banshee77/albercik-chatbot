"""Shared pytest fixtures (research.md §8).

- `fake_llm_provider` / `fake_embedding_provider`: the only `LLMProvider`/
  `EmbeddingProvider` implementations any automated test uses. No unit,
  integration, or contract test constructs `AnthropicLLMProvider` or
  `LocalSentenceTransformerEmbeddingProvider` (Design Constraint 2).
- `test_app` / `async_client`: an app built via `create_app(...)` with
  fakes passed in directly — the real-provider construction path in
  `main.py` is never exercised by tests.
- `db_engine` / `db_session`: a real PostgreSQL + `pgvector` instance
  (`db-test` in docker-compose.yml) for integration tests — there is no
  in-memory substitute for `pgvector`'s vector operators.

`AUTH_JWT_SECRET` has no default in `config.py` (pre-Phase-5 security
checkpoint, 2026-08-17) — the application must never silently run with a
secret anyone could read in source history. The test suite still needs to
work in a fresh checkout/CI with no `.env` file present, so a test-only
default is set here, as the very first thing this module does, before any
import that could construct `Settings()`. This value is never used
outside the test process.
"""

import os

os.environ.setdefault("AUTH_JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")

from collections.abc import Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from shiruno.main import create_app
from shiruno.persistence.models import Base
from tests.fakes.fake_embedding_provider import FakeEmbeddingProvider
from tests.fakes.fake_llm_provider import FakeLLMProvider

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://albercik:albercik@localhost:5433/albercik_test",
)


@pytest.fixture
def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def fake_embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def test_app(fake_llm_provider: FakeLLMProvider, fake_embedding_provider: FakeEmbeddingProvider):
    return create_app(llm_provider=fake_llm_provider, embedding_provider=fake_embedding_provider)


@pytest_asyncio.fixture
async def async_client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_async_client(test_app, db_session):
    """Like `async_client`, but also overrides the app's `get_session`
    dependency to the same transactional `db_session` used for seeding —
    needed by any contract test that seeds rows directly into Postgres
    (e.g. US1's chat outcomes, T030) rather than going through an upload
    endpoint. The route sees the exact rows the test just added, without a
    commit, and everything rolls back with `db_session` at teardown."""
    from shiruno.persistence.database import get_session

    test_app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    test_app.dependency_overrides.pop(get_session, None)


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped: one real Postgres+pgvector schema for the whole
    integration run (research.md §8)."""
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session]:  # type: ignore[valid-type]
    """One session per test, wrapped in a transaction rolled back afterward
    so tests never leak state into each other."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
