"""Shared test helper: seed an Administrator directly (no HTTP endpoint
creates one — FR-004a) and issue a valid JWT for it directly via
infra/security.py, bypassing the login endpoint for speed. Used by every
Phase 4 contract/integration test that needs an authenticated admin.

`tenant_id` is a required parameter (feature 009-admin-platform-foundation)
— every `Administrator` row must belong to a tenant, so callers pass
`default_tenant.id` (tests/conftest.py) or a tenant they seeded themselves
via `seed_tenant` below, e.g. to test cross-tenant isolation with two
distinct tenants.
"""

import uuid

from sqlalchemy.orm import Session

from shiruno.config import get_settings
from shiruno.infra.security import hash_password, issue_access_token
from shiruno.persistence.models import Administrator, Tenant


def seed_tenant(db_session: Session, *, name: str | None = None, slug: str | None = None) -> Tenant:
    unique = uuid.uuid4()
    tenant = Tenant(name=name or f"Tenant {unique}", slug=slug or f"tenant-{unique}")
    db_session.add(tenant)
    db_session.flush()
    return tenant


def seed_admin_and_token(
    db_session: Session, *, tenant_id: uuid.UUID, username: str | None = None
) -> str:
    admin = Administrator(
        username=username or f"admin-{uuid.uuid4()}",
        password_hash=hash_password("x"),
        tenant_id=tenant_id,
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
