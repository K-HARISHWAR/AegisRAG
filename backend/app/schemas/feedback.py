"""Pydantic schemas for feedback collection, quality metrics, and human review tasks."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

FeedbackRating = Literal["positive", "negative"]
FeedbackReasonTag = Literal[
    "incorrect",
    "incomplete",
    "outdated",
    "poor_citation",
    "irrelevant_retrieval",
    "access_issue",
]
ReviewStatus = Literal[
    "pending_review",
    "in_review",
    "reviewed",
    "resolved",
    "dismissed",
    "not_required",
]


class FeedbackCreateRequest(BaseModel):
    """Schema for submitting end-user feedback on an assistant response."""

    query_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Correlation query identifier returned in ChatQueryResponse",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="HTTP request ID correlation token",
    )
    query_text: str = Field(
        min_length=1,
        max_length=4000,
        description="Original user prompt",
    )
    answer_text: str = Field(
        min_length=1,
        description="Assistant answer text being rated",
    )
    rating: FeedbackRating = Field(
        description="Primary binary rating: 'positive' (thumbs-up) or 'negative' (thumbs-down)",
    )
    reason_tags: List[str] = Field(
        default_factory=list,
        description="Specific failure categorization tags (e.g. 'incorrect', 'outdated', 'poor_citation')",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional free-text explanation from the user",
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Model configuration identifier active during answer generation",
    )
    prompt_version: Optional[str] = Field(
        default=None,
        description="Prompt template version identifier",
    )
    retrieved_document_versions: Dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of document IDs to active version numbers referenced in context",
    )
    evidence_level: Optional[str] = Field(
        default=None,
        description="Qualitative evidence label assigned to the response ('strong', 'limited', 'insufficient')",
    )


class FeedbackReviewUpdateRequest(BaseModel):
    """Schema for human review triage of negative feedback."""

    review_status: ReviewStatus = Field(
        description="Updated lifecycle state for the review task",
    )
    reviewer_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Triage notes, root-cause assessment, or resolution details",
    )


class FeedbackResponse(BaseModel):
    """Detailed feedback record schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: Optional[str] = None
    user_department: Optional[str] = None
    query_id: Optional[uuid.UUID] = None
    request_id: Optional[str] = None
    query_text: str
    answer_text: str
    rating: FeedbackRating
    reason_tags: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    retrieved_document_versions: Dict[str, int] = Field(default_factory=dict)
    evidence_level: Optional[str] = None
    created_at: datetime
    review_status: ReviewStatus
    reviewer_user_id: Optional[uuid.UUID] = None
    reviewer_email: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class FeedbackStatsResponse(BaseModel):
    """Aggregated quality evaluation metrics and failure category breakdown."""

    total_feedback: int = Field(description="Total feedback submissions recorded")
    positive_count: int = Field(description="Total positive (thumbs-up) ratings")
    negative_count: int = Field(description="Total negative (thumbs-down) ratings")
    satisfaction_rate: float = Field(description="Ratio of positive feedback (0.0 - 1.0)")
    failure_categories: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of negative feedback occurrences by failure reason tag",
    )
    pending_reviews_count: int = Field(description="Number of negative feedback items pending triage")
    in_review_count: int = Field(description="Number of feedback items currently being investigated")
    resolved_reviews_count: int = Field(description="Number of feedback items marked resolved")

