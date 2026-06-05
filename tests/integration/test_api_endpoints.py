"""Integration tests for the feature-serving API (PRD § 12, M3.10).

The API is exercised end-to-end with FastAPI's TestClient. Both backing
stores are replaced with in-memory stand-ins via dependency overrides:
an in-memory SQLite engine for the offline store and fakeredis for the
online store. No PostgreSQL or Redis server is required.

Naming pattern: test_<endpoint>_<scenario>_<expected_result>
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from unittest.mock import MagicMock

import fakeredis
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_engine, get_redis
from src.api.main import create_app
from src.storage.models import Base, UserFeatures
from src.storage.online_store import set_user_features

_OLDER = datetime(2026, 5, 16, 3, 0, 0)
_NEWER = datetime(2026, 5, 17, 3, 0, 0)


@pytest.fixture
def sqlite_engine() -> Engine:
    """In-memory SQLite engine seeded with the user_features table.

    Uses StaticPool so every connection shares one in-memory database.
    Seeds users 1, 2 (also in Redis) and 5 (offline-only, for fallback).
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                UserFeatures(
                    user_id=1, recency_days=7, monetary_total=100.5,
                    country="USA", computed_at=_OLDER, feature_version="v1",
                ),
                UserFeatures(
                    user_id=2, recency_days=30, monetary_total=42.0,
                    country="UK", computed_at=_NEWER, feature_version="v1",
                ),
                UserFeatures(
                    user_id=5, recency_days=3, monetary_total=999.0,
                    country="India", computed_at=_OLDER, feature_version="v1",
                ),
            ]
        )
        session.commit()
    return engine


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """In-memory Redis seeded with users 1 and 2 only."""
    client = fakeredis.FakeRedis()
    set_user_features(
        client, 1,
        {"user_id": 1, "recency_days": 7, "monetary_total": 100.5,
         "computed_at": "2026-05-16T03:00:00", "feature_version": "v1"},
    )
    set_user_features(
        client, 2,
        {"user_id": 2, "recency_days": 30, "monetary_total": 42.0,
         "computed_at": "2026-05-17T03:00:00", "feature_version": "v1"},
    )
    return client


def _make_client(engine: Engine, redis_client: object) -> TestClient:
    """Build a TestClient whose store dependencies are overridden."""
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_redis] = lambda: redis_client
    return TestClient(app)


@pytest.fixture
def client(
    sqlite_engine: Engine, fake_redis: fakeredis.FakeRedis
) -> Iterator[TestClient]:
    """A TestClient wired to the seeded SQLite + fakeredis stores."""
    with _make_client(sqlite_engine, fake_redis) as test_client:
        yield test_client


class TestHealth:
    """Tests for GET /health."""

    def test_health_all_stores_up_returns_healthy(self, client: TestClient) -> None:
        """Both stores reachable -> 200 with status healthy."""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["checks"] == {"postgres": "ok", "redis": "ok"}

    def test_health_redis_down_returns_503(self, sqlite_engine: Engine) -> None:
        """An unreachable Redis -> 503 with status unhealthy."""
        broken = MagicMock()
        broken.ping.side_effect = RedisError("down")
        with _make_client(sqlite_engine, broken) as client:
            resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"
        assert resp.json()["checks"]["redis"] == "unavailable"


class TestOnlineFeatures:
    """Tests for GET /features/online/{user_id}."""

    def test_online_user_in_redis_returns_redis_source(self, client: TestClient) -> None:
        """A user present in Redis is served from Redis."""
        resp = client.get("/features/online/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == 1
        assert body["metadata"]["source"] == "redis"
        assert body["features"]["recency_days"] == 7

    def test_online_user_only_in_postgres_falls_back(self, client: TestClient) -> None:
        """A Redis miss falls back to PostgreSQL."""
        resp = client.get("/features/online/5")
        assert resp.status_code == 200
        assert resp.json()["metadata"]["source"] == "postgres"
        assert resp.json()["features"]["recency_days"] == 3

    def test_online_unknown_user_returns_404(self, client: TestClient) -> None:
        """A user in neither store -> 404."""
        resp = client.get("/features/online/99")
        assert resp.status_code == 404

    def test_online_feature_list_filters_result(self, client: TestClient) -> None:
        """feature_list query restricts the returned features."""
        resp = client.get("/features/online/1?feature_list=recency_days")
        assert resp.status_code == 200
        assert set(resp.json()["features"]) == {"recency_days"}

    def test_online_response_has_timing_header(self, client: TestClient) -> None:
        """Every response carries the X-Process-Time-Ms header (middleware)."""
        resp = client.get("/features/online/1")
        assert "X-Process-Time-Ms" in resp.headers


class TestOfflineFeatures:
    """Tests for GET /features/offline/{user_id}."""

    def test_offline_existing_user_returns_postgres_source(
        self, client: TestClient
    ) -> None:
        """An offline lookup returns the row with source=postgres."""
        resp = client.get("/features/offline/5")
        assert resp.status_code == 200
        assert resp.json()["metadata"]["source"] == "postgres"
        assert resp.json()["features"]["country"] == "India"

    def test_offline_unknown_user_returns_404(self, client: TestClient) -> None:
        """An absent offline row -> 404."""
        assert client.get("/features/offline/99").status_code == 404


class TestBatchFeatures:
    """Tests for POST /features/batch."""

    def test_batch_mix_of_hits_and_misses_counts_correctly(
        self, client: TestClient
    ) -> None:
        """Found/missing counts reflect Redis hits."""
        resp = client.post("/features/batch", json={"user_ids": [1, 2, 99]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["found"] == 2
        assert body["metadata"]["missing"] == 1
        missing_item = next(r for r in body["results"] if r["user_id"] == 99)
        assert missing_item["error"] == "not_found"

    def test_batch_feature_list_filters_each_result(self, client: TestClient) -> None:
        """feature_list restricts the features of each found user."""
        resp = client.post(
            "/features/batch",
            json={"user_ids": [1], "feature_list": ["recency_days"]},
        )
        assert resp.status_code == 200
        assert set(resp.json()["results"][0]["features"]) == {"recency_days"}

    def test_batch_over_100_users_returns_422(self, client: TestClient) -> None:
        """Exceeding the 100-user cap -> 422 validation error."""
        resp = client.post("/features/batch", json={"user_ids": list(range(101))})
        assert resp.status_code == 422

    def test_batch_empty_user_ids_returns_422(self, client: TestClient) -> None:
        """An empty user_ids list -> 422 validation error."""
        assert client.post("/features/batch", json={"user_ids": []}).status_code == 422


class TestFeatureMetadata:
    """Tests for GET /features/metadata."""

    def test_metadata_lists_registered_features(self, client: TestClient) -> None:
        """The catalog reflects the populated REGISTRY and newest timestamp."""
        resp = client.get("/features/metadata")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_features"] == len(body["features"]) > 0
        assert {"name", "description", "data_type"} <= body["features"][0].keys()
        assert body["last_computed_at"].startswith("2026-05-17")
