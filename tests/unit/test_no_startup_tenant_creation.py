"""Feature 009-admin-platform-foundation (FR-006): `create_app()` must
never create a `Tenant` row as a side effect of application startup — the
Albertos tenant is bootstrapped only by its Alembic migration
(alembic/versions/bacc16af8815_...), and any further tenant only by the
`create-tenant` CLI command (research.md §6).
"""

from sqlalchemy import func, select

from shiruno.main import create_app
from shiruno.persistence.models import Tenant


def test_create_app_does_not_create_a_tenant(
    db_session, fake_llm_provider, fake_embedding_provider
) -> None:
    before = db_session.execute(select(func.count()).select_from(Tenant)).scalar_one()

    create_app(llm_provider=fake_llm_provider, embedding_provider=fake_embedding_provider)
    create_app(llm_provider=fake_llm_provider, embedding_provider=fake_embedding_provider)

    after = db_session.execute(select(func.count()).select_from(Tenant)).scalar_one()
    assert after == before
