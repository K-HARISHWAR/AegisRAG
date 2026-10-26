"""DocumentGrant ORM model for explicit access permissions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, utc_now

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User
    from app.models.role import Role


class DocumentGrant(Base):
    """Explicit access grant conferring permission on a document to a user or role."""

    __tablename__ = "document_grants"
    __table_args__ = (
        CheckConstraint(
            "grantee_user_id IS NOT NULL OR grantee_role_id IS NOT NULL",
            name="check_grantee_specified",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grantee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    grantee_role_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    permission: Mapped[str] = mapped_column(
        String(30),
        default="read",
        nullable=False,
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="grants",
        lazy="selectin",
    )
    grantee_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[grantee_user_id],
        back_populates="received_grants",
        lazy="selectin",
    )
    grantee_role: Mapped["Role | None"] = relationship(
        "Role",
        foreign_keys=[grantee_role_id],
        lazy="selectin",
    )
    granted_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[granted_by_user_id],
        lazy="selectin",
    )
