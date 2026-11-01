"""Centralized authorization policies enforcing default-deny RBAC and document grants."""

import uuid
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.models.user import User

logger = get_logger(__name__)


def can_manage_users(user: User) -> bool:
    """Verify if user is authorized to manage user accounts and system configuration."""
    if not user.is_active:
        return False
    return user.is_admin


def can_upload_document(user: User, department_id: uuid.UUID) -> bool:
    """Verify if user can upload documents to the specified department."""
    if not user.is_active:
        return False

    # Admins can upload to any department
    if user.is_admin:
        return True

    # Department managers can only upload to their assigned department
    if user.is_manager:
        return user.department_id is not None and user.department_id == department_id

    # Regular employees cannot upload in v1 (default-deny)
    return False


async def can_read_document(
    user: User,
    document: Document,
    db: AsyncSession,
    require_active: bool = False,
) -> bool:
    """Verify if user can read the given document. Enforces default-deny and lifecycle states."""
    if not user.is_active:
        return False

    if document.status == "deleted" or document.lifecycle_state == "deleted":
        return False

    if require_active and document.lifecycle_state != "active":
        return False

    # 1. Global Admin privilege
    if user.is_admin:
        return True

    # 2. Document Owner
    if document.owner_id == user.id:
        return True

    # 3. Check explicit document grants in PostgreSQL
    user_role_ids = [r.id for r in user.roles]
    grant_stmt = select(DocumentGrant).where(
        DocumentGrant.document_id == document.id,
        or_(
            DocumentGrant.grantee_user_id == user.id,
            DocumentGrant.grantee_role_id.in_(user_role_ids) if user_role_ids else False,
        ),
    )
    result = await db.execute(grant_stmt)
    matching_grant = result.scalars().first()
    if matching_grant is not None:
        return True

    # 4. Department-level policy
    if user.department_id is not None and user.department_id == document.department_id:
        # Department managers can read all documents in their department
        if user.is_manager:
            return True

        # Standard employees can only read non-confidential department documents
        if not document.is_confidential:
            return True

    # Fail closed: default deny
    return False


def can_manage_grants(user: User, document: Document) -> bool:
    """Verify if user can grant or revoke access to the document."""
    if not user.is_active:
        return False

    if user.is_admin:
        return True

    if document.owner_id == user.id:
        return True

    if user.is_manager and user.department_id == document.department_id:
        return True

    return False


async def get_authorized_document_ids(
    user: User,
    db: AsyncSession,
    eligible_lifecycle_states: tuple[str, ...] = ("active",),
) -> list[uuid.UUID]:
    """Compute the full set of document IDs authorized for the user.
    
    Used for pre-retrieval vector search filtering from trusted PostgreSQL records.
    Filters strictly to active lifecycle versions by default.
    """
    if not user.is_active:
        return []

    lifecycle_filter = Document.lifecycle_state.in_(eligible_lifecycle_states)

    if user.is_admin:
        stmt = select(Document.id).where(Document.status != "deleted", lifecycle_filter)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # Collect IDs through multiple authorized channels
    authorized_ids: set[uuid.UUID] = set()

    # 1. Owned documents
    owned_stmt = select(Document.id).where(
        Document.owner_id == user.id,
        Document.status != "deleted",
        lifecycle_filter,
    )
    owned_res = await db.execute(owned_stmt)
    authorized_ids.update(owned_res.scalars().all())

    # 2. Department-level documents
    if user.department_id is not None:
        if user.is_manager:
            dept_stmt = select(Document.id).where(
                Document.department_id == user.department_id,
                Document.status != "deleted",
                lifecycle_filter,
            )
        else:
            dept_stmt = select(Document.id).where(
                Document.department_id == user.department_id,
                Document.is_confidential.is_(False),
                Document.status != "deleted",
                lifecycle_filter,
            )
        dept_res = await db.execute(dept_stmt)
        authorized_ids.update(dept_res.scalars().all())

    # 3. Explicit grants
    user_role_ids = [r.id for r in user.roles]
    grant_stmt = (
        select(DocumentGrant.document_id)
        .join(Document, Document.id == DocumentGrant.document_id)
        .where(
            Document.status != "deleted",
            lifecycle_filter,
            or_(
                DocumentGrant.grantee_user_id == user.id,
                DocumentGrant.grantee_role_id.in_(user_role_ids) if user_role_ids else False,
            ),
        )
    )
    grant_res = await db.execute(grant_stmt)
    authorized_ids.update(grant_res.scalars().all())

    return list(authorized_ids)
