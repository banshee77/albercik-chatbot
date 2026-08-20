"""Fail-closed resolution of the public reference tenant (feature
011-conversations-analytics, research.md §4). The single place this
resolution ever happens — a plain, non-mutating read with an exhaustively
fail-closed contract:

- exists check: the exact configured slug, nothing else;
- active check: an inactive tenant is treated identically to a missing one
  (mirrors `api/deps.py::get_current_tenant`'s existing admin-auth pattern);
- no fallback: no `.first()`, no "pick any tenant" — an unmatched or
  inactive slug returns `None`, full stop;
- no auto-create: this function only ever reads;
- no client influence: `slug` is always server configuration
  (`config.Settings.PUBLIC_CHAT_TENANT_SLUG`), never derived from request
  content.

Never raises for a missing/inactive tenant — `None` is a clean, explicit
"not available" signal for the caller (`record_conversation.py`) to act on.
This is a recording-subsystem concern only; it never gates the public chat
response itself (research.md §4).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from shiruno.persistence.models import Tenant, TenantStatus


def resolve_public_tenant(session: Session, *, slug: str) -> Tenant | None:
    tenant = session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
    if tenant is None or tenant.status != TenantStatus.active:
        return None
    return tenant
