"""Offline-to-online feature sync.

Streams every row from the PostgreSQL ``user_features`` table into the Redis
online store in batches, then records the sync timestamp under
``features:metadata:last_sync`` (PRD § 11, M3.2).

Rows are ordered by ``computed_at`` ascending so that, were a user_id ever to
recur, the most recently computed row is written last and wins. Redis errors
are caught per chunk: a mid-sync outage yields partial results, not a crash.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from loguru import logger
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.engine import Engine

from src.storage.models import UserFeatures
from src.storage.online_store import DEFAULT_TTL_SECONDS, write_features_batch

_LAST_SYNC_KEY: str = "features:metadata:last_sync"


def _record_last_sync(redis_client: Redis) -> None:
    """Store the current UTC timestamp under the last-sync metadata key."""
    stamp = datetime.now(UTC).isoformat()
    try:
        redis_client.set(_LAST_SYNC_KEY, stamp)
    except RedisError as exc:
        logger.warning("Could not record last_sync metadata: {}", exc)


def _split_batch(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Partition rows into writable ones and a count of skipped rows.

    A row is skipped when it has no usable ``user_id`` (cannot be keyed).
    Since user_id is the table's primary key this count is normally 0.

    Returns:
        A tuple of (writable rows, skipped count).
    """
    writable: list[dict[str, Any]] = []
    skipped = 0
    for row in rows:
        if pd.isna(row.get("user_id")):
            skipped += 1
        else:
            writable.append(row)
    return writable, skipped


def _sync_one_batch(
    redis_client: Redis, rows: Sequence[Any], ttl_seconds: int
) -> tuple[int, int, int]:
    """Write one DB batch to Redis.

    Returns:
        A tuple of (rows synced, rows skipped, rows failed).
    """
    writable, skipped = _split_batch([dict(row) for row in rows])
    if not writable:
        return 0, skipped, 0
    stats = write_features_batch(redis_client, pd.DataFrame(writable), ttl_seconds)
    return int(stats["inserted"]), skipped, int(stats["failed"])


def sync_offline_to_online(
    pg_engine: Engine,
    redis_client: Redis,
    batch_size: int = 500,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, int | float]:
    """Sync all features from the PostgreSQL offline store into Redis.

    Args:
        pg_engine: SQLAlchemy engine for the offline store.
        redis_client: Connected Redis client for the online store.
        batch_size: Rows fetched + pipelined per batch.
        ttl_seconds: Redis key expiry in seconds (default 25 hours).

    Returns:
        ``{"rows_synced": int, "skipped": int, "failed": int,
        "duration_sec": float}``
    """
    t0 = time.perf_counter()
    stmt = select(UserFeatures).order_by(UserFeatures.computed_at)
    rows_synced = 0
    skipped = 0
    failed = 0
    with pg_engine.connect() as conn:
        result = conn.execute(stmt).mappings()
        batch_index = 0
        while True:
            rows = result.fetchmany(batch_size)
            if not rows:
                break
            batch_index += 1
            synced, batch_skipped, batch_failed = _sync_one_batch(
                redis_client, rows, ttl_seconds
            )
            rows_synced += synced
            skipped += batch_skipped
            failed += batch_failed
            logger.info("Sync batch {}: {} rows processed", batch_index, len(rows))
    if rows_synced > 0:
        _record_last_sync(redis_client)
    duration = round(time.perf_counter() - t0, 3)
    logger.success(
        "Offline→online sync complete: {} synced, {} skipped, {} failed in {:.3f}s",
        rows_synced,
        skipped,
        failed,
        duration,
    )
    return {
        "rows_synced": rows_synced,
        "skipped": skipped,
        "failed": failed,
        "duration_sec": duration,
    }
