"""0006_workflow_executions

Revision ID: 0006_workflow_executions
Revises: 0005_governance_audit_hash_chain
Create Date: 2026-11-04 18:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "0006_workflow_executions"
down_revision: Union[str, None] = "0005_governance_audit_hash_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("workflow_executions"):
        op.create_table(
            "workflow_executions",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workflow_type", sa.String(50), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("input_params", sa.Text(), nullable=True),
            sa.Column("result_data", sa.Text(), nullable=True),
            sa.Column("steps", sa.Text(), nullable=True),
            sa.Column("authorized_document_ids", sa.Text(), nullable=True),
            sa.Column("total_duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_workflow_executions_user_id", "workflow_executions", ["user_id"])
        op.create_index("ix_workflow_executions_workflow_type", "workflow_executions", ["workflow_type"])
        op.create_index("ix_workflow_executions_status", "workflow_executions", ["status"])
        op.create_index("ix_workflow_executions_created_at", "workflow_executions", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("workflow_executions"):
        op.drop_table("workflow_executions")
