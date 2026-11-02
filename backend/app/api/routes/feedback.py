"""API routes for response feedback collection, quality analytics, and review tasks."""

from typing import Annotated, List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackReviewUpdateRequest,
    FeedbackStatsResponse,
)
from app.services.feedback import (
    get_feedback_stats,
    list_feedback,
    submit_feedback,
    update_review_task,
)

router = APIRouter(prefix="/feedback", tags=["Feedback & Evaluation"])


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit response feedback",
    description="Records user rating (positive/negative), failure tags, comment, and model provenance.",
)
async def submit_response_feedback(
    payload: FeedbackCreateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackResponse:
    """Submit end-user feedback linked to verified user identity."""
    ip_address = request.client.host if request.client else None
    return await submit_feedback(
        db=db,
        current_user=current_user,
        payload=payload,
        ip_address=ip_address,
    )


@router.get(
    "",
    response_model=List[FeedbackResponse],
    summary="List feedback records",
    description="Retrieves feedback records with server-enforced role and department scoping.",
)
async def list_feedback_records(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    rating: Optional[str] = Query(None, description="Filter by 'positive' or 'negative'"),
    review_status: Optional[str] = Query(None, description="Filter by review task status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[FeedbackResponse]:
    """Retrieve feedback records scoped to authorized tenant boundaries."""
    return await list_feedback(
        db=db,
        current_user=current_user,
        rating=rating,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get feedback quality analytics",
    description="Returns aggregated quality metrics, failure reason breakdown, and review task counts.",
)
async def get_quality_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackStatsResponse:
    """Get aggregated quality metrics for managers and administrators."""
    return await get_feedback_stats(db=db, current_user=current_user)


@router.patch(
    "/{feedback_id}/review",
    response_model=FeedbackResponse,
    summary="Triage and update human review task",
    description="Updates the review status and triage notes on a negative feedback record.",
)
async def update_review_task_status(
    feedback_id: uuid.UUID,
    payload: FeedbackReviewUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackResponse:
    """Update review status on negative feedback item with audit logging."""
    ip_address = request.client.host if request.client else None
    return await update_review_task(
        db=db,
        current_user=current_user,
        feedback_id=feedback_id,
        payload=payload,
        ip_address=ip_address,
    )
