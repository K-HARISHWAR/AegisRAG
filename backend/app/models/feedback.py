"""Feedback ORM model for capturing user ratings, failure reason tags, and review tasks."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, utc_now

if TYPE_CHECKING:
    from app.models.user import User


class Feedback(Base):
    """Stores user response feedback, diagnostic metadata, and human review tasks."""

    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    answer_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    rating: Mapped[str] = mapped_column(
        String(20),  # "positive" or "negative"
        nullable=False,
        index=True,
    )
    reason_tags: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    model_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    retrieved_document_versions: Mapped[Dict[str, int]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    evidence_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Human Review Task fields (for negative feedback triage)
    review_status: Mapped[str] = mapped_column(
        String(30),
        default="not_required",  # "pending_review", "in_review", "reviewed", "resolved", "dismissed", "not_required"
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewer_user_id],
        lazy="selectin",
    )

