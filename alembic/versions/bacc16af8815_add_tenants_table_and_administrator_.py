"""add tenants table and administrator tenant_id

Revision ID: bacc16af8815
Revises: 9e3393cc9c93
Create Date: 2026-08-19 21:47:56.730796

Introduces `Tenant` as a first-class security boundary (constitution
Principle II, amended 2026-08-19, v4.0.0; feature
009-admin-platform-foundation, data-model.md "Migration plan" §1).

Bootstraps exactly one tenant here — Albertos — rather than relying on an
operator to run a separate seed step first: this migration's own
`administrators.tenant_id` backfill needs a real tenant row to point at,
and Alembic's own revision tracking already guarantees this migration
runs at most once (research.md §6/§9), so this insert cannot duplicate on
a normal `alembic upgrade head`. Any *additional* tenant after Albertos is
provisioned through `shiruno.cli create-tenant`, not a migration.

Same explicit "add nullable -> backfill -> verify -> enforce NOT NULL"
four-step shape as `48197330146f_add_usage_records_provider_name.py`, so
the column is never briefly `NOT NULL` with ambiguous data for any
existing row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bacc16af8815'
down_revision: Union[str, None] = '9e3393cc9c93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: create `tenants` and bootstrap the Albertos row. The enum
    # type is created implicitly by `create_table` (matches
    # f915a8a88045_initial_schema.py's inline-Enum-in-Column pattern) — it
    # must NOT also be created explicitly beforehand, or the second
    # `CREATE TYPE` fails with `DuplicateObject`.
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("status", sa.Enum("active", "inactive", name="tenant_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    albertos_tenant_id = connection.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, status) "
            "VALUES (gen_random_uuid(), 'Albertos', 'albertos', 'active') "
            "RETURNING id"
        )
    ).scalar_one()

    # Step 2: add `administrators.tenant_id` nullable — no existing row is
    # touched or required to have a value yet.
    op.add_column("administrators", sa.Column("tenant_id", sa.Uuid(), nullable=True))

    # Step 3: backfill every existing administrator to Albertos, the only
    # tenant that can possibly exist before this feature.
    connection.execute(
        sa.text("UPDATE administrators SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": albertos_tenant_id},
    )

    # Step 4: verify the backfill was exhaustive; abort rather than
    # silently proceed if it wasn't.
    remaining = connection.execute(
        sa.text("SELECT count(*) FROM administrators WHERE tenant_id IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"administrators.tenant_id backfill left {remaining} row(s) unset — aborting "
            "migration rather than adding a NOT NULL constraint the data doesn't satisfy."
        )

    # Step 5: only now require it, and add the FK.
    op.alter_column("administrators", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_administrators_tenant_id_tenants",
        "administrators",
        "tenants",
        ["tenant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_administrators_tenant_id_tenants", "administrators", type_="foreignkey")
    op.drop_column("administrators", "tenant_id")
    op.drop_table("tenants")
    sa.Enum(name="tenant_status").drop(op.get_bind(), checkfirst=True)
