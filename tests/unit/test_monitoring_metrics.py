"""Unit tests for src.monitoring.metrics (M4.7).

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

from datetime import datetime

import fakeredis
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.monitoring.metrics import (
    count_offline_users,
    count_online_keys,
    load_feature_frame,
)
from src.storage.models import UserFeatures
from src.storage.online_store import set_user_features


def _seed_users(engine: Engine, n: int) -> None:
    """Insert n user_features rows with ids 1..n."""
    with Session(engine) as session:
        session.add_all(
            UserFeatures(
                user_id=i, recency_days=i, monetary_total=float(i),
                computed_at=datetime(2026, 5, 17), feature_version="v1",
            )
            for i in range(1, n + 1)
        )
        session.commit()


def test_count_offline_users_counts_rows(offline_engine: Engine) -> None:
    """The count matches the number of seeded rows."""
    _seed_users(offline_engine, 5)
    assert count_offline_users(offline_engine) == 5


def test_count_offline_users_empty_is_zero(offline_engine: Engine) -> None:
    """An empty table counts as zero."""
    assert count_offline_users(offline_engine) == 0


def test_count_online_keys_counts_blobs(fake_redis_client: fakeredis.FakeRedis) -> None:
    """Each written user blob is counted once."""
    for uid in (1, 2, 3):
        set_user_features(fake_redis_client, uid, {"user_id": uid, "recency_days": uid})
    assert count_online_keys(fake_redis_client) == 3


def test_load_feature_frame_returns_all_rows(offline_engine: Engine) -> None:
    """The loaded frame has one row per user and the expected columns."""
    _seed_users(offline_engine, 4)
    frame = load_feature_frame(offline_engine)
    assert len(frame) == 4
    assert {"user_id", "recency_days", "monetary_total"} <= set(frame.columns)
