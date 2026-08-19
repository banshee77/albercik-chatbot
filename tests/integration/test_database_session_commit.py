"""Pre-Phase-5 finding, fixed: `persistence/database.py::get_session()`
used to only `close()` a request's session, never `commit()` — meaning
nothing written during a real request would have survived past that
request in an actual deployment (a SQLAlchemy transaction isn't durable
until `commit()`). Every other test overrides `get_session` with the
hand-managed `db_session` fixture, which never needed a real commit to
work, so nothing else in the suite exercises this dependency as FastAPI
actually calls it. This test does: it drives the real generator exactly
the way FastAPI's dependency-with-yield machinery does (advance past
`yield` for success, `.throw()` an exception for failure) and verifies
durability from a completely independent connection.
"""

import uuid

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session as OrmSession

from shiruno.config import get_settings
from shiruno.persistence import database
from shiruno.persistence.database import get_session
from shiruno.persistence.models import Administrator

TEST_DATABASE_URL = "postgresql+psycopg://albercik:albercik@localhost:5433/albercik_test"


def _point_get_session_at_test_db(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    get_settings.cache_clear()
    database.get_engine.cache_clear()


def _row_exists(username: str) -> bool:
    verify_engine = create_engine(TEST_DATABASE_URL)
    try:
        with verify_engine.connect() as connection, OrmSession(bind=connection) as verify_session:
            found = verify_session.execute(
                select(Administrator).where(Administrator.username == username)
            ).scalar_one_or_none()
            return found is not None
    finally:
        verify_engine.dispose()


def _delete_row(username: str) -> None:
    cleanup_engine = create_engine(TEST_DATABASE_URL)
    try:
        with cleanup_engine.begin() as connection:
            connection.execute(delete(Administrator).where(Administrator.username == username))
    finally:
        cleanup_engine.dispose()


def test_get_session_commits_pending_work_on_success(db_engine, monkeypatch) -> None:
    # `db_engine` isn't used directly (this test drives get_session()'s own
    # independent engine) — it's a fixture dependency purely to guarantee
    # the schema already exists in db-test before this test runs.
    _point_get_session_at_test_db(monkeypatch)
    username = f"commit-regression-{uuid.uuid4()}"

    generator = get_session()
    session = next(generator)
    session.add(Administrator(username=username, password_hash="x"))
    session.flush()  # visible within this session, NOT yet durable

    # Mirrors FastAPI advancing the generator past `yield` once the route
    # handler returns successfully.
    try:
        next(generator)
    except StopIteration:
        pass

    get_settings.cache_clear()
    database.get_engine.cache_clear()
    try:
        assert _row_exists(username) is True
    finally:
        _delete_row(username)


def test_get_session_rolls_back_on_exception(db_engine, monkeypatch) -> None:
    _point_get_session_at_test_db(monkeypatch)
    username = f"rollback-regression-{uuid.uuid4()}"

    generator = get_session()
    session = next(generator)
    session.add(Administrator(username=username, password_hash="x"))
    session.flush()

    # Mirrors FastAPI throwing a route-handler exception into the
    # dependency generator at its `yield` point.
    try:
        generator.throw(RuntimeError("simulated route failure"))
    except RuntimeError:
        pass

    get_settings.cache_clear()
    database.get_engine.cache_clear()
    assert _row_exists(username) is False
