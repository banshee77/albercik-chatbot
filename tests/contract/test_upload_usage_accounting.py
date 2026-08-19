"""T065 (upload half) — a successful document upload records one
`embedding`-kind `UsageRecord` row for its batched passage-embedding call
(operational visibility only — Design Constraint 3: this must never be
counted toward, or reduce, the LLM budget computed by infra/budget.py,
which only ever looks at `provider_kind == 'llm'` rows).
"""

import pytest
from sqlalchemy import select

from shiruno.persistence.models import ProviderKind, UsageRecord
from tests.fixtures.admin import seed_admin_and_token


@pytest.mark.asyncio
async def test_successful_upload_records_one_embedding_usage_row(
    db_async_client, db_session, default_tenant
) -> None:
    token = seed_admin_and_token(db_session, tenant_id=default_tenant.id)

    response = await db_async_client.post(
        "/api/v1/documents",
        files={"file": ("godziny.txt", b"Albertos jest czynny od 9 do 17.", "text/plain")},
        headers={"authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    rows = (
        db_session.execute(
            select(UsageRecord).where(UsageRecord.provider_kind == ProviderKind.embedding)
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1
    assert rows[0].success is True
    assert rows[0].latency_ms >= 0
    assert rows[0].provider_model
