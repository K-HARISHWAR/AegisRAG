"""Document and grant management routes enforcing server-side RBAC."""

import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentGrantCreate, DocumentGrantRead, DocumentRead
from app.services.audit import log_audit_event
from app.services.policy import (
    can_manage_grants,
    can_read_document,
    can_upload_document,
    get_authorized_document_ids,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get(
    "",
    response_model=List[DocumentRead],
    summary="List accessible documents",
    description="Returns all documents that the current user is authorized to view based on RBAC and explicit grants.",
)
async def list_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[DocumentRead]:
    """Retrieve all authorized documents for the current user."""
    auth_doc_ids = await get_authorized_document_ids(current_user, db)
    if not auth_doc_ids:
        return []

    stmt = (
        select(Document)
        .options(selectinload(Document.grants))
        .where(Document.id.in_(auth_doc_ids))
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [DocumentRead.model_validate(doc) for doc in docs]


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Get document metadata",
    description="Fetches document metadata if permitted by server authorization policies. Fail closed if unauthorized.",
)
async def get_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    """Fetch specific document metadata with strict default-deny enforcement."""
    ip_address = request.client.host if request.client else None

    stmt = (
        select(Document)
        .options(selectinload(Document.grants))
        .where(Document.id == document_id)
    )
    result = await db.execute(stmt)
    document = result.scalars().first()

    if document is None or document.status == "deleted":
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="read_document",
            outcome="deny",
            resource_id=str(document_id),
            resource_type="document",
            details="document_not_found",
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Server-verified authorization check
    is_allowed = await can_read_document(current_user, document, db)
    if not is_allowed:
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="read_document",
            outcome="deny",
            resource_id=str(document.id),
            resource_type="document",
            details={"department_id": str(document.department_id), "is_confidential": document.is_confidential},
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to requested document",
        )

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="read_document",
        outcome="allow",
        resource_id=str(document.id),
        resource_type="document",
        ip_address=ip_address,
    )

    return DocumentRead.model_validate(document)


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register document metadata",
    description="Registers a new document. User must be a department manager for the target department or an admin.",
)
async def create_document(
    payload: DocumentCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    """Register document record with server-enforced upload permissions."""
    ip_address = request.client.host if request.client else None

    if not can_upload_document(current_user, payload.department_id):
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_document",
            outcome="deny",
            resource_type="document",
            details={"department_id": str(payload.department_id)},
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload documents for this department",
        )

    storage_key = f"doc_{uuid.uuid4().hex}"
    doc = Document(
        title=payload.title,
        owner_id=current_user.id,
        department_id=payload.department_id,
        storage_key=storage_key,
        file_type=payload.file_type.lower(),
        file_size_bytes=payload.file_size_bytes,
        checksum_sha256=payload.checksum_sha256,
        is_confidential=payload.is_confidential,
        status="uploaded",
        version=1,
    )

    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="upload_document",
        outcome="allow",
        resource_id=str(doc.id),
        resource_type="document",
        details={"title": doc.title, "department_id": str(doc.department_id)},
        ip_address=ip_address,
    )

    return DocumentRead.model_validate(doc)


@router.post(
    "/{document_id}/grants",
    response_model=DocumentGrantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create document access grant",
    description="Grants explicit access to a document. User must own the document, manage the department, or be an admin.",
)
async def create_document_grant(
    document_id: uuid.UUID,
    payload: DocumentGrantCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentGrantRead:
    """Create an explicit access grant on a document."""
    ip_address = request.client.host if request.client else None

    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    document = result.scalars().first()

    if document is None or document.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not can_manage_grants(current_user, document):
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="create_grant",
            outcome="deny",
            resource_id=str(document.id),
            resource_type="grant",
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to manage access grants for this document",
        )

    grant = DocumentGrant(
        document_id=document.id,
        grantee_user_id=payload.grantee_user_id,
        grantee_role_id=payload.grantee_role_id,
        permission=payload.permission,
        granted_by_user_id=current_user.id,
    )

    db.add(grant)
    await db.commit()
    await db.refresh(grant)

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="create_grant",
        outcome="allow",
        resource_id=str(grant.id),
        resource_type="grant",
        details={
            "document_id": str(document.id),
            "grantee_user_id": str(payload.grantee_user_id) if payload.grantee_user_id else None,
            "grantee_role_id": str(payload.grantee_role_id) if payload.grantee_role_id else None,
        },
        ip_address=ip_address,
    )

    return DocumentGrantRead.model_validate(grant)
