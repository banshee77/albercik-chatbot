"""Pre-Phase-5 security checkpoint (2026-08-17): unit tests for cli.py's
credential handling — secure interactive prompting is the default path,
`--password` is an explicit opt-out. Pure logic, no DB, no real terminal
(getpass.getpass is monkeypatched, never a real TTY read).
"""

import pytest

from albercik_chatbot import cli


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
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        cli, "create_admin", lambda username, password: calls.append((username, password))
    )
    monkeypatch.setattr(cli, "_prompt_for_password", lambda: "prompted-secret")

    cli.main(["create-admin", "--username", "admin"])

    assert calls == [("admin", "prompted-secret")]


def test_main_uses_password_flag_without_prompting_when_provided(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    prompted = {"called": False}
    monkeypatch.setattr(
        cli, "create_admin", lambda username, password: calls.append((username, password))
    )

    def _fail_if_prompted() -> str:
        prompted["called"] = True
        return "should-not-be-used"

    monkeypatch.setattr(cli, "_prompt_for_password", _fail_if_prompted)

    cli.main(["create-admin", "--username", "admin", "--password", "insecure-dev-only"])

    assert calls == [("admin", "insecure-dev-only")]
    assert prompted["called"] is False
