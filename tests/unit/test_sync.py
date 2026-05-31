"""Unit tests for the offline-to-online sync job.

The PostgreSQL offline store is stood in for by an in-memory SQLite database
(the sync SELECT is dialect-agnostic); the Redis online store is fakeredis.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import fakeredis
import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine, insert
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from src.storage.models import UserFeatures
from src.storage.online_store import get_user_features, sync_status
from src.storage.sync import sync_offline_to_online


@pytest.fixture
def pg_engine() -> Engine:
    """In-memory SQLite engine with the user_features table created.

    StaticPool keeps a single underlying connection so the in-memory DB is
    shared across the seed write and the sync read.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UserFeatures.__table__.create(engine)
    return engine


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    """Return a fresh, isolated in-memory Redis client."""
    return fakeredis.FakeRedis()


def _seed_users(engine: Engine, n: int) -> None:
    """Insert n user_features rows (user_ids 1..n); age/gender left NULL."""
    base = datetime(2026, 5, 17, 3, 0, 0)
    rows = [
        {
            "user_id": uid,
            "recency_days": uid % 30,
            "frequency_count": uid,
            "monetary_total": float(uid) * 10.0,
            "country": "USA",
            "is_active_30d": True,
            "computed_at": base,
            "feature_version": "v1",
        }
        for uid in range(1, n + 1)
    ]
    if rows:
        with engine.begin() as conn:
            conn.execute(insert(UserFeatures), rows)


class _BoomPipe:
    """A pipeline whose execute() always raises, simulating a Redis outage."""

    def set(self, *args: Any, **kwargs: Any) -> _BoomPipe:
        return self

    def execute(self) -> None:
        raise RedisError("simulated redis outage")


class _FailFirstPipeline:
    """FakeRedis wrapper whose first pipeline() fails; later ones succeed."""

    def __init__(self) -> None:
        self._inner = fakeredis.FakeRedis()
        self._pipeline_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def pipeline(self) -> Any:
        self._pipeline_calls += 1
        if self._pipeline_calls == 1:
            return _BoomPipe()
        return self._inner.pipeline()


class TestSyncOfflineToOnline:
    """Tests for sync_offline_to_online."""

    def test_sync_writes_all_rows_to_redis(
        self, pg_engine: Engine, redis_client: fakeredis.FakeRedis
    ) -> None:
        """All 100 seeded users land in Redis."""
        _seed_users(pg_engine, 100)
        stats = sync_offline_to_online(pg_engine, redis_client)
        assert stats["rows_synced"] == 100
        assert sync_status(redis_client)["total_keys"] == 100

    def test_sync_empty_offline_store_returns_zero(
        self, pg_engine: Engine, redis_client: fakeredis.FakeRedis
    ) -> None:
        """Syncing an empty table writes nothing and does not crash."""
        stats = sync_offline_to_online(pg_engine, redis_client)
        assert stats["rows_synced"] == 0
        assert stats["failed"] == 0

    def test_sync_is_idempotent(
        self, pg_engine: Engine, redis_client: fakeredis.FakeRedis
    ) -> None:
        """Running the sync twice leaves the same 50 keys, not duplicates."""
        _seed_users(pg_engine, 50)
        sync_offline_to_online(pg_engine, redis_client)
        stats = sync_offline_to_online(pg_engine, redis_client)
        assert stats["rows_synced"] == 50
        assert sync_status(redis_client)["total_keys"] == 50

    def test_sync_records_last_sync_metadata(
        self, pg_engine: Engine, redis_client: fakeredis.FakeRedis
    ) -> None:
        """A successful sync records a parseable ISO timestamp."""
        _seed_users(pg_engine, 10)
        sync_offline_to_online(pg_engine, redis_client)
        raw = redis_client.get("features:metadata:last_sync")
        assert raw is not None
        datetime.fromisoformat(raw.decode())  # must parse without error

    def test_sync_drops_null_features_in_redis(
        self, pg_engine: Engine, redis_client: fakeredis.FakeRedis
    ) -> None:
        """Columns left NULL in PostgreSQL are absent from the Redis blob."""
        _seed_users(pg_engine, 1)
        sync_offline_to_online(pg_engine, redis_client)
        result = get_user_features(redis_client, 1)
        assert result is not None
        assert result["user_id"] == 1
        assert "age" not in result
        assert "gender" not in result

    def test_sync_partial_failure_continues_after_redis_error(
        self, pg_engine: Engine
    ) -> None:
        """A failed batch is counted; the sync continues with later batches."""
        _seed_users(pg_engine, 100)
        flaky = _FailFirstPipeline()
        stats = sync_offline_to_online(pg_engine, flaky, batch_size=50)
        assert stats["rows_synced"] == 50
        assert stats["failed"] == 50
