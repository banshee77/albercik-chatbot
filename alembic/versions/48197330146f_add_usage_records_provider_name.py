"""add usage_records provider_name

Revision ID: 48197330146f
Revises: f915a8a88045
Create Date: 2026-08-18 14:17:21.664822

Adds `usage_records.provider_name` (feature 002-add-ollama-provider,
data-model.md Migration) in four explicit, ordered steps so the column is
never briefly `NOT NULL` with ambiguous or guessed data for any existing
row on a table that may already hold production usage history:

1. Add the column nullable — no existing row is touched or required to
   have a value yet.
2. Backfill every existing row deterministically, keyed EXCLUSIVELY on the
   existing `provider_kind` column — never on `provider_model` / model-name
   string matching, even though `provider_model` would today happen to
   disambiguate correctly too. `provider_kind` is the only signal this
   feature treats as structurally guaranteed correct.
3. Assert no row was missed (belt-and-suspenders: step 2 is already
   exhaustive by construction, since `provider_kind` is itself `NOT NULL`
   with exactly two possible values) — abort loudly rather than proceed
   silently if this is ever not the case.
4. Only now make the column `NOT NULL`. No `SERVER DEFAULT` is set at any
   point: every future insert specifies `provider_name` explicitly, the
   same way it already explicitly specifies `provider_kind` today.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48197330146f'
down_revision: Union[str, None] = 'f915a8a88045'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVIDER_NAME_ENUM = sa.Enum(
    "anthropic", "ollama", "local_sentence_transformer", name="provider_name"
)


def upgrade() -> None:
    # Step 1: add nullable.
    _PROVIDER_NAME_ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "usage_records",
        sa.Column("provider_name", _PROVIDER_NAME_ENUM, nullable=True),
    )

    # Step 2: deterministic backfill, keyed only on provider_kind — never
    # on provider_model.
    op.execute(
        "UPDATE usage_records SET provider_name = 'anthropic' "
        "WHERE provider_kind = 'llm'"
    )
    op.execute(
        "UPDATE usage_records SET provider_name = 'local_sentence_transformer' "
        "WHERE provider_kind = 'embedding'"
    )

    # Step 3: verify the backfill was exhaustive; abort rather than
    # silently proceed if it wasn't.
    connection = op.get_bind()
    remaining = connection.execute(
        sa.text("SELECT count(*) FROM usage_records WHERE provider_name IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"provider_name backfill left {remaining} row(s) unset — aborting "
            "migration rather than adding a NOT NULL constraint the data "
            "doesn't actually satisfy."
        )

    # Step 4: only now require it.
    op.alter_column("usage_records", "provider_name", nullable=False)


def downgrade() -> None:
    op.drop_column("usage_records", "provider_name")
    _PROVIDER_NAME_ENUM.drop(op.get_bind(), checkfirst=True)
