"""0004_conversation_threads_and_memory

Revision ID: 0004_conversation_threads_and_memory
Revises: 0003_feedback_and_review_tasks
Create Date: 2026-11-02 18:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "0004_conversation_threads_and_memory"
down_revision: Union[str, None] = "0003_feedback_and_review_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("threads"):
        op.create_table(
            "threads",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(255), nullable=False, server_default="New Conversation"),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_threads_user_id", "threads", ["user_id"])
        op.create_index("ix_threads_is_archived", "threads", ["is_archived"])
        op.create_index("ix_threads_created_at", "threads", ["created_at"])

    if not insp.has_table("thread_messages"):
        op.create_table(
            "thread_messages",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("thread_id", GUID(), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender", sa.String(20), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("citations", sa.JSON(), nullable=False),
            sa.Column("abstained", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("evidence_level", sa.String(20), nullable=True),
            sa.Column("abstention_reason", sa.String(100), nullable=True),
            sa.Column("query_id", GUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_thread_messages_thread_id", "thread_messages", ["thread_id"])
        op.create_index("ix_thread_messages_created_at", "thread_messages", ["created_at"])

    if not insp.has_table("thread_bookmarks"):
        op.create_table(
            "thread_bookmarks",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("thread_id", GUID(), sa.ForeignKey("threads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("location", sa.String(100), nullable=False),
            sa.Column("snippet", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_thread_bookmarks_thread_id", "thread_bookmarks", ["thread_id"])
        op.create_index("ix_thread_bookmarks_user_id", "thread_bookmarks", ["user_id"])
        op.create_index("ix_thread_bookmarks_document_id", "thread_bookmarks", ["document_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("thread_bookmarks"):
        op.drop_table("thread_bookmarks")
    if insp.has_table("thread_messages"):
        op.drop_table("thread_messages")
    if insp.has_table("threads"):
        op.drop_table("threads")
