"""add knowledge_document lifecycle metadata

Revision ID: 1c2b7e5a9f3d
Revises: e3406f01e5ec
Create Date: 2026-08-20 00:00:00.000000

Adds `updated_at`, `indexed_at`, and `safe_error_message` to
`knowledge_documents` (feature 010-knowledge-base-admin, data-model.md
"Migration plan" §1). Same explicit deterministic-backfill shape as the
previous tenant migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c2b7e5a9f3d'
down_revision: Union[str, None] = 'e3406f01e5ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # updated_at: add nullable, backfill from uploaded_at (the best
    # available proxy for pre-existing rows), assert exhaustive, set
    # NOT NULL with a server default for future rows.
    op.add_column(
        "knowledge_documents", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    connection.execute(
        sa.text("UPDATE knowledge_documents SET updated_at = uploaded_at WHERE updated_at IS NULL")
    )
    remaining = connection.execute(
        sa.text("SELECT count(*) FROM knowledge_documents WHERE updated_at IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"knowledge_documents.updated_at backfill left {remaining} row(s) unset — aborting "
            "migration rather than adding a NOT NULL constraint the data doesn't satisfy."
        )
    op.alter_column(
        "knowledge_documents",
        "updated_at",
        nullable=False,
        server_default=sa.text("now()"),
    )

    # indexed_at: nullable, backfilled only for rows already ready — no
    # exhaustiveness assertion needed, NULL is the permanent correct state
    # for any non-ready row.
    op.add_column(
        "knowledge_documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )
    connection.execute(
        sa.text(
            "UPDATE knowledge_documents SET indexed_at = uploaded_at "
            "WHERE status = 'ready' AND indexed_at IS NULL"
        )
    )

    # safe_error_message: nullable, no backfill — NULL is correct for
    # every pre-existing row (no failure to report).
    op.add_column("knowledge_documents", sa.Column("safe_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_documents", "safe_error_message")
    op.drop_column("knowledge_documents", "indexed_at")
    op.drop_column("knowledge_documents", "updated_at")
