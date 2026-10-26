"""User, Role, and Department Pydantic schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class RoleRead(BaseModel):
    """Role public representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class DepartmentRead(BaseModel):
    """Department public representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class UserRead(BaseModel):
    """User representation for authenticated profile and administrative queries."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    department_id: uuid.UUID | None = None
    department: DepartmentRead | None = None
    roles: list[RoleRead] = []
    is_active: bool
    is_superuser: bool
    created_at: datetime


class UserCreate(BaseModel):
    """Administrative user creation payload."""

    email: EmailStr
    password: str
    department_id: uuid.UUID | None = None
    role_names: list[str] = ["employee"]
