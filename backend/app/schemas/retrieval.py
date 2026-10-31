"""Retrieval request and response schemas with granular citation metadata."""

import uuid
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class RetrievalQuery(BaseModel):
    """Retrieval search query request schema."""

    query: str = Field(min_length=1, max_length=1000, description="Natural language search or question text")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of candidate chunks to retrieve")
    hybrid: bool = Field(default=True, description="Enable hybrid dense semantic + BM25 sparse keyword search")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance score threshold (0.0 to 1.0)")
    mode: Optional[Literal["vector", "hybrid"]] = Field(default=None, description="Explicit retrieval mode override ('vector' or 'hybrid')")
    rerank: Optional[bool] = Field(default=None, description="Explicit flag to enable/disable reranker on authorized candidates")


class RetrievedChunk(BaseModel):
    """Server-verified retrieved chunk with exact source citation metadata."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str = Field(description="Unique deterministic chunk identifier")
    document_id: uuid.UUID = Field(description="PostgreSQL verified document identifier")
    document_title: str = Field(description="Trusted document title from PostgreSQL")
    document_version: int = Field(default=1, description="Document revision version")
    chunk_index: int = Field(description="1-indexed sequence within document")
    text: str = Field(description="Extracted chunk text content")
    location: str = Field(description="Granular source coordinate (e.g. 'Page 2', 'Paragraph 4', 'Sheet: Summary!Row 12')")
    department_id: uuid.UUID = Field(description="Owning department identifier")
    is_confidential: bool = Field(description="Confidentiality flag")
    dense_score: float = Field(description="Dense semantic similarity score (0.0 to 1.0)")
    sparse_score: float = Field(description="Sparse BM25 score (0.0 to 1.0 normalized)")
    combined_score: float = Field(description="Fused hybrid relevance score (0.0 to 1.0)")
    content_hash: str = Field(description="SHA-256 deduplication checksum")
    channel: str = Field(default="both", description="Origin channel: 'dense', 'sparse', or 'both'")
    dense_rank: Optional[int] = Field(default=None, description="1-indexed rank from dense vector retrieval channel")
    sparse_rank: Optional[int] = Field(default=None, description="1-indexed rank from sparse lexical BM25 channel")
    rerank_score: Optional[float] = Field(default=None, description="Relevance score assigned by neural/cross-encoder reranker")
    rerank_rank: Optional[int] = Field(default=None, description="1-indexed rank after reranking")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional passage metadata")


class RetrievalDiagnostics(BaseModel):
    """Internal retrieval execution diagnostics for explainability and auditing."""

    mode: str = Field(description="Active retrieval mode: 'vector' or 'hybrid'")
    channels_used: List[str] = Field(description="Channels executed, e.g. ['dense', 'sparse']")
    dense_candidates_count: int = Field(description="Raw candidates retrieved from dense vector channel")
    sparse_candidates_count: int = Field(description="Raw candidates retrieved from sparse lexical channel")
    fused_candidates_count: int = Field(description="Unique candidates merged via RRF")
    post_validation_count: int = Field(description="Candidates surviving Stage 2 PostgreSQL revalidation")
    reranked: bool = Field(description="Whether reranking was executed on the candidates")
    reranker_latency_ms: Optional[float] = Field(default=None, description="Latency of reranking step in milliseconds")
    authorized_documents_count: int = Field(description="Count of documents authorized in Stage 1")


class RetrievalResponse(BaseModel):
    """Structured response containing verified retrieved chunks and retrieval metadata."""

    query: str
    chunks: List[RetrievedChunk]
    total_candidates_found: int
    authorized_documents_count: int
    execution_time_ms: float
    diagnostics: Optional[RetrievalDiagnostics] = Field(default=None, description="Internal retrieval execution diagnostics")
