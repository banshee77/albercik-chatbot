"""`create-tenant`/`create-admin` provisioning commands (T046; feature
009-admin-platform-foundation FR-003, FR-009) — out-of-band, no HTTP
endpoint creates either a Tenant or an Administrator row; these commands
are the only way, run manually:

    uv run python -m shiruno.cli create-tenant --name "Albertos" --slug albertos
    uv run python -m shiruno.cli create-admin --tenant albertos --username admin

The password is prompted for interactively (`getpass`, no echo) and
confirmed — it is never required on the command line, so it never lands in
shell history or process listings (`ps`), and it is never logged (only the
username is printed, on success or on a duplicate-username failure).

For automated/dev-only scenarios, `--password` is also accepted, but is
NOT the documented default and IS insecure (visible in shell history and
`ps` output) — see its `--help` text.

Deliberately not a full user-management system: no registration, no
password reset, no roles — a single privilege tier, provisioned one
account at a time by whoever has shell access to the deployment.
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from shiruno.infra.security import hash_password
from shiruno.persistence.database import get_session_factory
from shiruno.persistence.models import Administrator, Tenant


def create_tenant(name: str, slug: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(Tenant(name=name, slug=slug))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            print(f"Error: a tenant with slug '{slug}' already exists.", file=sys.stderr)
            raise SystemExit(1) from None

    print(f"Tenant '{name}' (slug: '{slug}') created.")


def create_admin(username: str, password: str, tenant_slug: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.slug == tenant_slug)
        ).scalar_one_or_none()
        if tenant is None:
            print(f"Error: no tenant with slug '{tenant_slug}' exists.", file=sys.stderr)
            raise SystemExit(1)

        session.add(
            Administrator(
                username=username, password_hash=hash_password(password), tenant_id=tenant.id
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            print(f"Error: an administrator named '{username}' already exists.", file=sys.stderr)
            raise SystemExit(1) from None

    print(f"Administrator '{username}' created.")


def _prompt_for_password() -> str:
    password = getpass.getpass("Password: ")
    if not password:
        print("Error: password must not be empty.", file=sys.stderr)
        raise SystemExit(1)
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Error: passwords do not match.", file=sys.stderr)
        raise SystemExit(1)
    return password


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m shiruno.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_tenant_parser = subparsers.add_parser(
        "create-tenant", help="Provision a new Tenant (customer organization) out-of-band."
    )
    create_tenant_parser.add_argument("--name", required=True)
    create_tenant_parser.add_argument("--slug", required=True)

    create_admin_parser = subparsers.add_parser(
        "create-admin", help="Provision a new Administrator account out-of-band."
    )
    create_admin_parser.add_argument(
        "--tenant", required=True, help="Slug of the tenant this administrator belongs to."
    )
    create_admin_parser.add_argument("--username", required=True)
    create_admin_parser.add_argument(
        "--password",
        default=None,
        help=(
            "INSECURE, development/automation-only: passes the password "
            "directly on the command line, where it is visible in shell "
            "history and process listings. Omit this flag to be prompted "
            "securely instead (the documented default behavior)."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "create-tenant":
        create_tenant(args.name, args.slug)
    elif args.command == "create-admin":
        password = args.password if args.password is not None else _prompt_for_password()
        create_admin(args.username, password, args.tenant)


if __name__ == "__main__":
    main()
