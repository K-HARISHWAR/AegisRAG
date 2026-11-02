"""Thread, ThreadMessage, and ThreadBookmark models for conversation workspaces and controlled memory."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, utc_now

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class Thread(Base):
    """Named conversation workspace isolated per authenticated user."""

    __tablename__ = "threads"

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
    title: Mapped[str] = mapped_column(
        String(255),
        default="New Conversation",
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    messages: Mapped[List["ThreadMessage"]] = relationship(
        "ThreadMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ThreadMessage.created_at.asc()",
        lazy="selectin",
    )
    bookmarks: Mapped[List["ThreadBookmark"]] = relationship(
        "ThreadBookmark",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ThreadBookmark.created_at.desc()",
        lazy="selectin",
    )


class ThreadMessage(Base):
    """Individual interaction turn within a conversation thread."""

    __tablename__ = "thread_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender: Mapped[str] = mapped_column(
        String(20),  # "user" or "assistant"
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    citations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    abstained: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    evidence_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    abstention_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    query_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    thread: Mapped["Thread"] = relationship(
        "Thread",
        back_populates="messages",
    )


class ThreadBookmark(Base):
    """User-saved grounded citation snippet linked to active document permission."""

    __tablename__ = "thread_bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    thread: Mapped["Thread"] = relationship(
        "Thread",
        back_populates="bookmarks",
    )
    document: Mapped["Document"] = relationship(
        "Document",
        lazy="selectin",
    )
