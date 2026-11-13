"""Pydantic schemas for server-side dynamic feature flags."""

from typing import Optional
from pydantic import BaseModel, Field


class FeatureFlagsState(BaseModel):
    """Current state of runtime server-side feature flags."""

    enable_hybrid_retrieval: bool = Field(default=True, description="Enable hybrid dense+sparse BM25 retrieval and reciprocal rank fusion")
    enable_reranking: bool = Field(default=True, description="Enable cross-encoder candidate passage reranking")
    enable_evidence_validation: bool = Field(default=True, description="Enable post-generation evidence and claim validation")
    enable_scoped_cache: bool = Field(default=True, description="Enable safe policy-scoped response caching")
    enable_rate_limiting: bool = Field(default=True, description="Enable identity-aware sliding-window rate limiting and quotas")
    enable_tracing: bool = Field(default=True, description="Enable distributed request tracing and latency profiling")
    enable_workflows: bool = Field(default=True, description="Enable read-only knowledge workflows (diff, summarize, extract)")
    enable_ocr: bool = Field(default=True, description="Enable OCR text extraction for scanned documents")


class FeatureFlagsUpdate(BaseModel):
    """Payload to update runtime server-side feature flags."""

    enable_hybrid_retrieval: Optional[bool] = None
    enable_reranking: Optional[bool] = None
    enable_evidence_validation: Optional[bool] = None
    enable_scoped_cache: Optional[bool] = None
    enable_rate_limiting: Optional[bool] = None
    enable_tracing: Optional[bool] = None
    enable_workflows: Optional[bool] = None
    enable_ocr: Optional[bool] = None

