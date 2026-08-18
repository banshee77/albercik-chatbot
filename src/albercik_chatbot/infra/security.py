"""Password hashing and JWT issue/verify (research.md §1).

Used only by US2's auth flow (cli.py, api/routers/auth.py, api/deps.py) —
implemented here as cross-cutting infra per plan.md's project structure.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


@dataclass(frozen=True)
class IssuedToken:
    access_token: str
    expires_in: int


def issue_access_token(
    *, administrator_id: uuid.UUID, secret: str, algorithm: str, expire_minutes: int
) -> IssuedToken:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=expire_minutes)
    payload = {"sub": str(administrator_id), "iat": now, "exp": expires_at}
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return IssuedToken(access_token=token, expires_in=expire_minutes * 60)


def verify_access_token(token: str, *, secret: str, algorithm: str) -> uuid.UUID | None:
    """Returns the administrator id encoded in the token, or None if the
    token is missing, malformed, expired, or has an invalid signature — the
    caller (api/deps.py) maps that to a generic 401 (FR-007, FR-008)."""
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return uuid.UUID(payload["sub"])
    except jwt.PyJWTError, KeyError, ValueError:
        return None
