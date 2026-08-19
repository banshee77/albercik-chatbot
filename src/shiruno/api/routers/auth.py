"""POST /api/v1/auth/login — Administrator sign-in (T047; FR-008,
research.md §1). Public route — no auth dependency, obviously, since this
is how one is obtained. Wrong username, wrong password, and an inactive
account all raise the exact same generic failure — never revealing which
case applied (FR-008). A fixed dummy hash is checked even when the
username doesn't exist, so a failed login for an unknown username takes
roughly the same bcrypt-bound time as one for a known username with a
wrong password — a cheap defense against username enumeration via
response-timing.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.api.errors import UnauthorizedError
from shiruno.api.schemas import LoginRequest, LoginResponse
from shiruno.config import get_settings
from shiruno.infra.audit import log_audit_event
from shiruno.infra.security import hash_password, issue_access_token, verify_password
from shiruno.persistence.database import get_session
from shiruno.persistence.models import Administrator

router = APIRouter(prefix="/api/v1", tags=["auth"])

_GENERIC_FAILURE = "Invalid username or password."
# Computed once at import time; never a real account's hash.
_DUMMY_PASSWORD_HASH = hash_password("no-such-administrator-timing-defense")


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    settings = get_settings()
    administrator = session.execute(
        select(Administrator).where(Administrator.username == payload.username)
    ).scalar_one_or_none()

    password_hash = administrator.password_hash if administrator else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, password_hash)

    if administrator is None or not administrator.is_active or not password_ok:
        log_audit_event("login_failure", outcome="failure", username=payload.username)
        raise UnauthorizedError(_GENERIC_FAILURE)

    issued = issue_access_token(
        administrator_id=administrator.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=settings.AUTH_JWT_EXPIRE_MINUTES,
    )
    log_audit_event(
        "login_success",
        outcome="success",
        administrator_id=administrator.id,
        username=administrator.username,
    )
    return LoginResponse(
        access_token=issued.access_token, token_type="bearer", expires_in=issued.expires_in
    )
