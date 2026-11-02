"""Pydantic schemas for conversation threads, follow-up messages, and bookmarks."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.generation import Citation


class ThreadCreate(BaseModel):
    """Schema to initialize a new conversation thread."""

    title: Optional[str] = Field(
        default="New Conversation",
        max_length=255,
        description="Optional human-readable title for the thread",
    )


class ThreadUpdate(BaseModel):
    """Schema for renaming or archiving a conversation thread."""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated conversation title",
    )
    is_archived: Optional[bool] = Field(
        default=None,
        description="Whether the thread is archived",
    )


class ThreadMessageCreate(BaseModel):
    """Schema for posting a new user query or contextual follow-up within a thread."""

    query: str = Field(
        min_length=1,
        max_length=4000,
        description="User message or follow-up question",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Candidate retrieval passages count",
    )
    hybrid: bool = Field(
        default=True,
        description="Whether to use hybrid sparse + dense retrieval",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM generation temperature",
    )


class ThreadMessageRead(BaseModel):
    """Schema for returning an interaction turn in a thread."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    sender: Literal["user", "assistant"]
    text: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    abstained: bool = False
    evidence_level: Optional[str] = None
    abstention_reason: Optional[str] = None
    query_id: Optional[uuid.UUID] = None
    created_at: datetime


class ThreadBookmarkCreate(BaseModel):
    """Schema for user-saving a verified citation snippet."""

    document_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=100)
    snippet: str = Field(min_length=1)
    content_hash: str = Field(min_length=8, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ThreadBookmarkRead(BaseModel):
    """Schema for returning a user-saved snippet bookmark."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    user_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    location: str
    snippet: str
    content_hash: str
    notes: Optional[str] = None
    created_at: datetime


class ThreadSummaryRead(BaseModel):
    """Lightweight summary of a conversation thread for sidebar listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    is_archived: bool
    message_count: int
    created_at: datetime
    updated_at: datetime


class ThreadRead(BaseModel):
    """Full conversation thread representation with interaction turns and bookmarks."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    messages: List[ThreadMessageRead] = Field(default_factory=list)
    bookmarks: List[ThreadBookmarkRead] = Field(default_factory=list)
