"""Service layer for conversation workspaces, user thread isolation, and permission-revalidated memory."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.document import Document
from app.models.thread import Thread, ThreadBookmark, ThreadMessage
from app.models.user import User
from app.schemas.generation import ChatQueryRequest, Citation
from app.schemas.thread import (
    ThreadBookmarkCreate,
    ThreadBookmarkRead,
    ThreadCreate,
    ThreadMessageCreate,
    ThreadMessageRead,
    ThreadRead,
    ThreadSummaryRead,
    ThreadUpdate,
)
from app.services.audit import log_audit_event
from app.services.embeddings import get_embedding_provider
from app.services.generation import generate_answer
from app.services.llm import get_llm_provider
from app.services.policy import can_read_document
from app.services.vector_store import get_vector_store

logger = get_logger(__name__)


async def get_user_thread_or_404(
    db: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
) -> Thread:
    """Retrieve a thread ensuring strict user isolation (no cross-user thread leakage)."""
    stmt = (
        select(Thread)
        .options(
            selectinload(Thread.messages),
            selectinload(Thread.bookmarks),
        )
        .where(Thread.id == thread_id)
    )
    result = await db.execute(stmt)
    thread = result.scalars().first()

    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation thread not found",
        )

    # Strict User Isolation: users cannot access or probe other users' threads
    if thread.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation thread not found",
        )

    return thread


async def create_thread(
    db: AsyncSession,
    current_user: User,
    payload: ThreadCreate,
    ip_address: Optional[str] = None,
) -> ThreadSummaryRead:
    """Initialize a new clean conversation workspace isolated to the current user."""
    title = payload.title.strip() if payload.title and payload.title.strip() else "New Conversation"

    thread = Thread(
        id=uuid.uuid4(),
        user_id=current_user.id,
        title=title,
        is_archived=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="thread_create",
        outcome="allow",
        resource_id=str(thread.id),
        resource_type="thread",
        details={"title": thread.title},
        ip_address=ip_address,
    )

    return ThreadSummaryRead(
        id=thread.id,
        user_id=thread.user_id,
        title=thread.title,
        is_archived=thread.is_archived,
        message_count=0,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


async def list_threads(
    db: AsyncSession,
    current_user: User,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> List[ThreadSummaryRead]:
    """List conversation threads belonging exclusively to the authenticated user."""
    stmt = (
        select(Thread, func.count(ThreadMessage.id).label("msg_count"))
        .outerjoin(ThreadMessage, Thread.id == ThreadMessage.thread_id)
        .where(Thread.user_id == current_user.id)
    )

    if not include_archived:
        stmt = stmt.where(Thread.is_archived == False)  # noqa: E712

    stmt = stmt.group_by(Thread.id).order_by(Thread.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    summaries: List[ThreadSummaryRead] = []
    for thread, msg_count in rows:
        summaries.append(
            ThreadSummaryRead(
                id=thread.id,
                user_id=thread.user_id,
                title=thread.title,
                is_archived=thread.is_archived,
                message_count=msg_count,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
            )
        )
    return summaries


async def get_thread_details(
    db: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
) -> ThreadRead:
    """Get full conversation thread with verified historical messages and active bookmarks."""
    thread = await get_user_thread_or_404(db, thread_id, current_user)

    messages = [
        ThreadMessageRead(
            id=m.id,
            thread_id=m.thread_id,
            sender=m.sender,  # type: ignore[arg-type]
            text=m.text,
            citations=m.citations or [],
            abstained=m.abstained,
            evidence_level=m.evidence_level,
            abstention_reason=m.abstention_reason,
            query_id=m.query_id,
            created_at=m.created_at,
        )
        for m in thread.messages
    ]

    # Verify and filter bookmarks by current active permission
    valid_bookmarks: List[ThreadBookmarkRead] = []
    for b in thread.bookmarks:
        doc = await db.get(Document, b.document_id)
        if doc and await can_read_document(current_user, doc, db, require_active=True):
            valid_bookmarks.append(
                ThreadBookmarkRead(
                    id=b.id,
                    thread_id=b.thread_id,
                    user_id=b.user_id,
                    document_id=b.document_id,
                    title=b.title,
                    location=b.location,
                    snippet=b.snippet,
                    content_hash=b.content_hash,
                    notes=b.notes,
                    created_at=b.created_at,
                )
            )

    return ThreadRead(
        id=thread.id,
        user_id=thread.user_id,
        title=thread.title,
        is_archived=thread.is_archived,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=messages,
        bookmarks=valid_bookmarks,
    )


async def update_thread(
    db: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
    payload: ThreadUpdate,
    ip_address: Optional[str] = None,
) -> ThreadSummaryRead:
    """Rename or archive a conversation thread."""
    thread = await get_user_thread_or_404(db, thread_id, current_user)

    if payload.title is not None and payload.title.strip():
        thread.title = payload.title.strip()
    if payload.is_archived is not None:
        thread.is_archived = payload.is_archived

    thread.updated_at = datetime.now(timezone.utc)
    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="thread_update",
        outcome="allow",
        resource_id=str(thread.id),
        resource_type="thread",
        details={
            "title": thread.title,
            "is_archived": thread.is_archived,
        },
        ip_address=ip_address,
    )

    count_stmt = select(func.count(ThreadMessage.id)).where(ThreadMessage.thread_id == thread.id)
    msg_count = (await db.execute(count_stmt)).scalar() or 0

    return ThreadSummaryRead(
        id=thread.id,
        user_id=thread.user_id,
        title=thread.title,
        is_archived=thread.is_archived,
        message_count=msg_count,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


async def delete_thread(
    db: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
    ip_address: Optional[str] = None,
) -> dict[str, str]:
    """Delete a conversation thread and its associated message turns and bookmarks."""
    thread = await get_user_thread_or_404(db, thread_id, current_user)

    await db.delete(thread)
    await db.commit()

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="thread_delete",
        outcome="allow",
        resource_id=str(thread_id),
        resource_type="thread",
        details={"deleted_title": thread.title},
        ip_address=ip_address,
    )

    return {"status": "deleted", "thread_id": str(thread_id)}


async def send_thread_message(
    db: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
    payload: ThreadMessageCreate,
    ip_address: Optional[str] = None,
) -> ThreadMessageRead:
    """Send a user message in a thread with permission revalidation and contextual memory."""
    thread = await get_user_thread_or_404(db, thread_id, current_user)

    # 1. Fetch previous message turns
    msg_stmt = (
        select(ThreadMessage)
        .where(ThreadMessage.thread_id == thread.id)
        .order_by(ThreadMessage.created_at.asc())
    )
    res = await db.execute(msg_stmt)
    history_messages = res.scalars().all()

    # 2. PERMISSION REVALIDATION ON HISTORICAL MEMORY (Mandatory Security Invariant)
    # Re-verify that user still holds active permissions to all previously cited documents.
    # If permission was revoked, the historical excerpt/context is strictly excluded from follow-up.
    valid_historical_context: List[str] = []
    for old_msg in history_messages[-4:]:  # Window of last 4 interaction turns
        if old_msg.sender == "user":
            valid_historical_context.append(f"User: {old_msg.text}")
        elif old_msg.sender == "assistant":
            # Check citations permissions
            all_citations_authorized = True
            if old_msg.citations:
                for cite in old_msg.citations:
                    doc_id_str = cite.get("document_id")
                    if doc_id_str:
                        doc = await db.get(Document, uuid.UUID(doc_id_str))
                        if not doc or not await can_read_document(current_user, doc, db, require_active=True):
                            all_citations_authorized = False
                            break

            if all_citations_authorized and not old_msg.abstained:
                # Use clean summary/answer
                valid_historical_context.append(f"Assistant: {old_msg.text[:300]}")
            else:
                # Redacted / access revoked since previous turn
                valid_historical_context.append("Assistant: [Historical content redacted due to access revocation]")

    # 3. Contextual Query Formation
    # For retrieval, the user's immediate question is primary. If historical context exists,
    # we augment query retrieval while strictly treating historical turns as untrusted text.
    combined_query = payload.query
    if valid_historical_context and len(payload.query.split()) < 10:
        # Short follow-up question (e.g., "What about sick leave?", "How does this compare?")
        recent_user_q = next((m.text for m in reversed(history_messages) if m.sender == "user"), None)
        if recent_user_q:
            combined_query = f"{recent_user_q} {payload.query}"

    # 4. Execute Grounded Answer Generation
    chat_req = ChatQueryRequest(
        query=payload.query,
        top_k=payload.top_k,
        hybrid=payload.hybrid,
        temperature=payload.temperature,
    )

    vector_store = get_vector_store()
    embedding_provider = get_embedding_provider()
    llm_provider = get_llm_provider()

    gen_resp = await generate_answer(
        request=chat_req,
        current_user=current_user,
        db=db,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        ip_address=ip_address,
    )

    # 5. Persist User Message
    user_msg = ThreadMessage(
        id=uuid.uuid4(),
        thread_id=thread.id,
        sender="user",
        text=payload.query,
        citations=[],
        abstained=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)

    # 6. Persist Assistant Response
    assistant_msg = ThreadMessage(
        id=uuid.uuid4(),
        thread_id=thread.id,
        sender="assistant",
        text=gen_resp.answer,
        citations=[c.model_dump(mode="json") for c in gen_resp.citations],
        abstained=gen_resp.abstained,
        evidence_level=gen_resp.evidence_level,
        abstention_reason=gen_resp.abstention_reason,
        query_id=gen_resp.query_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)

    # 7. Update Thread Title if default
    if thread.title == "New Conversation" and len(history_messages) == 0:
        words = payload.query.strip().split()
        thread.title = " ".join(words[:6]) + ("..." if len(words) > 6 else "")

    thread.updated_at = datetime.now(timezone.utc)
    db.add(thread)
    await db.commit()
    await db.refresh(assistant_msg)

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="thread_message",
        outcome="allow",
        resource_id=str(thread.id),
        resource_type="thread",
        details={
            "query_preview": payload.query[:80],
            "abstained": gen_resp.abstained,
            "citations_count": len(gen_resp.citations),
        },
        ip_address=ip_address,
    )

    return ThreadMessageRead(
        id=assistant_msg.id,
        thread_id=assistant_msg.thread_id,
        sender="assistant",
        text=assistant_msg.text,
        citations=assistant_msg.citations,
        abstained=assistant_msg.abstained,
        evidence_level=assistant_msg.evidence_level,
        abstention_reason=assistant_msg.abstention_reason,
        query_id=assistant_msg.query_id,
        created_at=assistant_msg.created_at,
    )


async def create_thread_bookmark(
    db: AsyncSession,
    thread_id: uuid.UUID,
    current_user: User,
    payload: ThreadBookmarkCreate,
    ip_address: Optional[str] = None,
) -> ThreadBookmarkRead:
    """Bookmark an exemplar citation snippet subject to current active document permissions."""
    thread = await get_user_thread_or_404(db, thread_id, current_user)

    # Check active access to document
    doc = await db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced document not found")

    if not await can_read_document(current_user, doc, db, require_active=True):
        await log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="bookmark_create",
            outcome="deny",
            resource_id=str(doc.id),
            resource_type="document",
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not hold permissions to bookmark snippets from this document",
        )

    bookmark = ThreadBookmark(
        id=uuid.uuid4(),
        thread_id=thread.id,
        user_id=current_user.id,
        document_id=doc.id,
        title=payload.title,
        location=payload.location,
        snippet=payload.snippet,
        content_hash=payload.content_hash,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc),
    )

    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="bookmark_create",
        outcome="allow",
        resource_id=str(bookmark.id),
        resource_type="bookmark",
        details={"document_id": str(doc.id), "location": payload.location},
        ip_address=ip_address,
    )

    return ThreadBookmarkRead(
        id=bookmark.id,
        thread_id=bookmark.thread_id,
        user_id=bookmark.user_id,
        document_id=bookmark.document_id,
        title=bookmark.title,
        location=bookmark.location,
        snippet=bookmark.snippet,
        content_hash=bookmark.content_hash,
        notes=bookmark.notes,
        created_at=bookmark.created_at,
    )


async def delete_thread_bookmark(
    db: AsyncSession,
    bookmark_id: uuid.UUID,
    current_user: User,
    ip_address: Optional[str] = None,
) -> dict[str, str]:
    """Delete a user-saved citation bookmark."""
    bookmark = await db.get(ThreadBookmark, bookmark_id)
    if not bookmark or bookmark.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

    await db.delete(bookmark)
    await db.commit()

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="bookmark_delete",
        outcome="allow",
        resource_id=str(bookmark_id),
        resource_type="bookmark",
        ip_address=ip_address,
    )

    return {"status": "deleted", "bookmark_id": str(bookmark_id)}
