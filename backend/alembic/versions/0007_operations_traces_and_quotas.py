"""0007_operations_traces_and_quotas

Revision ID: 0007_operations_traces_and_quotas
Revises: 0006_workflow_executions
Create Date: 2026-11-13 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "0007_operations_traces_and_quotas"
down_revision: Union[str, None] = "0006_workflow_executions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("request_traces"):
        op.create_table(
            "request_traces",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("request_id", sa.String(64), nullable=False),
            sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("endpoint", sa.String(120), nullable=False, server_default="/api/v1/chat/query"),
            sa.Column("total_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("slowest_stage", sa.String(50), nullable=False, server_default="unknown"),
            sa.Column("slowest_stage_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("is_empty_result", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_abstained", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("error_type", sa.String(100), nullable=True),
            sa.Column("spans_data", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_request_traces_request_id", "request_traces", ["request_id"])
        op.create_index("ix_request_traces_user_id", "request_traces", ["user_id"])
        op.create_index("ix_request_traces_endpoint", "request_traces", ["endpoint"])
        op.create_index("ix_request_traces_slowest_stage", "request_traces", ["slowest_stage"])
        op.create_index("ix_request_traces_is_empty_result", "request_traces", ["is_empty_result"])
        op.create_index("ix_request_traces_is_abstained", "request_traces", ["is_abstained"])
        op.create_index("ix_request_traces_created_at", "request_traces", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("request_traces"):
        op.drop_table("request_traces")
