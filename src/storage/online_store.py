"""Redis online store for low-latency feature serving.

Persists per-user feature dicts as JSON blobs under ``features:user:{id}``
keys with a 25-hour TTL, and provides single + batch read/write helpers plus
a lightweight status probe (PRD § 11 Redis Schema, M3.1).
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import pandas as pd
import redis
from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from src.config import settings

DEFAULT_TTL_SECONDS: int = 90_000  # 25 hours — one hour past the daily refresh
PIPELINE_CHUNK_SIZE: int = 200
_KEY_PREFIX: str = "features:user:"


def get_redis_client() -> Redis:
    """Create a Redis client from application settings.

    The client is lazy: no network connection is opened until the first
    command is issued.

    Returns:
        A Redis client pointed at the configured host/port.
    """
    return redis.from_url(settings.redis_url)


def _user_key(user_id: int) -> str:
    """Return the Redis key for a user's feature blob."""
    return f"{_KEY_PREFIX}{user_id}"


def _json_default(value: object) -> object:
    """JSON encoder fallback for datetime and Decimal values.

    Raises:
        TypeError: For any value type that is not handled here.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    """Drop null/NaN-valued keys so they are omitted from the stored JSON."""
    return {key: val for key, val in record.items() if not pd.isna(val)}


def set_user_features(
    redis_client: Redis,
    user_id: int,
    features: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """Write one user's feature dict to Redis as a JSON blob.

    Args:
        redis_client: Connected Redis client.
        user_id: User identifier (used to build the key).
        features: Feature name → value mapping; null values are omitted.
        ttl_seconds: Key expiry in seconds (default 25 hours).

    Returns:
        True on success; False if serialization or the Redis write failed.
    """
    try:
        payload = json.dumps(_clean_record(features), default=_json_default)
    except TypeError as exc:
        logger.warning("Cannot serialize features for user {}: {}", user_id, exc)
        return False
    try:
        redis_client.set(_user_key(user_id), payload, ex=ttl_seconds)
    except RedisError as exc:
        logger.warning("Redis write failed for user {}: {}", user_id, exc)
        return False
    return True


def get_user_features(redis_client: Redis, user_id: int) -> dict[str, Any] | None:
    """Read one user's feature dict from Redis.

    Args:
        redis_client: Connected Redis client.
        user_id: User identifier.

    Returns:
        The feature dict, or None if the key is missing/expired, Redis is
        unreachable, or the stored value is not valid JSON.
    """
    try:
        raw = cast("bytes | None", redis_client.get(_user_key(user_id)))
    except RedisError as exc:
        logger.warning("Redis read failed for user {}: {}", user_id, exc)
        return None
    if raw is None:
        return None
    try:
        parsed: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Corrupt JSON for user {}: {}", user_id, exc)
        return None
    return parsed


def _serialize_rows(df: pd.DataFrame) -> tuple[list[tuple[str, str]], int]:
    """Convert DataFrame rows to (key, json_payload) pairs.

    Args:
        df: Wide feature DataFrame with a ``user_id`` column.

    Returns:
        A tuple of (serializable (key, payload) pairs, count of failed rows).
    """
    pairs: list[tuple[str, str]] = []
    failed = 0
    for record in df.to_dict(orient="records"):
        try:
            user_id = int(record["user_id"])
            payload = json.dumps(_clean_record(record), default=_json_default)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Skipping unserializable row: {}", exc)
            failed += 1
            continue
        pairs.append((_user_key(user_id), payload))
    return pairs, failed


def _flush_chunk(
    redis_client: Redis, chunk: list[tuple[str, str]], ttl_seconds: int
) -> int:
    """SET every (key, payload) in one pipeline.

    Returns:
        The number of rows written, or 0 if the pipeline failed.
    """
    try:
        pipe = redis_client.pipeline()
        for key, payload in chunk:
            pipe.set(key, payload, ex=ttl_seconds)
        pipe.execute()
    except RedisError as exc:
        logger.warning("Redis pipeline failed for {}-row chunk: {}", len(chunk), exc)
        return 0
    return len(chunk)


def write_features_batch(
    redis_client: Redis,
    df: pd.DataFrame,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, int | float]:
    """Write every row of a feature DataFrame to Redis using pipelines.

    Rows are serialized to JSON (null values omitted) and SET in pipelined
    chunks of PIPELINE_CHUNK_SIZE to avoid per-row round trips.

    Args:
        redis_client: Connected Redis client.
        df: Wide feature DataFrame with a ``user_id`` column.
        ttl_seconds: Key expiry in seconds (default 25 hours).

    Returns:
        ``{"inserted": int, "failed": int, "duration_sec": float}``
    """
    t0 = time.perf_counter()
    pairs, failed = _serialize_rows(df)
    inserted = 0
    for start in range(0, len(pairs), PIPELINE_CHUNK_SIZE):
        chunk = pairs[start : start + PIPELINE_CHUNK_SIZE]
        written = _flush_chunk(redis_client, chunk, ttl_seconds)
        inserted += written
        failed += len(chunk) - written
    duration = round(time.perf_counter() - t0, 3)
    logger.success(
        "Redis batch write: {} inserted, {} failed in {:.3f}s",
        inserted,
        failed,
        duration,
    )
    return {"inserted": inserted, "failed": failed, "duration_sec": duration}


def _collect_computed_at(redis_client: Redis, keys: list[Any]) -> list[str]:
    """Read each key's blob and extract its ``computed_at`` timestamp string."""
    if not keys:
        return []
    try:
        values = cast("list[bytes | None]", redis_client.mget(keys))
    except RedisError as exc:
        logger.warning("Redis mget failed during status probe: {}", exc)
        return []
    stamps: list[str] = []
    for raw in values:
        if raw is None:
            continue
        try:
            doc = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        stamp = doc.get("computed_at")
        if stamp is not None:
            stamps.append(str(stamp))
    return stamps


def sync_status(redis_client: Redis) -> dict[str, Any]:
    """Summarize the current state of the online store.

    Args:
        redis_client: Connected Redis client.

    Returns:
        ``{"total_keys": int, "oldest_computed_at": str | None,
        "newest_computed_at": str | None}``. Counts are 0 / None when Redis
        is unreachable. ISO timestamp strings sort chronologically, so
        ``min``/``max`` give the oldest/newest computed_at.
    """
    try:
        keys = list(redis_client.scan_iter(match=f"{_KEY_PREFIX}*"))
    except RedisError as exc:
        logger.warning("Redis scan failed: {}", exc)
        return {"total_keys": 0, "oldest_computed_at": None, "newest_computed_at": None}
    timestamps = _collect_computed_at(redis_client, keys)
    return {
        "total_keys": len(keys),
        "oldest_computed_at": min(timestamps) if timestamps else None,
        "newest_computed_at": max(timestamps) if timestamps else None,
    }
