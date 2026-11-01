"""Schemas for RAG question answering, grounded citations, and prompt generation."""

import uuid
from typing import List, Literal, Optional
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


class EvidenceDiagnostics(BaseModel):
    """Qualitative diagnostics regarding retrieval relevance, faithfulness, and citation integrity."""

    retrieval_relevance: Literal["high", "medium", "low"] = Field(
        description="Qualitative assessment of retrieval context relevance"
    )
    faithfulness_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Ratio of answer claims directly grounded in retrieved context",
    )
    supported_claims_count: int = Field(description="Count of verified grounded claims in answer")
    total_claims_count: int = Field(description="Total factual claims extracted from answer")
    conflicts_detected: bool = Field(
        default=False,
        description="Whether contradictory statements were detected across retrieved active sources",
    )
    citation_integrity_verified: bool = Field(
        default=True,
        description="Whether all generated citations resolve to active authorized documents in context",
    )
    unsupported_claims: List[str] = Field(
        default_factory=list,
        description="List of answer claims that lacked sufficient evidence in retrieved chunks",
    )


class ChatQueryResponse(BaseModel):
    """Fully grounded RAG assistant answer with citations and qualitative evidence status."""

    query: str
    answer: str
    citations: List[Citation]
    retrieved_chunks: List[RetrievedChunk]
    abstained: bool = Field(description="True if documentation was insufficient to answer")
    evidence_level: Literal["strong", "limited", "insufficient"] = Field(
        default="strong",
        description="Qualitative evidence label (Strong, Limited, or Insufficient)",
    )
    abstention_reason: Optional[str] = Field(
        default=None,
        description="Explicit categorization of abstention cause if documentation is insufficient",
    )
    evidence_diagnostics: Optional[EvidenceDiagnostics] = Field(
        default=None,
        description="Explainable evidence verification breakdown",
    )
    execution_time_ms: float
