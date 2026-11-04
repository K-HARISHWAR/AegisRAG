"""API routes for read-only knowledge workflows (version comparison, collection summaries, extraction, export)."""

import json
import re
import uuid
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.policy_codes import PolicyReasonCode
from app.core.workflow_tools import (
    ALLOWLISTED_WORKFLOW_TOOLS,
    DISALLOWED_TOOLS,
    DisallowedToolError,
    verify_tool_allowlist,
)
from app.models.user import User
from app.models.workflow import WorkflowExecution
from app.schemas.workflow import (
    CollectionSummaryRequest,
    CollectionSummaryResponse,
    StructuredExtractionRequest,
    StructuredExtractionResponse,
    VersionComparisonRequest,
    VersionComparisonResponse,
    WorkflowExecutionRead,
    WorkflowExportRequest,
)
from app.services.audit import log_audit_event
from app.services.storage import StorageProvider, get_storage_provider
from app.services.vector_store import VectorStore, get_vector_store
from app.services.workflow import (
    execute_collection_summary,
    execute_structured_extraction,
    execute_version_comparison,
    render_workflow_markdown,
    render_workflow_pdf,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get(
    "/tools",
    summary="Get approved read-only tool allowlist",
    description="Returns the explicit set of allowlisted workflow tools and active security boundaries.",
)
async def get_tool_allowlist(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Inspect the system's approved read-only tool allowlist."""
    return {
        "is_read_only": True,
        "allowed_tools": sorted(list(ALLOWLISTED_WORKFLOW_TOOLS)),
        "disallowed_tools_sample": sorted(list(DISALLOWED_TOOLS))[:10],
        "default_deny": True,
        "external_write_actions_permitted": False,
    }


@router.post(
    "/compare",
    response_model=VersionComparisonResponse,
    summary="Compare two authorized document revisions",
    description="Computes clause additions, deletions, modifications, and policy impacts between two document versions.",
)
async def compare_documents(
    payload: VersionComparisonRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> VersionComparisonResponse:
    """Execute version comparison workflow with strict PostgreSQL permission verification."""
    ip_address = request.client.host if request.client else None
    return await execute_version_comparison(
        user=current_user,
        source_document_id=payload.source_document_id,
        target_document_id=payload.target_document_id,
        focus=payload.focus,
        db=db,
        storage=storage,
        vector_store=vector_store,
        ip_address=ip_address,
    )


@router.post(
    "/summarize-collection",
    response_model=CollectionSummaryResponse,
    summary="Synthesize an authorized collection of documents",
    description="Summarizes an authorized multi-document collection or department scope, strictly excluding restricted documents.",
)
async def summarize_collection(
    payload: CollectionSummaryRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> CollectionSummaryResponse:
    """Execute collection summary workflow with default-deny RBAC filtering."""
    ip_address = request.client.host if request.client else None
    return await execute_collection_summary(
        user=current_user,
        document_ids=payload.document_ids,
        department_id=payload.department_id,
        collection_title=payload.collection_title,
        focus_query=payload.focus_query,
        db=db,
        storage=storage,
        vector_store=vector_store,
        ip_address=ip_address,
    )


@router.post(
    "/extract-fields",
    response_model=StructuredExtractionResponse,
    summary="Extract structured fields, requirements, and risks",
    description="Extracts metadata, custodian, review cycles, requirements, and a risk matrix with citation coordinates.",
)
async def extract_document_fields(
    payload: StructuredExtractionRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: StorageProvider = Depends(get_storage_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> StructuredExtractionResponse:
    """Execute structured field extraction workflow."""
    ip_address = request.client.host if request.client else None
    return await execute_structured_extraction(
        user=current_user,
        document_id=payload.document_id,
        template_type=payload.template_type,
        db=db,
        storage=storage,
        vector_store=vector_store,
        ip_address=ip_address,
    )


@router.post(
    "/export",
    summary="Export authorized workflow summary to Markdown or PDF",
    description="Generates an authorized export artifact in Markdown or PDF with verified source citations.",
)
async def export_workflow(
    payload: WorkflowExportRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Export workflow results with provenance citations to Markdown, text, or PDF."""
    ip_address = request.client.host if request.client else None
    title = payload.title or f"{payload.workflow_type.title()} Report"
    md_content = render_workflow_markdown(
        workflow_type=payload.workflow_type,
        title=title,
        data=payload.data,
    )

    fmt = payload.format.lower().strip()

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="workflow_export",
        outcome="allow",
        policy_reason_code=PolicyReasonCode.WORKFLOW_EXPORTED,
        resource_id=str(payload.workflow_id) if payload.workflow_id else None,
        resource_type="workflow",
        details={
            "workflow_type": payload.workflow_type,
            "format": fmt,
            "title": title,
        },
        ip_address=ip_address,
    )

    if fmt == "pdf":
        pdf_bytes = render_workflow_pdf(md_content)
        safe_filename = re.sub(r"[^\w\-_\.]", "_", title.lower()) + ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
            },
        )

    # Default to Markdown / plain text
    safe_filename = re.sub(r"[^\w\-_\.]", "_", title.lower()) + ".md"
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


@router.get(
    "/history",
    response_model=List[WorkflowExecutionRead],
    summary="List past workflow executions",
    description="Returns recent workflow executions completed by the authenticated user.",
)
async def get_workflow_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(20, ge=1, le=100),
) -> List[WorkflowExecutionRead]:
    """Retrieve history of workflows executed by the current user."""
    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.user_id == current_user.id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    results = []
    for r in records:
        steps_list = None
        result_dict = None
        if r.steps:
            try:
                steps_list = json.loads(r.steps)
            except Exception:
                pass
        if r.result_data:
            try:
                result_dict = json.loads(r.result_data)
            except Exception:
                pass

        results.append(
            WorkflowExecutionRead(
                id=r.id,
                workflow_type=r.workflow_type,
                status=r.status,
                title=r.title,
                total_duration_ms=r.total_duration_ms,
                created_at=r.created_at,
                steps=steps_list,
                result_data=result_dict,
            )
        )
    return results


@router.get(
    "/{execution_id}",
    response_model=WorkflowExecutionRead,
    summary="Get single workflow execution details",
)
async def get_workflow_execution(
    execution_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkflowExecutionRead:
    """Retrieve details of a single workflow execution."""
    stmt = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    res = await db.execute(stmt)
    rec = res.scalars().first()

    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow execution not found")

    # Only owner or admin can view execution
    if rec.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to workflow execution")

    steps_list = None
    result_dict = None
    if rec.steps:
        try:
            steps_list = json.loads(rec.steps)
        except Exception:
            pass
    if rec.result_data:
        try:
            result_dict = json.loads(rec.result_data)
        except Exception:
            pass

    return WorkflowExecutionRead(
        id=rec.id,
        workflow_type=rec.workflow_type,
        status=rec.status,
        title=rec.title,
        total_duration_ms=rec.total_duration_ms,
        created_at=rec.created_at,
        steps=steps_list,
        result_data=result_dict,
    )
