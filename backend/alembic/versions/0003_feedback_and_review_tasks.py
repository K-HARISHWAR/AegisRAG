"""0003_feedback_and_review_tasks

Revision ID: 0003_feedback_and_review_tasks
Revises: 0002_lifecycle_versioning
Create Date: 2026-11-02 18:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "0003_feedback_and_review_tasks"
down_revision: Union[str, None] = "0002_lifecycle_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("feedbacks"):
        op.create_table(
            "feedbacks",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("query_id", GUID(), nullable=True),
            sa.Column("request_id", sa.String(100), nullable=True),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=False),
            sa.Column("rating", sa.String(20), nullable=False),
            sa.Column("reason_tags", sa.JSON(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("model_version", sa.String(50), nullable=True),
            sa.Column("prompt_version", sa.String(50), nullable=True),
            sa.Column("retrieved_document_versions", sa.JSON(), nullable=False),
            sa.Column("evidence_level", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("review_status", sa.String(30), nullable=False, server_default="not_required"),
            sa.Column("reviewer_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewer_notes", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"])
        op.create_index("ix_feedbacks_query_id", "feedbacks", ["query_id"])
        op.create_index("ix_feedbacks_request_id", "feedbacks", ["request_id"])
        op.create_index("ix_feedbacks_rating", "feedbacks", ["rating"])
        op.create_index("ix_feedbacks_created_at", "feedbacks", ["created_at"])
        op.create_index("ix_feedbacks_review_status", "feedbacks", ["review_status"])
        op.create_index("ix_feedbacks_reviewer_user_id", "feedbacks", ["reviewer_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("feedbacks"):
        op.drop_table("feedbacks")
