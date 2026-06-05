"""Unit tests for the Redis online store.

Uses fakeredis (an in-memory Redis implementation) so the suite needs no
running server. Redis-error paths are exercised with a MagicMock client.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import fakeredis
import pandas as pd
import pytest
from redis import Redis
from redis.exceptions import RedisError

from src.storage.online_store import (
    get_redis_client,
    get_user_features,
    set_user_features,
    sync_status,
    write_features_batch,
)


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    """Return a fresh, isolated in-memory Redis client."""
    return fakeredis.FakeRedis()


def _make_feature_df(n: int) -> pd.DataFrame:
    """Build an n-row feature DataFrame with user_ids 1..n."""
    user_ids = list(range(1, n + 1))
    return pd.DataFrame(
        {
            "user_id": user_ids,
            "recency_days": [uid % 30 for uid in user_ids],
            "monetary_total": [float(uid) * 10.0 for uid in user_ids],
            "country": ["USA"] * n,
            "computed_at": [datetime(2026, 5, 17, 3, 0, 0)] * n,
            "feature_version": ["v1"] * n,
        }
    )


class TestSetGetUserFeatures:
    """Tests for set_user_features and get_user_features round-trips."""

    def test_set_then_get_round_trips_features(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """Features written then read back are identical."""
        features = {"user_id": 1, "recency_days": 7, "country": "USA"}
        assert set_user_features(redis_client, 1, features) is True
        assert get_user_features(redis_client, 1) == features

    def test_get_user_features_missing_key_returns_none(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """A user with no Redis key yields None."""
        assert get_user_features(redis_client, 999) is None

    def test_set_user_features_applies_ttl(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """The key is created with the requested TTL."""
        set_user_features(redis_client, 1, {"user_id": 1}, ttl_seconds=90_000)
        ttl = redis_client.ttl("features:user:1")
        assert 0 < ttl <= 90_000

    def test_set_user_features_serializes_datetime(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """datetime values are stored as ISO 8601 strings."""
        ts = datetime(2026, 5, 17, 3, 0, 0)
        set_user_features(redis_client, 1, {"user_id": 1, "computed_at": ts})
        result = get_user_features(redis_client, 1)
        assert result is not None
        assert result["computed_at"] == ts.isoformat()

    def test_set_user_features_drops_null_values(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """Null-valued features are omitted from the stored JSON."""
        set_user_features(redis_client, 1, {"user_id": 1, "recency_days": None})
        assert get_user_features(redis_client, 1) == {"user_id": 1}

    def test_get_user_features_redis_error_returns_none(self) -> None:
        """A Redis read error is swallowed and yields None."""
        broken = MagicMock()
        broken.get.side_effect = RedisError("connection refused")
        assert get_user_features(broken, 1) is None

    def test_set_user_features_redis_error_returns_false(self) -> None:
        """A Redis write error is swallowed and yields False."""
        broken = MagicMock()
        broken.set.side_effect = RedisError("connection refused")
        assert set_user_features(broken, 1, {"user_id": 1}) is False

    def test_set_user_features_unserializable_value_returns_false(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """A value JSON cannot encode yields False, with nothing written."""
        assert set_user_features(redis_client, 1, {"user_id": 1, "bad": object()}) is False
        assert get_user_features(redis_client, 1) is None

    def test_get_user_features_corrupt_json_returns_none(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """A key holding non-JSON bytes yields None instead of raising."""
        redis_client.set("features:user:1", b"not-valid-json{")
        assert get_user_features(redis_client, 1) is None


class TestWriteFeaturesBatch:
    """Tests for write_features_batch."""

    def test_write_features_batch_writes_all_rows(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """All 1000 rows are written and individually retrievable."""
        stats = write_features_batch(redis_client, _make_feature_df(1000))
        assert stats["inserted"] == 1000
        assert stats["failed"] == 0
        for uid in (1, 500, 1000):
            assert get_user_features(redis_client, uid) is not None

    def test_write_features_batch_returns_duration(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """The stats dict reports a non-negative duration."""
        stats = write_features_batch(redis_client, _make_feature_df(10))
        assert stats["duration_sec"] >= 0

    def test_write_features_batch_drops_null_feature(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """A null cell in one row is omitted from that user's blob."""
        df = _make_feature_df(3)
        df.loc[0, "country"] = None
        write_features_batch(redis_client, df)
        result = get_user_features(redis_client, 1)
        assert result is not None
        assert "country" not in result

    def test_write_features_batch_empty_df_returns_zero(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """An empty DataFrame writes nothing and reports zero inserted."""
        stats = write_features_batch(redis_client, _make_feature_df(0))
        assert stats["inserted"] == 0

    def test_write_features_batch_skips_unserializable_row(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """An unserializable row is counted as failed; clean rows still write."""
        df = _make_feature_df(3)
        df["bad"] = [None, object(), None]
        stats = write_features_batch(redis_client, df)
        assert stats["inserted"] == 2
        assert stats["failed"] == 1


class TestSyncStatus:
    """Tests for sync_status."""

    def test_sync_status_empty_store_reports_zero(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """An empty store reports zero keys and no timestamps."""
        status = sync_status(redis_client)
        assert status["total_keys"] == 0
        assert status["oldest_computed_at"] is None
        assert status["newest_computed_at"] is None

    def test_sync_status_counts_keys(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """total_keys equals the number of user blobs written."""
        write_features_batch(redis_client, _make_feature_df(5))
        assert sync_status(redis_client)["total_keys"] == 5

    def test_sync_status_reports_oldest_and_newest(
        self, redis_client: fakeredis.FakeRedis
    ) -> None:
        """oldest/newest computed_at are derived from the stored blobs."""
        set_user_features(redis_client, 1, {"user_id": 1, "computed_at": "2026-05-01T00:00:00"})
        set_user_features(redis_client, 2, {"user_id": 2, "computed_at": "2026-05-17T00:00:00"})
        set_user_features(redis_client, 3, {"user_id": 3, "computed_at": "2026-05-10T00:00:00"})
        status = sync_status(redis_client)
        assert status["oldest_computed_at"] == "2026-05-01T00:00:00"
        assert status["newest_computed_at"] == "2026-05-17T00:00:00"

    def test_sync_status_scan_error_returns_zero(self) -> None:
        """A Redis scan failure yields a zeroed status, not a crash."""
        broken = MagicMock()
        broken.scan_iter.side_effect = RedisError("connection refused")
        status = sync_status(broken)
        assert status["total_keys"] == 0
        assert status["oldest_computed_at"] is None

    def test_sync_status_mget_error_yields_no_timestamps(self) -> None:
        """A scan that succeeds but mget that fails reports keys, no timestamps."""
        broken = MagicMock()
        broken.scan_iter.return_value = iter([b"features:user:1"])
        broken.mget.side_effect = RedisError("connection refused")
        status = sync_status(broken)
        assert status["total_keys"] == 1
        assert status["newest_computed_at"] is None


class TestGetRedisClient:
    """Tests for the get_redis_client factory."""

    def test_get_redis_client_returns_redis_instance(self) -> None:
        """The factory returns a Redis client (no connection is opened)."""
        assert isinstance(get_redis_client(), Redis)
