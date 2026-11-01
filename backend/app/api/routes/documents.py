"""Document ingestion, extraction, and access management routes enforcing server-side RBAC."""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.models.user import User
from app.schemas.chunk import DocumentChunkRead
from app.schemas.document import (
    DocumentContentResponse,
    DocumentCreate,
    DocumentGrantCreate,
    DocumentGrantRead,
    DocumentHistoryResponse,
    DocumentPassageRead,
    DocumentRead,
    DocumentRevisionHistoryItem,
    DocumentUploadResponse,
)
from app.services.audit import log_audit_event
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.extraction import extract_document_text
from app.services.indexing import index_document
from app.services.policy import (
    can_manage_grants,
    can_read_document,
    can_upload_document,
    get_authorized_document_ids,
)
from app.services.storage import StorageProvider, get_storage_provider
from app.services.validation import FileValidationError, validate_file_upload
from app.services.vector_store import VectorStore, get_vector_store

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
    include_superseded: bool = False,
) -> List[DocumentRead]:
    """Retrieve all authorized documents for the current user."""
    eligible_states = ("active", "superseded", "archived") if include_superseded else ("active",)
    auth_doc_ids = await get_authorized_document_ids(
        current_user,
        db,
        eligible_lifecycle_states=eligible_states,
    )
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


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register document metadata",
    description="Registers a new document metadata record. User must be a manager for the department or an admin.",
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

    # Check for active duplicate checksum in the target department
    dup_stmt = select(Document).where(
        Document.department_id == payload.department_id,
        Document.checksum_sha256 == payload.checksum_sha256,
        Document.lifecycle_state == "active",
        Document.status != "deleted",
    )
    existing_dup = (await db.execute(dup_stmt)).scalars().first()
    if existing_dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate document detected: exact content already exists with ID {existing_dup.id}",
        )

    storage_key = f"doc_{uuid.uuid4().hex}"
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        logical_document_id=doc_id,
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
        lifecycle_state="active",
        effective_date=datetime.now(timezone.utc),
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
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest document",
    description="Upload a document file (PDF, DOCX, XLSX up to 20MB). Validates signatures and extracts text safely.",
)
async def upload_document(
    request: Request,
    department_id: Annotated[uuid.UUID, Form(description="Target department ID")],
    file: Annotated[UploadFile, File(description="Document binary file (PDF, DOCX, XLSX)")],
    is_confidential: Annotated[bool, Form(description="Whether document requires manager privileges")] = False,
    title: Annotated[str | None, Form(description="Optional custom display title")] = None,
    revises_document_id: Annotated[uuid.UUID | None, Form(description="Document ID that this upload supersedes / revises")] = None,
    effective_date: Annotated[datetime | None, Form(description="Optional document effective date")] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> DocumentUploadResponse:
    """Ingest, validate, store, and safely extract document text with provenance."""
    ip_address = request.client.host if request.client else None

    # 1. Server-side permission check: user must be authorized to upload to target department
    if not can_upload_document(current_user, department_id):
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_document",
            outcome="deny",
            resource_type="document",
            details={"department_id": str(department_id), "reason": "unauthorized_department"},
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload documents for this department",
        )

    # 2. Read and validate file content
    try:
        file_bytes = await file.read()
        validated = validate_file_upload(
            filename=file.filename or "uploaded_document",
            file_bytes=file_bytes,
        )
    except FileValidationError as err:
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_document",
            outcome="deny",
            resource_type="document",
            details={"filename": file.filename, "error": err.message},
            ip_address=ip_address,
        )
        raise HTTPException(status_code=err.status_code, detail=err.message)

    # 2.5 Revision inspection (if revising an existing document)
    target_original_doc: Document | None = None
    if revises_document_id is not None:
        orig_stmt = (
            select(Document)
            .options(selectinload(Document.grants))
            .where(Document.id == revises_document_id, Document.status != "deleted")
        )
        target_original_doc = (await db.execute(orig_stmt)).scalars().first()
        if not target_original_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document to revise not found",
            )
        if not (can_manage_grants(current_user, target_original_doc) or can_upload_document(current_user, target_original_doc.department_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to revise this document",
            )
        if target_original_doc.checksum_sha256 == validated.checksum_sha256:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Revision content is identical to the current revision",
            )

    # 2.6 Duplicate upload detection via checksum against active documents in the target department
    target_dept_id = target_original_doc.department_id if target_original_doc else department_id
    dup_stmt = select(Document).where(
        Document.department_id == target_dept_id,
        Document.checksum_sha256 == validated.checksum_sha256,
        Document.lifecycle_state == "active",
        Document.status != "deleted",
    )
    existing_dup = (await db.execute(dup_stmt)).scalars().first()
    if existing_dup:
        if target_original_doc is None or existing_dup.logical_document_id != target_original_doc.logical_document_id:
            await log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_document",
                outcome="deny",
                resource_type="document",
                details={
                    "reason": "duplicate_document",
                    "checksum": validated.checksum_sha256,
                    "existing_id": str(existing_dup.id),
                },
                ip_address=ip_address,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate document detected: exact content already exists with ID {existing_dup.id}",
            )

    display_title = title.strip() if title and title.strip() else validated.sanitized_filename

    # 3. Save to storage abstraction with server-generated key
    storage_key = f"{uuid.uuid4().hex}.{validated.file_type}"
    try:
        await storage.save_file(storage_key, file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist document to storage",
        )

    # 4. Safe text extraction
    extraction = extract_document_text(validated.file_type, file_bytes)

    # Lifecycle status based on extraction outcome
    doc_status = "failed" if extraction.status == "failed" else "uploaded"

    # 5. Version and lineage assignment
    new_doc_id = uuid.uuid4()
    if target_original_doc is not None:
        logical_doc_id = target_original_doc.logical_document_id
        supersedes_id = target_original_doc.id
        max_v_stmt = select(func.max(Document.version)).where(Document.logical_document_id == logical_doc_id)
        current_max_ver = (await db.execute(max_v_stmt)).scalar() or target_original_doc.version
        new_version = current_max_ver + 1
    else:
        logical_doc_id = new_doc_id
        supersedes_id = None
        new_version = 1

    # 6. Persist document record in PostgreSQL
    doc = Document(
        id=new_doc_id,
        logical_document_id=logical_doc_id,
        supersedes_id=supersedes_id,
        version=new_version,
        lifecycle_state="active",
        effective_date=effective_date or datetime.now(timezone.utc),
        title=display_title,
        owner_id=current_user.id,
        department_id=target_dept_id,
        storage_key=storage_key,
        file_type=validated.file_type,
        file_size_bytes=validated.file_size_bytes,
        checksum_sha256=validated.checksum_sha256,
        is_confidential=is_confidential,
        status=doc_status,
    )
    db.add(doc)

    # 7. Invalidate superseded vectors and update older active revisions in the family
    if target_original_doc is not None:
        prev_active_stmt = select(Document).where(
            Document.logical_document_id == logical_doc_id,
            Document.lifecycle_state == "active",
            Document.id != new_doc_id,
        )
        prev_active_docs = (await db.execute(prev_active_stmt)).scalars().all()
        for prev_doc in prev_active_docs:
            prev_doc.lifecycle_state = "superseded"
            db.add(prev_doc)
            vector_store.delete_by_document(prev_doc.id)

        # Inherit explicit grants from the original document
        for grant in target_original_doc.grants:
            new_grant = DocumentGrant(
                document_id=doc.id,
                grantee_user_id=grant.grantee_user_id,
                grantee_role_id=grant.grantee_role_id,
                permission=grant.permission,
                granted_by_user_id=current_user.id,
            )
            db.add(new_grant)

    await db.commit()
    await db.refresh(doc)

    # 8. Index document into vector store if extraction succeeded
    if doc.status != "failed" and extraction.passages:
        try:
            await index_document(
                document=doc,
                db=db,
                storage=storage,
                vector_store=vector_store,
                embedding_provider=embedding_provider,
            )
        except Exception as exc:
            pass

    # Log successful ingestion
    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="upload_document",
        outcome="allow",
        resource_id=str(doc.id),
        resource_type="document",
        details={
            "title": doc.title,
            "department_id": str(target_dept_id),
            "logical_document_id": str(doc.logical_document_id),
            "version": doc.version,
            "supersedes_id": str(doc.supersedes_id) if doc.supersedes_id else None,
            "passages_count": len(extraction.passages),
            "status": doc.status,
        },
        ip_address=ip_address,
    )

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(doc),
        extraction_status=extraction.status,
        total_passages=len(extraction.passages),
        warning_message=extraction.warning_message,
    )


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


@router.get(
    "/{document_id}/content",
    response_model=DocumentContentResponse,
    summary="Get extracted document content",
    description="Fetches extracted text passages with location coordinates for an authorized document.",
)
async def get_document_content(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentContentResponse:
    """Retrieve extracted passages with exact citation locations for authorized user."""
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    document = result.scalars().first()

    if document is None or document.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not await can_read_document(current_user, document, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to document content")

    try:
        file_bytes = await storage.read_file(document.storage_key)
        extraction = extract_document_text(document.file_type, file_bytes)
        passages = [
            DocumentPassageRead(location=p.location, text=p.text, passage_index=p.passage_index)
            for p in extraction.passages
        ]
        total_passages = len(extraction.passages)
        total_characters = extraction.total_characters
    except FileNotFoundError:
        # Fall back to indexed vector store chunks for pre-seeded or external documents
        chunks = vector_store.get_by_document(document.id)
        if not chunks:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document binary not found in storage")
        passages = [
            DocumentPassageRead(location=c.location, text=c.text, passage_index=c.chunk_index)
            for c in chunks
        ]
        total_passages = len(passages)
        total_characters = sum(len(c.text) for c in chunks)

    return DocumentContentResponse(
        document_id=document.id,
        title=document.title,
        passages=passages,
        total_passages=total_passages,
        total_characters=total_characters,
    )


@router.delete(
    "/{document_id}",
    summary="Delete document",
    description="Idempotently deletes a document, removing its stored file, indexed vectors, and updating database status.",
)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict[str, str]:
    """Idempotently delete document and remove underlying storage file and vectors."""
    ip_address = request.client.host if request.client else None

    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    document = result.scalars().first()

    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.status == "deleted":
        return {"status": "deleted", "document_id": str(document.id)}

    if not can_manage_grants(current_user, document):
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="delete_document",
            outcome="deny",
            resource_id=str(document.id),
            resource_type="document",
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this document",
        )

    # 1. Remove vectors from vector store
    vector_store.delete_by_document(document.id)

    # 2. Remove file from storage
    await storage.delete_file(document.storage_key)

    # 3. Mark status as deleted in database
    document.status = "deleted"
    document.lifecycle_state = "deleted"
    db.add(document)
    await db.commit()

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="delete_document",
        outcome="allow",
        resource_id=str(document.id),
        resource_type="document",
        ip_address=ip_address,
    )

    return {"status": "deleted", "document_id": str(document.id)}


@router.post(
    "/{document_id}/index",
    summary="Index or re-index document",
    description="Extracts, chunks, embeds, and updates the vector index for an authorized document.",
)
async def index_document_endpoint(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict[str, Any]:
    """Manually trigger or refresh indexing for a document."""
    ip_address = request.client.host if request.client else None

    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    document = result.scalars().first()

    if document is None or document.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not can_manage_grants(current_user, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to index this document",
        )

    chunks_count = await index_document(
        document=document,
        db=db,
        storage=storage,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
    )

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="index_document",
        outcome="allow",
        resource_id=str(document.id),
        resource_type="document",
        details={"chunks_indexed": chunks_count, "status": document.status},
        ip_address=ip_address,
    )

    return {
        "status": document.status,
        "document_id": str(document.id),
        "chunks_indexed": chunks_count,
    }


@router.get(
    "/{document_id}/chunks",
    response_model=List[DocumentChunkRead],
    summary="Get indexed document chunks",
    description="Returns all indexed chunks for an authorized document.",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    vector_store: VectorStore = Depends(get_vector_store),
) -> List[DocumentChunkRead]:
    """Retrieve all indexed chunks for an authorized document."""
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    document = result.scalars().first()

    if document is None or document.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not await can_read_document(current_user, document, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to document chunks")

    return vector_store.get_by_document(document_id)


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


@router.post(
    "/{document_id}/rollback",
    response_model=DocumentRead,
    summary="Roll back to a prior document revision",
    description="Restores a previous revision as active, marks the current active revision as superseded, and updates vector store indexes.",
)
async def rollback_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> DocumentRead:
    """Restore a previous revision as the active document version."""
    ip_address = request.client.host if request.client else None

    stmt = (
        select(Document)
        .options(selectinload(Document.grants))
        .where(Document.id == document_id)
    )
    result = await db.execute(stmt)
    target_doc = result.scalars().first()

    if target_doc is None or target_doc.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document revision not found",
        )

    # Permission check: must be owner, department manager, or admin
    if not (can_manage_grants(current_user, target_doc) or can_upload_document(current_user, target_doc.department_id)):
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="rollback_document",
            outcome="deny",
            resource_id=str(target_doc.id),
            resource_type="document",
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to roll back this document",
        )

    if target_doc.lifecycle_state == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document revision is already active",
        )

    # 1. Supersede any currently active revision(s) in this family and purge their vectors
    active_stmt = select(Document).where(
        Document.logical_document_id == target_doc.logical_document_id,
        Document.lifecycle_state == "active",
    )
    active_docs = (await db.execute(active_stmt)).scalars().all()
    for active_doc in active_docs:
        active_doc.lifecycle_state = "superseded"
        db.add(active_doc)
        vector_store.delete_by_document(active_doc.id)

    # 2. Mark target document as active
    target_doc.lifecycle_state = "active"
    db.add(target_doc)
    await db.commit()
    await db.refresh(target_doc)

    # 3. Re-index target document into vector store
    await index_document(
        document=target_doc,
        db=db,
        storage=storage,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
    )

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="rollback_document",
        outcome="allow",
        resource_id=str(target_doc.id),
        resource_type="document",
        details={
            "logical_document_id": str(target_doc.logical_document_id),
            "restored_version": target_doc.version,
        },
        ip_address=ip_address,
    )

    return DocumentRead.model_validate(target_doc)


@router.get(
    "/{document_id}/history",
    response_model=DocumentHistoryResponse,
    summary="Get document revision history timeline",
    description="Returns all revisions belonging to the same logical document ordered by version descending.",
)
async def get_document_history(
    document_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentHistoryResponse:
    """Fetch all revisions in the logical document family ordered by version descending."""
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    target_doc = result.scalars().first()

    if target_doc is None or target_doc.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not await can_read_document(current_user, target_doc, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to document history")

    hist_stmt = (
        select(Document)
        .where(
            Document.logical_document_id == target_doc.logical_document_id,
            Document.status != "deleted",
        )
        .order_by(Document.version.desc())
    )
    revisions = (await db.execute(hist_stmt)).scalars().all()

    active_ver = target_doc.version
    for rev in revisions:
        if rev.lifecycle_state == "active":
            active_ver = rev.version
            break

    return DocumentHistoryResponse(
        logical_document_id=target_doc.logical_document_id,
        title=target_doc.title,
        active_version=active_ver,
        total_revisions=len(revisions),
        revisions=[DocumentRevisionHistoryItem.model_validate(r) for r in revisions],
    )
