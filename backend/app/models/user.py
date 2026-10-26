"""User ORM model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, utc_now
from app.models.role import user_roles

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.role import Role
    from app.models.document import Document
    from app.models.grant import DocumentGrant
    from app.models.audit import AuditEvent


class User(Base):
    """User account entity with department assignment and RBAC roles."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    department: Mapped["Department | None"] = relationship(
        "Department",
        back_populates="users",
        lazy="selectin",
    )
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )
    owned_documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="owner",
        lazy="selectin",
    )
    received_grants: Mapped[List["DocumentGrant"]] = relationship(
        "DocumentGrant",
        foreign_keys="[DocumentGrant.grantee_user_id]",
        back_populates="grantee_user",
        lazy="selectin",
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="actor",
        lazy="selectin",
    )

    @property
    def role_names(self) -> set[str]:
        """Return the set of role names assigned to the user."""
        return {r.name for r in self.roles}

    @property
    def is_admin(self) -> bool:
        """Return whether user has admin privileges."""
        return self.is_superuser or "admin" in self.role_names

    @property
    def is_manager(self) -> bool:
        """Return whether user has department manager role."""
        return "department_manager" in self.role_names or self.is_admin
