"""0002_document_lifecycle_and_versioning

Revision ID: 0002_lifecycle_versioning
Revises: 0001_initial_rbac_schema
Create Date: 2026-11-01 09:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "0002_lifecycle_versioning"
down_revision: Union[str, None] = "0001_initial_rbac_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_cols = [c["name"] for c in insp.get_columns("documents")]
    indexes = [i["name"] for i in insp.get_indexes("documents")]
    is_sqlite = bind.dialect.name == "sqlite"

    with op.batch_alter_table("documents") as batch_op:
        if "logical_document_id" not in existing_cols:
            batch_op.add_column(sa.Column("logical_document_id", GUID(), nullable=True))
        if "supersedes_id" not in existing_cols:
            batch_op.add_column(sa.Column("supersedes_id", GUID(), nullable=True))
        if "lifecycle_state" not in existing_cols:
            batch_op.add_column(sa.Column("lifecycle_state", sa.String(30), nullable=False, server_default="active"))
        if "effective_date" not in existing_cols:
            batch_op.add_column(sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True))

        if "ix_documents_logical_document_id" not in indexes:
            batch_op.create_index("ix_documents_logical_document_id", ["logical_document_id"])
        if "ix_documents_supersedes_id" not in indexes:
            batch_op.create_index("ix_documents_supersedes_id", ["supersedes_id"])
        if "ix_documents_lifecycle_state" not in indexes:
            batch_op.create_index("ix_documents_lifecycle_state", ["lifecycle_state"])

    # If Postgres, add foreign key constraint
    if not is_sqlite:
        op.create_foreign_key(
            "fk_documents_supersedes_id",
            "documents",
            "documents",
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Safe backfill for existing records
    op.execute("UPDATE documents SET logical_document_id = id WHERE logical_document_id IS NULL")
    op.execute("UPDATE documents SET lifecycle_state = 'deleted' WHERE status = 'deleted'")


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not is_sqlite:
        op.drop_constraint("fk_documents_supersedes_id", "documents", type_="foreignkey")

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_index("ix_documents_lifecycle_state")
        batch_op.drop_index("ix_documents_supersedes_id")
        batch_op.drop_index("ix_documents_logical_document_id")
        batch_op.drop_column("effective_date")
        batch_op.drop_column("lifecycle_state")
        batch_op.drop_column("supersedes_id")
        batch_op.drop_column("logical_document_id")
