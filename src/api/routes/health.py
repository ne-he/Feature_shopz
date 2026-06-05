"""Health-check endpoint for the feature-serving API (PRD § 12).

Probes both backing stores. Returns 200 with ``status="healthy"`` when
PostgreSQL and Redis both respond, or 503 with ``status="unhealthy"`` and
per-store detail when either is unreachable (M3.6, M3.9).
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from loguru import logger
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.api import API_VERSION
from src.api.dependencies import EngineDep, RedisDep
from src.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


def _check_postgres(engine: Engine) -> str:
    """Probe PostgreSQL with a trivial query; return 'ok' or 'unavailable'."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Postgres health check failed: {}", exc)
        return "unavailable"
    return "ok"


def _check_redis(redis_client: Redis) -> str:
    """Ping Redis; return 'ok' or 'unavailable'."""
    try:
        redis_client.ping()
    except RedisError as exc:
        logger.warning("Redis health check failed: {}", exc)
        return "unavailable"
    return "ok"


@router.get("/health", response_model=HealthResponse)
def health(
    engine: EngineDep,
    redis_client: RedisDep,
    response: Response,
) -> HealthResponse:
    """Report service health by probing PostgreSQL and Redis.

    Args:
        engine: Injected SQLAlchemy engine for the offline store.
        redis_client: Injected Redis client for the online store.
        response: Mutable response used to set a 503 status when degraded.

    Returns:
        A HealthResponse; HTTP 200 when both stores are reachable, else 503.
    """
    checks = {
        "postgres": _check_postgres(engine),
        "redis": _check_redis(redis_client),
    }
    healthy = all(state == "ok" for state in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="healthy" if healthy else "unhealthy",
        version=API_VERSION,
        checks=checks,
    )
