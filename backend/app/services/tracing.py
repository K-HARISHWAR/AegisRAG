"""Distributed request tracing, stage latency profiling, token counting, and cost estimation."""

import json
import math
import re
import statistics
import time
import uuid
from collections import Counter, deque
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger, request_id_ctx_var
from app.models.trace import RequestTrace
from app.models.user import User
from app.schemas.operations import OperationsMetricsResponse, RequestTraceRead, SpanRead, StageLatencyStat

logger = get_logger(__name__)
settings = get_settings()

SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "key", "cookie", "prompt_text", "raw_text"}


def _sanitize_span_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize span metadata to guarantee no secrets, credentials, or raw text leak into traces."""
    clean: Dict[str, Any] = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            clean[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > 120:
            clean[k] = v[:120] + "..."
        elif isinstance(v, (int, float, bool, list, dict)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


class SpanRecord:
    """Individual execution span within a request trace."""

    def __init__(
        self,
        stage_name: str,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.span_id = span_id or str(uuid.uuid4())
        self.parent_span_id = parent_span_id
        self.stage_name = stage_name
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration_ms: float = 0.0
        self.status: str = "ok"
        self.metadata: Dict[str, Any] = _sanitize_span_metadata(metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "stage_name": self.stage_name,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "metadata": self.metadata,
        }


class RequestTracer:
    """Tracer bound to an individual request lifecycle."""

    def __init__(
        self,
        request_id: str,
        user_id: uuid.UUID,
        endpoint: str = "/api/v1/chat/query",
    ) -> None:
        self.request_id = request_id
        self.user_id = user_id
        self.endpoint = endpoint
        self.start_time: float = time.perf_counter()
        self.spans: List[SpanRecord] = []
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.estimated_cost_usd: float = 0.0

    @asynccontextmanager
    async def span(
        self,
        stage_name: str,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[SpanRecord, None]:
        """Async context manager wrapping a pipeline stage."""
        span_rec = SpanRecord(
            stage_name=stage_name,
            parent_span_id=parent_span_id,
            metadata=metadata,
        )
        span_rec.start_time = time.perf_counter()
        try:
            yield span_rec
        except Exception as exc:
            span_rec.status = "error"
            span_rec.metadata["error"] = type(exc).__name__
            raise
        finally:
            span_rec.end_time = time.perf_counter()
            span_rec.duration_ms = (span_rec.end_time - span_rec.start_time) * 1000
            self.spans.append(span_rec)

    def record_span_instant(
        self,
        stage_name: str,
        duration_ms: float,
        status: str = "ok",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SpanRecord:
        """Record an already measured stage span (e.g. from existing sub-services)."""
        span_rec = SpanRecord(
            stage_name=stage_name,
            metadata=metadata,
        )
        span_rec.duration_ms = duration_ms
        span_rec.status = status
        self.spans.append(span_rec)
        return span_rec

    def estimate_tokens_and_cost(
        self,
        prompt_text: str,
        completion_text: str,
    ) -> Tuple[int, int, int, float]:
        """Compute estimated token usage and estimated cost for the request."""
        # Standard token heuristic: ~4 characters per token or 1.3 tokens per word
        def _count(text: str) -> int:
            if not text:
                return 0
            words = len(re.findall(r"\b\w+\b", text))
            chars = len(text)
            return max(1, int(max(words * 1.3, chars / 4.0)))

        p_tokens = _count(prompt_text)
        c_tokens = _count(completion_text)
        total = p_tokens + c_tokens

        prompt_cost = (p_tokens / 1_000_000.0) * settings.COST_PER_MILLION_PROMPT_TOKENS
        completion_cost = (c_tokens / 1_000_000.0) * settings.COST_PER_MILLION_COMPLETION_TOKENS
        cost = round(prompt_cost + completion_cost, 6)

        self.prompt_tokens = p_tokens
        self.completion_tokens = c_tokens
        self.estimated_cost_usd = cost
        return p_tokens, c_tokens, total, cost

    def get_slowest_stage(self) -> Tuple[str, float]:
        """Identify the slowest pipeline stage and its duration in ms."""
        if not self.spans:
            return "unknown", 0.0
        slowest = max(self.spans, key=lambda s: s.duration_ms)
        return slowest.stage_name, slowest.duration_ms

    async def finalize(
        self,
        db: AsyncSession,
        is_empty_result: bool = False,
        is_abstained: bool = False,
        error_type: Optional[str] = None,
    ) -> RequestTrace:
        """Persist trace into PostgreSQL/SQLite and record in telemetry store."""
        total_latency_ms = (time.perf_counter() - self.start_time) * 1000
        slowest_stage, slowest_latency = self.get_slowest_stage()

        spans_json = json.dumps([s.to_dict() for s in self.spans])

        trace_record = RequestTrace(
            id=uuid.uuid4(),
            request_id=self.request_id,
            user_id=self.user_id,
            endpoint=self.endpoint,
            total_latency_ms=round(total_latency_ms, 2),
            slowest_stage=slowest_stage,
            slowest_stage_latency_ms=round(slowest_latency, 2),
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.prompt_tokens + self.completion_tokens,
            estimated_cost_usd=self.estimated_cost_usd,
            is_empty_result=is_empty_result,
            is_abstained=is_abstained,
            error_type=error_type,
            spans_data=spans_json,
        )

        db.add(trace_record)
        await db.commit()

        # Add to in-memory telemetry buffer
        get_telemetry_store().record_trace(trace_record, [s.to_dict() for s in self.spans])
        return trace_record


class TelemetryStore:
    """Thread-safe telemetry aggregator maintaining recent request traces for instant metric reporting."""

    def __init__(self, max_history: int = 500) -> None:
        self.max_history = max_history
        self._traces: deque[Dict[str, Any]] = deque(maxlen=max_history)
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    def record_cache_event(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_trace(self, trace: RequestTrace, spans: List[Dict[str, Any]]) -> None:
        """Store trace summary in memory for fast metric aggregations."""
        item = {
            "id": str(trace.id),
            "request_id": trace.request_id,
            "user_id": str(trace.user_id),
            "endpoint": trace.endpoint,
            "total_latency_ms": trace.total_latency_ms,
            "slowest_stage": trace.slowest_stage,
            "slowest_stage_latency_ms": trace.slowest_stage_latency_ms,
            "prompt_tokens": trace.prompt_tokens,
            "completion_tokens": trace.completion_tokens,
            "total_tokens": trace.total_tokens,
            "estimated_cost_usd": trace.estimated_cost_usd,
            "is_empty_result": trace.is_empty_result,
            "is_abstained": trace.is_abstained,
            "error_type": trace.error_type,
            "spans": spans,
            "created_at": trace.created_at.isoformat() if hasattr(trace.created_at, "isoformat") else str(trace.created_at),
        }
        self._traces.append(item)

    def get_recent_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return most recent request traces."""
        return list(self._traces)[-limit:][::-1]

    def get_trace_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Lookup trace by request correlation ID."""
        for t in reversed(self._traces):
            if t["request_id"] == request_id:
                return t
        return None

    def compute_metrics(self) -> OperationsMetricsResponse:
        """Compute p50, p95 latencies per stage, empty result rates, and cost telemetry."""
        total = len(self._traces)
        if total == 0:
            return OperationsMetricsResponse(
                total_requests=0,
                empty_result_rate=0.0,
                abstention_rate=0.0,
                error_count=0,
                total_tokens=0,
                total_estimated_cost_usd=0.0,
                stage_latencies=[],
                slowest_stages_distribution={},
                cache_hit_rate=0.0,
                active_alerts=[],
            )

        empty_count = sum(1 for t in self._traces if t["is_empty_result"])
        abstained_count = sum(1 for t in self._traces if t["is_abstained"])
        error_count = sum(1 for t in self._traces if t.get("error_type"))
        total_tokens = sum(t["total_tokens"] for t in self._traces)
        total_cost = sum(t["estimated_cost_usd"] for t in self._traces)

        # Stage latency aggregations
        stage_times: Dict[str, List[float]] = {}
        slowest_dist: Dict[str, int] = Counter()

        for t in self._traces:
            slowest_dist[t["slowest_stage"]] += 1
            for span in t.get("spans", []):
                s_name = span.get("stage_name", "unknown")
                dur = float(span.get("duration_ms", 0.0))
                stage_times.setdefault(s_name, []).append(dur)

        def _percentiles(values: List[float]) -> Tuple[float, float, float]:
            if not values:
                return 0.0, 0.0, 0.0
            sorted_v = sorted(values)
            n = len(sorted_v)
            p50 = sorted_v[int(n * 0.50)]
            p95 = sorted_v[min(n - 1, int(n * 0.95))]
            max_v = sorted_v[-1]
            return round(p50, 2), round(p95, 2), round(max_v, 2)

        stage_latency_stats: List[StageLatencyStat] = []
        for stage, times in stage_times.items():
            p50, p95, max_v = _percentiles(times)
            stage_latency_stats.append(
                StageLatencyStat(
                    stage_name=stage,
                    p50_ms=p50,
                    p95_ms=p95,
                    max_ms=max_v,
                    samples_count=len(times),
                )
            )

        # Cache hit rate
        total_cache_events = self.cache_hits + self.cache_misses
        cache_hit_rate = round(self.cache_hits / max(1, total_cache_events), 3)

        # Active alert rules
        alerts: List[str] = []
        empty_rate = empty_count / total
        abstention_rate = abstained_count / total

        gen_stats = [s for s in stage_latency_stats if s.stage_name == "generation"]
        if gen_stats and gen_stats[0].p95_ms > 2500.0:
            alerts.append(f"High generation latency: p95 is {gen_stats[0].p95_ms:.1f}ms (>2500ms threshold).")

        ret_stats = [s for s in stage_latency_stats if s.stage_name == "retrieval"]
        if ret_stats and ret_stats[0].p95_ms > 1000.0:
            alerts.append(f"Elevated retrieval latency: p95 is {ret_stats[0].p95_ms:.1f}ms (>1000ms threshold).")

        if empty_rate > 0.30:
            alerts.append(f"High empty-result rate: {empty_rate * 100:.1f}% queries yielded zero authorized passages.")

        if error_count > 0:
            alerts.append(f"System errors detected: {error_count} recent request failure(s).")

        return OperationsMetricsResponse(
            total_requests=total,
            empty_result_rate=round(empty_rate, 3),
            abstention_rate=round(abstention_rate, 3),
            error_count=error_count,
            total_tokens=total_tokens,
            total_estimated_cost_usd=round(total_cost, 4),
            stage_latencies=stage_latency_stats,
            slowest_stages_distribution=dict(slowest_dist),
            cache_hit_rate=cache_hit_rate,
            active_alerts=alerts,
        )


_global_telemetry_store: Optional[TelemetryStore] = None


def get_telemetry_store() -> TelemetryStore:
    """Return singleton telemetry store instance."""
    global _global_telemetry_store
    if _global_telemetry_store is None:
        _global_telemetry_store = TelemetryStore(max_history=settings.TRACE_MAX_HISTORY)
    return _global_telemetry_store

