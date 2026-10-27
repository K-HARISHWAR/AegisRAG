"""Health check endpoints for liveness and readiness probes."""

from datetime import datetime, timezone
import os
from pathlib import Path
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


class LivenessResponse(BaseModel):
    """Response model for liveness check."""

    status: str = "live"
    timestamp: str


class ReadinessResponse(BaseModel):
    """Response model for readiness check (sanitized, zero-leakage)."""

    status: str
    environment: str
    checks: dict[str, str]
    timestamp: str


@router.get(
    "/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Indicates whether the application process is running and accepting HTTP requests.",
)
async def health_live() -> LivenessResponse:
    """Liveness probe - always returns 200 when server is alive."""
    return LivenessResponse(
        status="live",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Indicates whether the application dependencies are ready without leaking credentials or paths.",
)
async def health_ready(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Readiness probe - checks configuration and storage without exposing paths or secrets."""
    checks: dict[str, str] = {}
    is_ready = True

    # 1. Configuration check
    if settings.SECRET_KEY and settings.PROJECT_NAME:
        checks["configuration"] = "healthy"
    else:
        checks["configuration"] = "unhealthy"
        is_ready = False

    # 2. Storage directory check
    try:
        storage_path = Path(settings.LOCAL_STORAGE_DIR)
        storage_path.mkdir(parents=True, exist_ok=True)
        if os.access(storage_path, os.W_OK):
            checks["storage"] = "healthy"
        else:
            checks["storage"] = "unhealthy"
            is_ready = False
    except Exception as exc:
        logger.error("Storage readiness check failed: %s", str(exc))
        checks["storage"] = "unhealthy"
        is_ready = False

    # 3. Database connectivity check (zero-leakage)
    try:
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", str(exc))
        checks["database"] = "unhealthy"
        if settings.ENVIRONMENT == "production":
            is_ready = False

    # 4. Vector store readiness check
    try:
        from app.services.vector_store import get_vector_store
        vstore = get_vector_store()
        if vstore.health_check():
            checks["vector_store"] = "healthy"
        else:
            checks["vector_store"] = "unhealthy"
            is_ready = False
    except Exception as exc:
        logger.warning("Vector store readiness check failed: %s", str(exc))
        checks["vector_store"] = "unhealthy"
        is_ready = False

    overall_status = "ready" if is_ready else "unhealthy"
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        checks=checks,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
