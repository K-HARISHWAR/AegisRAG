"""Chunk data structures and vector search result representations."""

import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    """Deterministic document chunk with granular location provenance and RBAC metadata."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str = Field(description="Deterministic chunk identifier (doc_id + index + content_hash)")
    document_id: uuid.UUID
    document_version: int = 1
    chunk_index: int
    text: str
    location: str = Field(description="Source provenance (e.g. 'Page 2', 'Paragraph 4', 'Sheet: Summary!Row 12')")
    department_id: uuid.UUID
    is_confidential: bool = False
    content_hash: str = Field(description="SHA-256 hash of text and provenance for deduplication")
    metadata: dict[str, Any] = {}


class SearchResult(BaseModel):
    """Retrieved candidate passage from vector search."""

    chunk_id: str
    document_id: uuid.UUID
    document_version: int
    chunk_index: int
    text: str
    location: str
    department_id: uuid.UUID
    is_confidential: bool
    similarity_score: float
    metadata: dict[str, Any] = {}


class DocumentChunkRead(BaseModel):
    """Public chunk inspection schema."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    chunk_index: int
    location: str
    text: str
    content_hash: str
