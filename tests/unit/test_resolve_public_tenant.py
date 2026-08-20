"""T011 — unit test: `resolve_public_tenant` (feature
011-conversations-analytics, research.md §4 "Testing implication"). Every
fail-closed rule proven directly against the function, without driving a
full HTTP request: exists+active resolves; missing returns None; inactive
returns None; a second, differently-slugged tenant is never selected as a
fallback; no Tenant row is ever created as a side effect.
"""

import uuid

import pytest
from sqlalchemy import func, select

from shiruno.application.resolve_public_tenant import resolve_public_tenant
from shiruno.persistence.models import Tenant, TenantStatus


def _tenant_count(db_session):
    return db_session.execute(select(func.count()).select_from(Tenant)).scalar_one()


def test_resolves_existing_active_tenant(db_session) -> None:
    slug = f"albertos-{uuid.uuid4()}"
    tenant = Tenant(name="Albertos", slug=slug, status=TenantStatus.active)
    db_session.add(tenant)
    db_session.flush()

    resolved = resolve_public_tenant(db_session, slug=slug)

    assert resolved is not None
    assert resolved.id == tenant.id


def test_missing_tenant_returns_none(db_session) -> None:
    resolved = resolve_public_tenant(db_session, slug=f"nonexistent-{uuid.uuid4()}")

    assert resolved is None


def test_inactive_tenant_returns_none(db_session) -> None:
    slug = f"albertos-{uuid.uuid4()}"
    tenant = Tenant(name="Albertos", slug=slug, status=TenantStatus.inactive)
    db_session.add(tenant)
    db_session.flush()

    resolved = resolve_public_tenant(db_session, slug=slug)

    assert resolved is None


def test_never_falls_back_to_a_differently_slugged_tenant(db_session) -> None:
    configured_slug = f"albertos-{uuid.uuid4()}"
    other = Tenant(
        name="Some Other Tenant", slug=f"other-{uuid.uuid4()}", status=TenantStatus.active
    )
    db_session.add(other)
    db_session.flush()

    resolved = resolve_public_tenant(db_session, slug=configured_slug)

    assert resolved is None
    assert resolved != other


def test_does_not_create_a_tenant_as_a_side_effect(db_session) -> None:
    before = _tenant_count(db_session)

    resolve_public_tenant(db_session, slug=f"nonexistent-{uuid.uuid4()}")

    after = _tenant_count(db_session)
    assert after == before


@pytest.mark.parametrize("status", [TenantStatus.active, TenantStatus.inactive])
def test_does_not_create_a_tenant_even_when_a_real_one_exists(db_session, status) -> None:
    slug = f"albertos-{uuid.uuid4()}"
    db_session.add(Tenant(name="Albertos", slug=slug, status=status))
    db_session.flush()
    before = _tenant_count(db_session)

    resolve_public_tenant(db_session, slug=slug)

    after = _tenant_count(db_session)
    assert after == before
