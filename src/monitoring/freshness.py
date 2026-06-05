"""Feature freshness checks (PRD § 17, M4.1).

Answers "when were features last computed, and are they stale?" by reading
the newest ``computed_at`` from the offline store and the last successful
offline→online sync timestamp from Redis. Feeds the dashboard overview and
serves as an operational staleness signal.
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.storage.offline_store import get_last_computed_at

_LAST_SYNC_KEY: str = "features:metadata:last_sync"


class FreshnessReport(BaseModel):
    """Snapshot of how current the stored features are."""

    last_computed_at: datetime | None
    age_hours: float | None
    cadence_hours: int
    is_fresh: bool
    last_sync_at: datetime | None


def _to_naive(stamp: datetime) -> datetime:
    """Drop tzinfo so naive and aware timestamps compare without error."""
    return stamp.replace(tzinfo=None) if stamp.tzinfo is not None else stamp


def _read_last_sync(redis_client: Redis) -> datetime | None:
    """Read and parse the last-sync timestamp from Redis, or None on miss."""
    try:
        raw = redis_client.get(_LAST_SYNC_KEY)
    except RedisError as exc:
        logger.warning("Could not read last_sync from Redis: {}", exc)
        return None
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        logger.warning("Malformed last_sync timestamp in Redis: {!r}", text)
        return None


def build_freshness_report(
    engine: Engine,
    redis_client: Redis | None = None,
    now: datetime | None = None,
) -> FreshnessReport:
    """Assemble a freshness report from the offline + online stores.

    Args:
        engine: SQLAlchemy engine for the offline store.
        redis_client: Optional Redis client; adds ``last_sync_at`` when given.
        now: Reference 'current' time; defaults to ``datetime.now()``.

    Returns:
        A FreshnessReport whose ``is_fresh`` is True when the newest
        ``computed_at`` is within FEATURE_REFRESH_CADENCE_HOURS of ``now``.
    """
    reference = _to_naive(now or datetime.now())
    cadence = settings.feature_refresh_cadence_hours
    try:
        last_computed = get_last_computed_at(engine)
    except SQLAlchemyError as exc:
        logger.warning("Could not read last_computed_at: {}", exc)
        last_computed = None
    age_hours: float | None = None
    if last_computed is not None:
        age_hours = (reference - _to_naive(last_computed)).total_seconds() / 3600
    last_sync = _read_last_sync(redis_client) if redis_client is not None else None
    return FreshnessReport(
        last_computed_at=last_computed,
        age_hours=round(age_hours, 3) if age_hours is not None else None,
        cadence_hours=cadence,
        is_fresh=age_hours is not None and age_hours <= cadence,
        last_sync_at=last_sync,
    )
