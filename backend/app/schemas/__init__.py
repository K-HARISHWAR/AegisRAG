"""Pydantic schemas export."""

from app.schemas.auth import LoginRequest, Token, TokenPayload
from app.schemas.user import UserRead, UserCreate, RoleRead, DepartmentRead
from app.schemas.document import (
    DocumentRead,
    DocumentCreate,
    DocumentGrantRead,
    DocumentGrantCreate,
    DocumentPassageRead,
    DocumentContentResponse,
    DocumentUploadResponse,
    DocumentHistoryResponse,
    DocumentRevisionHistoryItem,
    ExtractionQualityReport,
    DocumentExtractionPreviewResponse,
)
from app.schemas.audit import AuditEventRead
from app.schemas.chunk import Chunk, DocumentChunkRead, SearchResult
from app.schemas.generation import ChatQueryRequest, ChatQueryResponse, Citation
from app.schemas.retrieval import RetrievalQuery, RetrievalResponse, RetrievedChunk
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackReviewUpdateRequest,
    FeedbackResponse,
    FeedbackStatsResponse,
)
from app.schemas.thread import (
    ThreadCreate,
    ThreadUpdate,
    ThreadRead,
    ThreadSummaryRead,
    ThreadMessageCreate,
    ThreadMessageRead,
    ThreadBookmarkCreate,
    ThreadBookmarkRead,
)

__all__ = [
    "LoginRequest",
    "Token",
    "TokenPayload",
    "UserRead",
    "UserCreate",
    "RoleRead",
    "DepartmentRead",
    "DocumentRead",
    "DocumentCreate",
    "DocumentGrantRead",
    "DocumentGrantCreate",
    "DocumentPassageRead",
    "DocumentContentResponse",
    "DocumentUploadResponse",
    "DocumentHistoryResponse",
    "DocumentRevisionHistoryItem",
    "ExtractionQualityReport",
    "DocumentExtractionPreviewResponse",
    "AuditEventRead",
    "Chunk",
    "SearchResult",
    "DocumentChunkRead",
    "RetrievalQuery",
    "RetrievedChunk",
    "RetrievalResponse",
    "ChatQueryRequest",
    "Citation",
    "ChatQueryResponse",
    "FeedbackCreateRequest",
    "FeedbackReviewUpdateRequest",
    "FeedbackResponse",
    "FeedbackStatsResponse",
    "ThreadCreate",
    "ThreadUpdate",
    "ThreadRead",
    "ThreadSummaryRead",
    "ThreadMessageCreate",
    "ThreadMessageRead",
    "ThreadBookmarkCreate",
    "ThreadBookmarkRead",
]
