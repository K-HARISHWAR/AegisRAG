"""Department ORM model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, utc_now

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document


class Department(Base):
    """Department model representing organizational units (e.g. Engineering, HR)."""

    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="department",
        lazy="selectin",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="department",
        lazy="selectin",
    )
