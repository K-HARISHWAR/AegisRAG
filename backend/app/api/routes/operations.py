"""Operations, telemetry, request traces, and quota monitoring endpoints."""

import json
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user, get_db
from app.models.trace import RequestTrace
from app.models.user import User
from app.schemas.operations import (
    OperationsMetricsResponse,
    QuotaStatusResponse,
    RequestTraceRead,
    SpanRead,
)
from app.services.cache import get_safe_cache
from app.services.rate_limit import get_rate_limiter
from app.services.tracing import get_telemetry_store

router = APIRouter(prefix="/operations", tags=["Operations & Observability"])


@router.get(
    "/metrics",
    response_model=OperationsMetricsResponse,
    summary="Get operational and cost telemetry metrics",
    description="Returns p50/p95 stage latencies, slowest stage distribution, token and cost accounting, cache hit rate, and active system alerts.",
)
async def get_operations_metrics(
    admin_user: Annotated[User, Depends(get_current_admin)],
) -> OperationsMetricsResponse:
    """Retrieve system performance, latency, and cost telemetry."""
    store = get_telemetry_store()
    return store.compute_metrics()


@router.get(
    "/traces",
    response_model=List[RequestTraceRead],
    summary="List recent request traces",
    description="Returns recent request traces with stage latency breakdowns and slowest stage identification.",
)
async def list_recent_traces(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum traces to return")] = 50,
) -> List[RequestTraceRead]:
    """Retrieve recent distributed request traces from the database."""
    stmt = select(RequestTrace).order_by(desc(RequestTrace.created_at)).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()

    results: List[RequestTraceRead] = []
    for r in records:
        spans: List[SpanRead] = []
        if r.spans_data:
            try:
                raw_spans = json.loads(r.spans_data)
                spans = [SpanRead(**s) for s in raw_spans]
            except Exception:
                pass

        results.append(
            RequestTraceRead(
                id=r.id,
                request_id=r.request_id,
                user_id=r.user_id,
                endpoint=r.endpoint,
                total_latency_ms=r.total_latency_ms,
                slowest_stage=r.slowest_stage,
                slowest_stage_latency_ms=r.slowest_stage_latency_ms,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                total_tokens=r.total_tokens,
                estimated_cost_usd=r.estimated_cost_usd,
                is_empty_result=r.is_empty_result,
                is_abstained=r.is_abstained,
                error_type=r.error_type,
                spans=spans,
                created_at=r.created_at,
            )
        )
    return results


@router.get(
    "/traces/{request_id}",
    response_model=RequestTraceRead,
    summary="Get request trace by ID",
    description="Retrieve execution trace and waterfall spans for an individual request correlation ID.",
)
async def get_request_trace(
    request_id: str,
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestTraceRead:
    """Retrieve a single request trace by its correlation ID."""
    stmt = select(RequestTrace).where(RequestTrace.request_id == request_id)
    res = await db.execute(stmt)
    record = res.scalars().first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request trace with correlation ID '{request_id}' not found",
        )

    spans: List[SpanRead] = []
    if record.spans_data:
        try:
            raw_spans = json.loads(record.spans_data)
            spans = [SpanRead(**s) for s in raw_spans]
        except Exception:
            pass

    return RequestTraceRead(
        id=record.id,
        request_id=record.request_id,
        user_id=record.user_id,
        endpoint=record.endpoint,
        total_latency_ms=record.total_latency_ms,
        slowest_stage=record.slowest_stage,
        slowest_stage_latency_ms=record.slowest_stage_latency_ms,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        total_tokens=record.total_tokens,
        estimated_cost_usd=record.estimated_cost_usd,
        is_empty_result=record.is_empty_result,
        is_abstained=record.is_abstained,
        error_type=record.error_type,
        spans=spans,
        created_at=record.created_at,
    )


@router.get(
    "/quotas",
    response_model=QuotaStatusResponse,
    summary="Get caller rate limit and daily quota status",
    description="Returns current sliding-window minute requests remaining and daily quota usage for the authenticated user.",
)
async def get_quota_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> QuotaStatusResponse:
    """Retrieve caller quota and rate limit status."""
    rate_limiter = get_rate_limiter()
    return rate_limiter.get_quota_status(current_user)


@router.post(
    "/cache/clear",
    summary="Purge safe scoped cache",
    description="Purges all cached generation responses across all scopes. Requires admin privileges.",
)
async def clear_safe_cache(
    admin_user: Annotated[User, Depends(get_current_admin)],
) -> Dict[str, Any]:
    """Purge cached responses."""
    cache = get_safe_cache()
    cleared = cache.clear()
    return {
        "cleared_entries": cleared,
        "message": f"Successfully cleared {cleared} entries from safe scoped cache.",
    }
