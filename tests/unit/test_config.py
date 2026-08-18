"""Pre-Phase-5 security checkpoint (2026-08-17): AUTH_JWT_SECRET
requiredness and minimum-length validation. Constructs `Settings` directly
with explicit keyword overrides (which take priority over `.env`/the
environment in pydantic-settings), so these tests are independent of
whatever's actually in the real `.env` file.
"""

import pytest
from pydantic import ValidationError

from albercik_chatbot.config import Settings


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(AUTH_JWT_SECRET="too-short")  # type: ignore[call-arg]


def test_empty_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        Settings(AUTH_JWT_SECRET="")  # type: ignore[call-arg]


def test_whitespace_only_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        Settings(AUTH_JWT_SECRET="   " * 20)  # type: ignore[call-arg]


def test_sufficiently_long_jwt_secret_is_accepted() -> None:
    secret = "a" * 32
    settings = Settings(AUTH_JWT_SECRET=secret)  # type: ignore[call-arg]
    assert settings.AUTH_JWT_SECRET == secret


def test_jwt_secret_exactly_at_minimum_length_is_accepted() -> None:
    settings = Settings(AUTH_JWT_SECRET="x" * 32)  # type: ignore[call-arg]
    assert len(settings.AUTH_JWT_SECRET) == 32


def test_jwt_secret_one_below_minimum_length_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(AUTH_JWT_SECRET="x" * 31)  # type: ignore[call-arg]
