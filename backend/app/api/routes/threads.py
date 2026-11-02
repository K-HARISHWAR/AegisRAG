"""API routes for conversation workspaces, multi-turn follow-ups, and citation bookmarks."""

from typing import Annotated, List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
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
from app.services.thread import (
    create_thread,
    create_thread_bookmark,
    delete_thread,
    delete_thread_bookmark,
    get_thread_details,
    list_threads,
    send_thread_message,
    update_thread,
)

router = APIRouter(prefix="/threads", tags=["Conversation Workspaces"])


@router.post(
    "",
    response_model=ThreadSummaryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation thread",
    description="Initializes a new, isolated conversation workspace for the authenticated user.",
)
async def create_new_thread(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: Optional[ThreadCreate] = None,
) -> ThreadSummaryRead:
    """Create a new user conversation thread with zero prior context."""
    ip_address = request.client.host if request.client else None
    if payload is None:
        payload = ThreadCreate()
    return await create_thread(db=db, current_user=current_user, payload=payload, ip_address=ip_address)


@router.get(
    "",
    response_model=List[ThreadSummaryRead],
    summary="List conversation threads",
    description="Lists all conversation threads belonging exclusively to the authenticated user.",
)
async def list_user_threads(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_archived: bool = Query(False, description="Whether to include archived threads"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[ThreadSummaryRead]:
    """Retrieve isolated threads for current user."""
    return await list_threads(
        db=db,
        current_user=current_user,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{thread_id}",
    response_model=ThreadRead,
    summary="Get conversation thread details",
    description="Fetches full interaction history and permission-verified bookmarks for a thread.",
)
async def get_thread(
    thread_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ThreadRead:
    """Get full thread details with strict user isolation (returns 404 for other users' threads)."""
    return await get_thread_details(db=db, thread_id=thread_id, current_user=current_user)


@router.patch(
    "/{thread_id}",
    response_model=ThreadSummaryRead,
    summary="Rename or archive thread",
    description="Updates conversation title or archive status.",
)
async def update_user_thread(
    thread_id: uuid.UUID,
    payload: ThreadUpdate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ThreadSummaryRead:
    """Update title or archive state with audit logging."""
    ip_address = request.client.host if request.client else None
    return await update_thread(
        db=db,
        thread_id=thread_id,
        current_user=current_user,
        payload=payload,
        ip_address=ip_address,
    )


@router.delete(
    "/{thread_id}",
    summary="Delete conversation thread",
    description="Permanently deletes thread and all associated messages and bookmarks.",
)
async def delete_user_thread(
    thread_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Permanently delete user's thread."""
    ip_address = request.client.host if request.client else None
    return await delete_thread(
        db=db,
        thread_id=thread_id,
        current_user=current_user,
        ip_address=ip_address,
    )


@router.post(
    "/{thread_id}/messages",
    response_model=ThreadMessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Post contextual follow-up message",
    description="Processes follow-up query with permission-revalidated historical context and returns grounded assistant answer.",
)
async def post_thread_message(
    thread_id: uuid.UUID,
    payload: ThreadMessageCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ThreadMessageRead:
    """Post query in thread with automatic permission revalidation on historical excerpts."""
    ip_address = request.client.host if request.client else None
    return await send_thread_message(
        db=db,
        thread_id=thread_id,
        current_user=current_user,
        payload=payload,
        ip_address=ip_address,
    )


@router.post(
    "/{thread_id}/bookmarks",
    response_model=ThreadBookmarkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Bookmark citation snippet",
    description="Saves a verified passage quote, re-checking active document permissions.",
)
async def add_bookmark(
    thread_id: uuid.UUID,
    payload: ThreadBookmarkCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ThreadBookmarkRead:
    """Bookmark citation snippet with server-side permission validation."""
    ip_address = request.client.host if request.client else None
    return await create_thread_bookmark(
        db=db,
        thread_id=thread_id,
        current_user=current_user,
        payload=payload,
        ip_address=ip_address,
    )


@router.delete(
    "/bookmarks/{bookmark_id}",
    summary="Delete bookmark",
    description="Removes a saved citation snippet.",
)
async def remove_bookmark(
    bookmark_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete bookmark owned by current user."""
    ip_address = request.client.host if request.client else None
    return await delete_thread_bookmark(
        db=db,
        bookmark_id=bookmark_id,
        current_user=current_user,
        ip_address=ip_address,
    )
