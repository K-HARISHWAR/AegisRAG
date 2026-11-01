"""Schemas for RAG question answering, grounded citations, and prompt generation."""

import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.retrieval import RetrievedChunk


class ChatQueryRequest(BaseModel):
    """User question submission request schema."""

    query: str = Field(min_length=1, max_length=1000, description="Natural language question")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context passages to retrieve")
    hybrid: bool = Field(default=True, description="Enable hybrid dense + sparse retrieval")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0, description="Sampling temperature for LLM")
    mode: Optional[str] = Field(default=None, description="Retrieval mode override ('vector' or 'hybrid')")
    rerank: Optional[bool] = Field(default=None, description="Flag to enable/disable reranker")


class Citation(BaseModel):
    """Grounded source citation referencing verified document location."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID = Field(description="PostgreSQL document identifier")
    document_title: str = Field(description="Official document title")
    document_version: int = Field(default=1, description="Document revision version")
    location: str = Field(description="Exact location citation (e.g. 'Page 2', 'Paragraph 3')")
    content_hash: str = Field(description="SHA-256 chunk hash for provenance integrity")
    snippet: str = Field(description="Exemplar passage quote supporting the answer")


class ChatQueryResponse(BaseModel):
    """Fully grounded RAG assistant answer with citations and abstention status."""

    query: str
    answer: str
    citations: List[Citation]
    retrieved_chunks: List[RetrievedChunk]
    abstained: bool = Field(description="True if documentation was insufficient to answer")
    execution_time_ms: float
