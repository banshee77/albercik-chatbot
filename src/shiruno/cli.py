"""`create-admin` seed command (T046) — out-of-band Administrator
provisioning (FR-004a). No HTTP endpoint creates an Administrator row;
this is the only way, run manually:

    uv run python -m shiruno.cli create-admin --username admin

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

from sqlalchemy.exc import IntegrityError

from shiruno.infra.security import hash_password
from shiruno.persistence.database import get_session_factory
from shiruno.persistence.models import Administrator


def create_admin(username: str, password: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(Administrator(username=username, password_hash=hash_password(password)))
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

    create_admin_parser = subparsers.add_parser(
        "create-admin", help="Provision a new Administrator account out-of-band."
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

    if args.command == "create-admin":
        password = args.password if args.password is not None else _prompt_for_password()
        create_admin(args.username, password)


if __name__ == "__main__":
    main()
