"""Unit tests for src.monitoring.freshness (M4.1).

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

from datetime import datetime, timedelta

import fakeredis
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.monitoring.freshness import build_freshness_report
from src.storage.models import UserFeatures

_NOW = datetime(2026, 5, 17, 12, 0, 0)


def _seed(engine: Engine, computed_at: datetime) -> None:
    """Insert a single user_features row with the given computed_at."""
    with Session(engine) as session:
        session.add(
            UserFeatures(user_id=1, recency_days=1, computed_at=computed_at, feature_version="v1")
        )
        session.commit()


def test_build_freshness_report_recent_is_fresh(offline_engine: Engine) -> None:
    """A row computed 2h ago is within the 24h cadence -> fresh."""
    _seed(offline_engine, _NOW - timedelta(hours=2))
    report = build_freshness_report(offline_engine, now=_NOW)
    assert report.is_fresh is True
    assert report.age_hours is not None and 1.9 < report.age_hours < 2.1


def test_build_freshness_report_old_is_stale(offline_engine: Engine) -> None:
    """A row computed 48h ago exceeds the 24h cadence -> stale."""
    _seed(offline_engine, _NOW - timedelta(hours=48))
    report = build_freshness_report(offline_engine, now=_NOW)
    assert report.is_fresh is False
    assert report.age_hours is not None and report.age_hours > 24


def test_build_freshness_report_empty_table_returns_none(offline_engine: Engine) -> None:
    """No rows -> no last_computed_at, no age, not fresh."""
    report = build_freshness_report(offline_engine, now=_NOW)
    assert report.last_computed_at is None
    assert report.age_hours is None
    assert report.is_fresh is False


def test_build_freshness_report_reads_last_sync_from_redis(
    offline_engine: Engine, fake_redis_client: fakeredis.FakeRedis
) -> None:
    """A valid last_sync key in Redis is parsed into last_sync_at."""
    fake_redis_client.set("features:metadata:last_sync", "2026-05-17T03:00:00")
    _seed(offline_engine, _NOW - timedelta(hours=1))
    report = build_freshness_report(offline_engine, fake_redis_client, now=_NOW)
    assert report.last_sync_at == datetime(2026, 5, 17, 3, 0, 0)


def test_build_freshness_report_malformed_last_sync_returns_none(
    offline_engine: Engine, fake_redis_client: fakeredis.FakeRedis
) -> None:
    """A malformed last_sync value is ignored (None), not raised."""
    fake_redis_client.set("features:metadata:last_sync", "not-a-timestamp")
    report = build_freshness_report(offline_engine, fake_redis_client, now=_NOW)
    assert report.last_sync_at is None
