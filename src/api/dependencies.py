"""FastAPI dependency-injection providers for the serving layer.

The application lifespan (see ``src.api.main``) creates a single SQLAlchemy
Engine and Redis client and stores them on ``app.state``. These providers
expose those shared resources to route handlers so connections are created
once per process rather than per request.

Tests override these providers via ``app.dependency_overrides`` to inject
in-memory stand-ins (SQLite engine + fakeredis), keeping the suite free of
any running database or cache server.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request
from redis import Redis
from sqlalchemy.engine import Engine


def get_engine(request: Request) -> Engine:
    """Return the process-wide SQLAlchemy engine from application state.

    Args:
        request: The incoming request (carries ``app.state``).

    Returns:
        The shared SQLAlchemy Engine for the offline (PostgreSQL) store.
    """
    return cast("Engine", request.app.state.engine)


def get_redis(request: Request) -> Redis:
    """Return the process-wide Redis client from application state.

    Args:
        request: The incoming request (carries ``app.state``).

    Returns:
        The shared Redis client for the online store.
    """
    return cast("Redis", request.app.state.redis)


EngineDep = Annotated[Engine, Depends(get_engine)]
"""Route-parameter alias injecting the shared SQLAlchemy engine."""

RedisDep = Annotated[Redis, Depends(get_redis)]
"""Route-parameter alias injecting the shared Redis client."""
