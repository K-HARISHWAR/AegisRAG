"""Pydantic schemas for Observability, Request Tracing, Performance Metrics, and Cost Controls."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SpanRead(BaseModel):
    """Execution span capturing stage latency and metadata."""

    span_id: str
    parent_span_id: Optional[str] = None
    stage_name: str = Field(description="Stage name (auth, policy, retrieval, reranking, generation, citation_validation, cache, ocr)")
    duration_ms: float = Field(description="Execution latency in milliseconds")
    status: str = Field(description="Span status: ok, error, timeout, hit, miss")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized, non-sensitive execution details")


class RequestTraceRead(BaseModel):
    """Full request trace with waterfall spans and cost telemetry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: str
    user_id: uuid.UUID
    endpoint: str
    total_latency_ms: float
    slowest_stage: str
    slowest_stage_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    is_empty_result: bool
    is_abstained: bool
    error_type: Optional[str] = None
    spans: List[SpanRead] = Field(default_factory=list)
    created_at: datetime


class StageLatencyStat(BaseModel):
    """Latency distribution for a discrete pipeline stage."""

    stage_name: str
    p50_ms: float
    p95_ms: float
    max_ms: float
    samples_count: int


class OperationsMetricsResponse(BaseModel):
    """Aggregated operations, performance, cost, and health telemetry."""

    total_requests: int
    empty_result_rate: float = Field(description="Fraction of queries that yielded 0 chunks (0.0 to 1.0)")
    abstention_rate: float = Field(description="Fraction of queries resulting in responsible abstention")
    error_count: int
    total_tokens: int
    total_estimated_cost_usd: float
    stage_latencies: List[StageLatencyStat]
    slowest_stages_distribution: Dict[str, int]
    cache_hit_rate: float
    active_alerts: List[str] = Field(default_factory=list)


class QuotaStatusResponse(BaseModel):
    """Caller identity rate limits and daily quota telemetry."""

    user_id: uuid.UUID
    email: str
    role: str
    rate_limit_per_minute: int
    requests_remaining_minute: int
    daily_quota: int
    daily_queries_used: int
    daily_queries_remaining: int
    reset_seconds: int

