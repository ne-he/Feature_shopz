"""FastAPI application entry point for the feature-serving layer.

The app is built by a factory. Its lifespan creates a single SQLAlchemy
engine and Redis client (stored on ``app.state`` for the DI providers in
``dependencies.py``) and disposes them on shutdown. Importing the six
feature modules populates the global REGISTRY as a side effect, so the
metadata endpoint has a catalog to serve.

A timing middleware logs every request and stamps an ``X-Process-Time-Ms``
header; exception handlers translate validation failures and unexpected
store errors into structured JSON responses (M3.3, M3.8, M3.9).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from src.api import API_VERSION
from src.api.routes import features, health
from src.config import settings
from src.features import (  # noqa: F401 -- imported to populate REGISTRY on load
    behavior,
    demographics,
    discount,
    engagement,
    rfm,
    temporal,
)
from src.storage.online_store import get_redis_client

PROCESS_TIME_HEADER: str = "X-Process-Time-Ms"

# Permissive CORS for local MVP so the static frontend can call the API from
# file:// or a different port. Tighten to explicit origins for any real deploy.
_CORS_ORIGINS: list[str] = ["*"]

# Static showcase frontend (Claude design). Served at "/" when present so a
# single `uvicorn` command serves both the page and the API on one origin.
_FRONTEND_DIR: Path = Path(__file__).parents[2] / "frontend" / "MLv2"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared store clients on startup; release them on shutdown.

    Args:
        app: The FastAPI application whose ``state`` holds the clients.

    Yields:
        Control to the running application.
    """
    engine = create_engine(settings.postgres_url, pool_pre_ping=True)
    redis_client = get_redis_client()
    app.state.engine = engine
    app.state.redis = redis_client
    logger.info("API startup: offline + online store clients ready")
    try:
        yield
    finally:
        engine.dispose()
        redis_client.close()
        logger.info("API shutdown: store connections released")


def _register_middleware(app: FastAPI) -> None:
    """Attach the request-timing + logging middleware (M3.9)."""

    @app.middleware("http")
    async def add_timing_header(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[PROCESS_TIME_HEADER] = f"{elapsed_ms:.2f}"
        logger.info(
            "{} {} -> {} ({:.2f}ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers mapping validation + store errors to JSON (M3.10)."""

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Validation error on {}: {}", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "detail": exc.errors()},
        )

    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(RedisError)
    async def on_store_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Store error on {}: {}", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "store_unavailable", "detail": "A backing store is unavailable"},
        )


def _mount_frontend(app: FastAPI) -> None:
    """Serve the static showcase frontend at "/" when the directory exists.

    Mounted last so the API routes (and /docs) registered earlier always win;
    only unmatched paths fall through to the static files.
    """
    if _FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
        logger.info("Serving frontend from {}", _FRONTEND_DIR)
    else:
        logger.warning("Frontend dir not found; static mount skipped: {}", _FRONTEND_DIR)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        A FastAPI app with CORS, routers, middleware, exception handlers, and
        the static frontend mount wired.
    """
    app = FastAPI(
        title="Feature Store MVP API",
        version=API_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=[PROCESS_TIME_HEADER],
    )
    _register_middleware(app)
    _register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(features.router)
    _mount_frontend(app)
    return app


app = create_app()
