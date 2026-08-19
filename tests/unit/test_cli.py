"""Pre-Phase-5 security checkpoint (2026-08-17): unit tests for cli.py's
credential handling — secure interactive prompting is the default path,
`--password` is an explicit opt-out. Pure logic, no DB, no real terminal
(getpass.getpass is monkeypatched, never a real TTY read).

The `create-tenant`/`create-admin --tenant` DB-backed tests below (feature
009-admin-platform-foundation, contracts/cli-provisioning-contract.md) are
the one exception — `cli.py`'s provisioning functions own their session
via `get_session_factory()` with no injection point, so they're pointed at
the real `db-test` service the same way
`tests/integration/test_database_session_commit.py` already does, rather
than the hand-managed `db_session` fixture used everywhere else.
"""

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as OrmSession

from shiruno import cli
from shiruno.config import get_settings
from shiruno.persistence import database
from shiruno.persistence.models import Administrator, Tenant

TEST_DATABASE_URL = "postgresql+psycopg://albercik:albercik@localhost:5433/albercik_test"


def _point_cli_at_test_db(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    get_settings.cache_clear()
    database.get_engine.cache_clear()


def test_prompt_for_password_returns_password_when_confirmed(monkeypatch) -> None:
    inputs = iter(["secret123", "secret123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(inputs))

    assert cli._prompt_for_password() == "secret123"


def test_prompt_for_password_rejects_mismatched_confirmation(monkeypatch) -> None:
    inputs = iter(["secret123", "something-else"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(inputs))

    with pytest.raises(SystemExit):
        cli._prompt_for_password()


def test_prompt_for_password_rejects_empty_password(monkeypatch) -> None:
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "")

    with pytest.raises(SystemExit):
        cli._prompt_for_password()


def test_main_prompts_for_password_when_flag_omitted(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        cli,
        "create_admin",
        lambda username, password, tenant_slug: calls.append((username, password, tenant_slug)),
    )
    monkeypatch.setattr(cli, "_prompt_for_password", lambda: "prompted-secret")

    cli.main(["create-admin", "--tenant", "albertos", "--username", "admin"])

    assert calls == [("admin", "prompted-secret", "albertos")]


def test_main_uses_password_flag_without_prompting_when_provided(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []
    prompted = {"called": False}
    monkeypatch.setattr(
        cli,
        "create_admin",
        lambda username, password, tenant_slug: calls.append((username, password, tenant_slug)),
    )

    def _fail_if_prompted() -> str:
        prompted["called"] = True
        return "should-not-be-used"

    monkeypatch.setattr(cli, "_prompt_for_password", _fail_if_prompted)

    cli.main(
        [
            "create-admin",
            "--tenant",
            "albertos",
            "--username",
            "admin",
            "--password",
            "insecure-dev-only",
        ]
    )

    assert calls == [("admin", "insecure-dev-only", "albertos")]
    assert prompted["called"] is False


def test_main_requires_tenant_flag_for_create_admin() -> None:
    with pytest.raises(SystemExit):
        cli.main(["create-admin", "--username", "admin", "--password", "x"])


def test_main_dispatches_create_tenant(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "create_tenant", lambda name, slug: calls.append((name, slug)))

    cli.main(["create-tenant", "--name", "Albertos", "--slug", "albertos"])

    assert calls == [("Albertos", "albertos")]


def test_create_tenant_creates_an_active_tenant(db_engine, monkeypatch) -> None:
    _point_cli_at_test_db(monkeypatch)
    slug = f"cli-tenant-{uuid.uuid4()}"

    cli.create_tenant("CLI Test Tenant", slug)

    verify_engine = create_engine(TEST_DATABASE_URL)
    try:
        with verify_engine.connect() as connection, OrmSession(bind=connection) as session:
            tenant = session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one()
            assert tenant.name == "CLI Test Tenant"
            assert tenant.status.value == "active"
    finally:
        verify_engine.dispose()


def test_create_tenant_duplicate_slug_fails_clearly_without_duplicating(
    db_engine, monkeypatch, capsys
) -> None:
    _point_cli_at_test_db(monkeypatch)
    slug = f"cli-dup-tenant-{uuid.uuid4()}"
    cli.create_tenant("First", slug)

    with pytest.raises(SystemExit):
        cli.create_tenant("Second", slug)

    stderr = capsys.readouterr().err
    assert "already exists" in stderr

    verify_engine = create_engine(TEST_DATABASE_URL)
    try:
        with verify_engine.connect() as connection, OrmSession(bind=connection) as session:
            count = len(session.execute(select(Tenant).where(Tenant.slug == slug)).all())
            assert count == 1
    finally:
        verify_engine.dispose()


def test_create_admin_with_missing_tenant_fails_clearly_and_creates_nothing(
    db_engine, monkeypatch, capsys
) -> None:
    _point_cli_at_test_db(monkeypatch)
    username = f"cli-orphan-admin-{uuid.uuid4()}"

    with pytest.raises(SystemExit):
        cli.create_admin(username, "irrelevant-password", "no-such-tenant-slug")

    stderr = capsys.readouterr().err
    assert "no tenant with slug" in stderr

    verify_engine = create_engine(TEST_DATABASE_URL)
    try:
        with verify_engine.connect() as connection, OrmSession(bind=connection) as session:
            found = session.execute(
                select(Administrator).where(Administrator.username == username)
            ).scalar_one_or_none()
            assert found is None
    finally:
        verify_engine.dispose()


def test_create_admin_with_existing_tenant_succeeds_with_correct_tenant_id(
    db_engine, monkeypatch, capsys
) -> None:
    _point_cli_at_test_db(monkeypatch)
    slug = f"cli-owner-tenant-{uuid.uuid4()}"
    cli.create_tenant("Owner Tenant", slug)
    username = f"cli-admin-{uuid.uuid4()}"

    cli.create_admin(username, "irrelevant-password", slug)

    captured = capsys.readouterr()
    assert "irrelevant-password" not in captured.out
    assert "irrelevant-password" not in captured.err

    verify_engine = create_engine(TEST_DATABASE_URL)
    try:
        with verify_engine.connect() as connection, OrmSession(bind=connection) as session:
            tenant = session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one()
            admin = session.execute(
                select(Administrator).where(Administrator.username == username)
            ).scalar_one()
            assert admin.tenant_id == tenant.id
            assert "irrelevant-password" not in admin.password_hash
    finally:
        verify_engine.dispose()
