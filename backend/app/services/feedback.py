"""Service layer for user feedback collection, quality analytics, and human review triage."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackReviewUpdateRequest,
    FeedbackStatsResponse,
)
from app.services.audit import log_audit_event

logger = get_logger(__name__)
settings = get_settings()


def _is_admin(user: User) -> bool:
    """Check if user has administrative privileges."""
    if user.is_superuser:
        return True
    return any(r.name == "admin" for r in user.roles)


def _is_manager(user: User) -> bool:
    """Check if user is a department manager or administrator."""
    if _is_admin(user):
        return True
    return any(r.name == "department_manager" for r in user.roles)


def _to_feedback_response(fb: Feedback) -> FeedbackResponse:
    """Serialize Feedback model to FeedbackResponse schema with user details."""
    user_email = fb.user.email if fb.user else None
    user_dept = fb.user.department.name if fb.user and fb.user.department else None
    reviewer_email = fb.reviewer.email if fb.reviewer else None

    return FeedbackResponse(
        id=fb.id,
        user_id=fb.user_id,
        user_email=user_email,
        user_department=user_dept,
        query_id=fb.query_id,
        request_id=fb.request_id,
        query_text=fb.query_text,
        answer_text=fb.answer_text,
        rating=fb.rating,  # type: ignore[arg-type]
        reason_tags=fb.reason_tags or [],
        comment=fb.comment,
        model_version=fb.model_version,
        prompt_version=fb.prompt_version,
        retrieved_document_versions=fb.retrieved_document_versions or {},
        evidence_level=fb.evidence_level,
        created_at=fb.created_at,
        review_status=fb.review_status,  # type: ignore[arg-type]
        reviewer_user_id=fb.reviewer_user_id,
        reviewer_email=reviewer_email,
        reviewer_notes=fb.reviewer_notes,
        reviewed_at=fb.reviewed_at,
    )


async def submit_feedback(
    db: AsyncSession,
    current_user: User,
    payload: FeedbackCreateRequest,
    ip_address: Optional[str] = None,
) -> FeedbackResponse:
    """Submit user feedback for an assistant response and trigger review tasks if negative."""
    if not settings.ENABLE_FEEDBACK_COLLECTION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback collection is currently disabled",
        )

    # Determine initial human review task state
    if payload.rating == "negative" and settings.FEEDBACK_AUTO_CREATE_REVIEW_TASK:
        review_status = "pending_review"
    else:
        review_status = "not_required"

    feedback_record = Feedback(
        id=uuid.uuid4(),
        user_id=current_user.id,
        query_id=payload.query_id,
        request_id=payload.request_id,
        query_text=payload.query_text,
        answer_text=payload.answer_text,
        rating=payload.rating,
        reason_tags=payload.reason_tags,
        comment=payload.comment,
        model_version=payload.model_version or settings.LLM_MODEL,
        prompt_version=payload.prompt_version or settings.SYSTEM_PROMPT_VERSION,
        retrieved_document_versions=payload.retrieved_document_versions,
        evidence_level=payload.evidence_level,
        created_at=datetime.now(timezone.utc),
        review_status=review_status,
    )

    db.add(feedback_record)
    await db.commit()
    await db.refresh(feedback_record, attribute_names=["user", "reviewer"])

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="feedback_submission",
        outcome="allow",
        resource_id=str(feedback_record.id),
        resource_type="feedback",
        details={
            "query_id": str(payload.query_id) if payload.query_id else None,
            "rating": payload.rating,
            "reason_tags": payload.reason_tags,
            "review_status": review_status,
        },
        ip_address=ip_address,
    )

    return _to_feedback_response(feedback_record)


async def list_feedback(
    db: AsyncSession,
    current_user: User,
    rating: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[FeedbackResponse]:
    """List feedback records with strict department and role scoping."""
    stmt = (
        select(Feedback)
        .options(
            selectinload(Feedback.user).selectinload(User.department),
            selectinload(Feedback.reviewer),
        )
        .order_by(Feedback.created_at.desc())
    )

    # RBAC Scoping
    if _is_admin(current_user):
        pass  # Global administrator sees all feedback
    elif _is_manager(current_user):
        # Manager sees feedback from users in their own department
        stmt = stmt.join(User, Feedback.user_id == User.id).where(
            User.department_id == current_user.department_id
        )
    else:
        # Standard employee can only see their own feedback submissions
        stmt = stmt.where(Feedback.user_id == current_user.id)

    if rating:
        stmt = stmt.where(Feedback.rating == rating)
    if review_status:
        stmt = stmt.where(Feedback.review_status == review_status)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [_to_feedback_response(r) for r in records]


async def get_feedback_stats(
    db: AsyncSession,
    current_user: User,
) -> FeedbackStatsResponse:
    """Compute aggregated feedback quality metrics and failure reason breakdown for authorized admins/managers."""
    if not _is_manager(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative or department manager privileges required to view quality statistics",
        )

    stmt = select(Feedback)
    if not _is_admin(current_user):
        stmt = stmt.join(User, Feedback.user_id == User.id).where(
            User.department_id == current_user.department_id
        )

    result = await db.execute(stmt)
    all_feedbacks = result.scalars().all()

    total = len(all_feedbacks)
    if total == 0:
        return FeedbackStatsResponse(
            total_feedback=0,
            positive_count=0,
            negative_count=0,
            satisfaction_rate=0.0,
            failure_categories={},
            pending_reviews_count=0,
            in_review_count=0,
            resolved_reviews_count=0,
        )

    positive_count = sum(1 for f in all_feedbacks if f.rating == "positive")
    negative_count = sum(1 for f in all_feedbacks if f.rating == "negative")
    satisfaction_rate = round(positive_count / total, 4) if total > 0 else 0.0

    failure_categories: Dict[str, int] = {}
    pending_count = 0
    in_review_count = 0
    resolved_count = 0

    for f in all_feedbacks:
        if f.review_status == "pending_review":
            pending_count += 1
        elif f.review_status == "in_review":
            in_review_count += 1
        elif f.review_status in ("resolved", "dismissed", "reviewed"):
            resolved_count += 1

        if f.rating == "negative" and f.reason_tags:
            for tag in f.reason_tags:
                failure_categories[tag] = failure_categories.get(tag, 0) + 1

    return FeedbackStatsResponse(
        total_feedback=total,
        positive_count=positive_count,
        negative_count=negative_count,
        satisfaction_rate=satisfaction_rate,
        failure_categories=failure_categories,
        pending_reviews_count=pending_count,
        in_review_count=in_review_count,
        resolved_reviews_count=resolved_count,
    )


async def update_review_task(
    db: AsyncSession,
    current_user: User,
    feedback_id: uuid.UUID,
    payload: FeedbackReviewUpdateRequest,
    ip_address: Optional[str] = None,
) -> FeedbackResponse:
    """Triage and update review status on a negative feedback record."""
    if not _is_manager(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative or department manager privileges required to update review tasks",
        )

    stmt = (
        select(Feedback)
        .options(
            selectinload(Feedback.user).selectinload(User.department),
            selectinload(Feedback.reviewer),
        )
        .where(Feedback.id == feedback_id)
    )
    result = await db.execute(stmt)
    record = result.scalars().first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback record not found",
        )

    # Department scoping for managers
    if not _is_admin(current_user) and record.user:
        if record.user.department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot triage feedback outside your department",
            )

    record.review_status = payload.review_status
    record.reviewer_user_id = current_user.id
    if payload.reviewer_notes is not None:
        record.reviewer_notes = payload.reviewer_notes
    record.reviewed_at = datetime.now(timezone.utc)

    db.add(record)
    await db.commit()
    await db.refresh(record, attribute_names=["user", "reviewer"])

    await log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="feedback_review_triage",
        outcome="allow",
        resource_id=str(record.id),
        resource_type="feedback",
        details={
            "feedback_id": str(record.id),
            "new_status": payload.review_status,
            "has_notes": bool(payload.reviewer_notes),
        },
        ip_address=ip_address,
    )

    return _to_feedback_response(record)

