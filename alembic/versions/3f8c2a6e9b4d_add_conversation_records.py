"""add conversation_records

Revision ID: 3f8c2a6e9b4d
Revises: 7a4d6c1e8b2f
Create Date: 2026-08-20 00:00:02.000000

Adds the `conversation_records` table (feature 011-conversations-analytics,
data-model.md "Migration plan"). Purely additive — no existing table is
touched, and no backfill is needed since conversation recording did not
exist before this feature, so the table has no historical rows by
construction.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3f8c2a6e9b4d'
down_revision: Union[str, None] = '7a4d6c1e8b2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONVERSATION_OUTCOME_VALUES = (
    "grounded",
    "insufficient_information",
    "out_of_scope",
    "unavailable",
    "small_talk",
)
_FAILURE_CATEGORY_VALUES = (
    "provider_error",
    "budget_exceeded",
    "kill_switch",
    "concurrency_limit",
)


def upgrade() -> None:
    # create_type=True (the default) — op.create_table() below creates
    # these as part of the table DDL; no separate standalone .create()
    # call, which would otherwise attempt to create each type twice.
    conversation_outcome = postgresql.ENUM(
        *_CONVERSATION_OUTCOME_VALUES, name="conversation_outcome"
    )
    conversation_failure_category = postgresql.ENUM(
        *_FAILURE_CATEGORY_VALUES, name="conversation_failure_category"
    )

    op.create_table(
        "conversation_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("outcome", conversation_outcome, nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("safe_failure_category", conversation_failure_category, nullable=True),
        # provider_name reuses the existing provider_name enum type
        # (created by the initial-schema migration for usage_records) —
        # no new enum type for this column.
        sa.Column(
            "provider_name",
            postgresql.ENUM(
                "anthropic",
                "ollama",
                "local_sentence_transformer",
                name="provider_name",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("provider_model", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("request_id", name="uq_conversation_records_request_id"),
    )
    op.create_index(
        "ix_conversation_records_tenant_id_created_at",
        "conversation_records",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_conversation_records_tenant_id_outcome_created_at",
        "conversation_records",
        ["tenant_id", "outcome", "created_at"],
    )
    op.create_index(
        "ix_conversation_records_tenant_id_normalized_question",
        "conversation_records",
        ["tenant_id", "normalized_question"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_records_tenant_id_normalized_question", table_name="conversation_records"
    )
    op.drop_index(
        "ix_conversation_records_tenant_id_outcome_created_at", table_name="conversation_records"
    )
    op.drop_index("ix_conversation_records_tenant_id_created_at", table_name="conversation_records")
    op.drop_table("conversation_records")

    postgresql.ENUM(name="conversation_failure_category").drop(op.get_bind())
    postgresql.ENUM(name="conversation_outcome").drop(op.get_bind())
