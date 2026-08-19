"""add knowledge_document tenant_id

Revision ID: e3406f01e5ec
Revises: bacc16af8815
Create Date: 2026-08-19 21:48:25.696049

Tenant-scopes the existing admin document management endpoints (feature
009-admin-platform-foundation, research.md §3, data-model.md "Migration
plan" §2): every pre-existing `knowledge_documents` row is Albertos's,
since Albertos is the only customer with real data before this feature.
Same explicit four-step shape as the previous migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3406f01e5ec'
down_revision: Union[str, None] = 'bacc16af8815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: add nullable.
    op.add_column("knowledge_documents", sa.Column("tenant_id", sa.Uuid(), nullable=True))

    # Step 2: backfill every existing document to Albertos, looked up by
    # its fixed slug rather than assumed/guessed.
    connection.execute(
        sa.text(
            "UPDATE knowledge_documents SET tenant_id = "
            "(SELECT id FROM tenants WHERE slug = 'albertos') "
            "WHERE tenant_id IS NULL"
        )
    )

    # Step 3: verify the backfill was exhaustive.
    remaining = connection.execute(
        sa.text("SELECT count(*) FROM knowledge_documents WHERE tenant_id IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"knowledge_documents.tenant_id backfill left {remaining} row(s) unset — aborting "
            "migration rather than adding a NOT NULL constraint the data doesn't satisfy."
        )

    # Step 4: only now require it, and add the FK.
    op.alter_column("knowledge_documents", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_knowledge_documents_tenant_id_tenants",
        "knowledge_documents",
        "tenants",
        ["tenant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_knowledge_documents_tenant_id_tenants", "knowledge_documents", type_="foreignkey"
    )
    op.drop_column("knowledge_documents", "tenant_id")
