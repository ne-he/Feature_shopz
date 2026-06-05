"""Store and feature metrics for the monitoring dashboard (PRD § 17, M4.7).

Lightweight read helpers the dashboard and drift module build on: row counts
for the offline and online stores, plus a loader that pulls the full
``user_features`` table into a DataFrame for distribution and drift analysis.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from src.storage.models import UserFeatures
from src.storage.online_store import sync_status


def count_offline_users(engine: Engine) -> int:
    """Return the number of rows in the offline ``user_features`` table."""
    stmt = select(func.count()).select_from(UserFeatures)
    with engine.connect() as conn:
        return int(conn.execute(stmt).scalar_one())


def count_online_keys(redis_client: Redis) -> int:
    """Return the number of user feature blobs currently held in Redis."""
    return int(sync_status(redis_client)["total_keys"])


def load_feature_frame(engine: Engine) -> pd.DataFrame:
    """Load the full ``user_features`` table into a DataFrame.

    Used by the dashboard (feature distributions) and the drift module
    (reference vs current windows).

    Args:
        engine: SQLAlchemy engine for the offline store.

    Returns:
        A DataFrame with one row per user and all feature columns.
    """
    with engine.connect() as conn:
        frame = pd.read_sql(select(UserFeatures), conn)
    logger.debug("Loaded {} feature rows for analysis", len(frame))
    return frame
