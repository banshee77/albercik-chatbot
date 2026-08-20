"""add knowledge_document replaces_document_id

Revision ID: 7a4d6c1e8b2f
Revises: 1c2b7e5a9f3d
Create Date: 2026-08-20 00:00:01.000000

Adds the nullable self-referential FK that links a replacement document
back to its predecessor (feature 010-knowledge-base-admin, data-model.md
"Migration plan" §2). NULL for every pre-existing row — none were
created via replace.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a4d6c1e8b2f'
down_revision: Union[str, None] = '1c2b7e5a9f3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents", sa.Column("replaces_document_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_knowledge_documents_replaces_document_id_knowledge_documents",
        "knowledge_documents",
        "knowledge_documents",
        ["replaces_document_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_knowledge_documents_replaces_document_id_knowledge_documents",
        "knowledge_documents",
        type_="foreignkey",
    )
    op.drop_column("knowledge_documents", "replaces_document_id")
