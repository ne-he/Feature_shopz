"""The daily feature-refresh job (PRD § 13, M4.5).

One callable, ``run_refresh_job``, chains the existing pieces end to end:
compute features from the raw CSV, upsert them into the offline store, then
sync the offline store into Redis. APScheduler (``flows.py``) invokes it on a
daily cadence; it is also directly callable for an on-demand refresh.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config import settings
from src.features.pipeline import run_feature_pipeline
from src.storage.offline_store import write_features_to_db
from src.storage.online_store import get_redis_client
from src.storage.sync import sync_offline_to_online

_DEFAULT_CSV: Path = (
    Path(__file__).parents[2] / "data" / "raw" / "ecommerce_synthetic_dataset.csv"
)


def run_refresh_job(
    csv_path: str | Path | None = None,
    engine: Engine | None = None,
    redis_client: Redis | None = None,
) -> dict[str, Any]:
    """Compute, persist, and sync features end to end.

    Args:
        csv_path: Raw transactions CSV; defaults to data/raw/ecommerce_...csv.
        engine: Offline-store engine; one is created from settings if omitted
            (and disposed afterwards).
        redis_client: Online-store client; created from settings if omitted.

    Returns:
        Summary dict with ``rows_written``, ``rows_synced``, ``duration_sec``.
    """
    csv = Path(csv_path) if csv_path is not None else _DEFAULT_CSV
    owns_engine = engine is None
    eng = engine or create_engine(settings.postgres_url)
    rds = redis_client or get_redis_client()
    try:
        features = run_feature_pipeline(csv)
        write_stats = write_features_to_db(features, eng)
        sync_stats = sync_offline_to_online(eng, rds)
        logger.success(
            "Refresh job done: {} written, {} synced",
            write_stats["rows_written"],
            sync_stats["rows_synced"],
        )
        return {
            "rows_written": write_stats["rows_written"],
            "rows_synced": sync_stats["rows_synced"],
            "duration_sec": round(
                write_stats["duration_sec"] + sync_stats["duration_sec"], 3
            ),
        }
    finally:
        if owns_engine:
            eng.dispose()
