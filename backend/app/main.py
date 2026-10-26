"""FastAPI application factory and entry point."""

import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import admin, auth, documents, health
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import get_logger, request_id_ctx_var, setup_logging

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to each request context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Honor client-supplied X-Request-ID if provided, else generate a UUID4
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Bind to context variable for logging
        token = request_id_ctx_var.set(request_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            return response
        finally:
            request_id_ctx_var.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory."""
    if settings is None:
        settings = get_settings()

    # Initialize structured logging
    setup_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="AegisRAG Enterprise Assistant - Server-Verified RBAC Document Assistant API",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
    )

    # 1. Register Request ID Middleware
    app.add_middleware(RequestIdMiddleware)

    # 2. Register CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # 3. Register Global Error Handlers (sanitized client responses)
    register_error_handlers(app)

    # 4. Include Routers
    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.API_V1_STR)
    app.include_router(documents.router, prefix=settings.API_V1_STR)
    app.include_router(admin.router, prefix=settings.API_V1_STR)

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """Root endpoint returning service identity."""
        return {
            "name": settings.PROJECT_NAME,
            "version": "0.1.0",
            "status": "online",
        }

    return app


# Default application instance for Uvicorn
app = create_app()
