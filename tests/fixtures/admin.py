"""Shared test helper: seed an Administrator directly (no HTTP endpoint
creates one — FR-004a) and issue a valid JWT for it directly via
infra/security.py, bypassing the login endpoint for speed. Used by every
Phase 4 contract/integration test that needs an authenticated admin.
"""

import uuid

from sqlalchemy.orm import Session

from albercik_chatbot.config import get_settings
from albercik_chatbot.infra.security import hash_password, issue_access_token
from albercik_chatbot.persistence.models import Administrator


def seed_admin_and_token(db_session: Session, *, username: str | None = None) -> str:
    admin = Administrator(
        username=username or f"admin-{uuid.uuid4()}", password_hash=hash_password("x")
    )
    db_session.add(admin)
    db_session.flush()

    settings = get_settings()
    issued = issue_access_token(
        administrator_id=admin.id,
        secret=settings.AUTH_JWT_SECRET,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        expire_minutes=settings.AUTH_JWT_EXPIRE_MINUTES,
    )
    return issued.access_token
