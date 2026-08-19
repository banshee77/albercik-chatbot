"""add usage_records provider_metrics

Revision ID: 9e3393cc9c93
Revises: 48197330146f
Create Date: 2026-08-18 23:09:53.126443

Adds `usage_records.provider_metrics` (feature
004-rag-answerability-and-ollama-performance, data-model.md "UsageRecord
(extended)") — purely additive, unlike the `provider_name` migration this
one follows: every existing row correctly has no telemetry data (it was
never captured before this feature), so `NULL` is the right value for
every historical row and no backfill is needed or performed. No
`NOT NULL` constraint is ever applied — Anthropic-backed rows and every
`embedding`-kind row are expected to stay `NULL` forever.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '9e3393cc9c93'
down_revision: Union[str, None] = '48197330146f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage_records",
        sa.Column("provider_metrics", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usage_records", "provider_metrics")
