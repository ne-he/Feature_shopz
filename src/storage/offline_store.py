"""Offline feature store writer.

Persists the wide feature DataFrame produced by run_feature_pipeline into
the ``user_features`` PostgreSQL table. Supports upsert (INSERT … ON CONFLICT
DO UPDATE) with batched execution (PRD § 11, M2.9).
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import pandas as pd
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from src.storage.models import UserFeatures

BATCH_SIZE: int = 5_000

_EXPECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "user_id",
        "recency_days",
        "frequency_count",
        "monetary_total",
        "monetary_avg_per_purchase",
        "monetary_max",
        "preferred_category",
        "preferred_device",
        "preferred_referral",
        "category_diversity_count",
        "product_diversity_count",
        "avg_session_duration",
        "avg_review_score",
        "total_reviews_given",
        "positive_review_ratio",
        "days_since_signup",
        "is_active_30d",
        "purchase_velocity",
        "discount_usage_rate",
        "avg_discount_rate",
        "total_savings",
        "age",
        "country",
        "gender",
        "computed_at",
        "feature_version",
    }
)


def _validate_columns(df: pd.DataFrame) -> None:
    """Raise ValueError if df is missing any required feature columns.

    Args:
        df: Feature DataFrame to validate.

    Raises:
        ValueError: If any column from _EXPECTED_COLUMNS is absent.
    """
    missing = _EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")


def _build_upsert_sql(columns: list[str], upsert: bool) -> str:
    """Build the parameterised INSERT (+ optional ON CONFLICT) SQL statement.

    Args:
        columns: Ordered list of column names from the DataFrame.
        upsert: Whether to append an ON CONFLICT DO UPDATE clause.

    Returns:
        A SQLAlchemy text()-compatible SQL string with :param placeholders.
    """
    col_list = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    base_sql = f"INSERT INTO user_features ({col_list}) VALUES ({placeholders})"  # noqa: S608
    if not upsert:
        return base_sql
    feature_cols = [c for c in columns if c != "user_id"]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in feature_cols)
    return f"{base_sql} ON CONFLICT (user_id) DO UPDATE SET {set_clause}"


def _execute_batches(
    records: list[dict[str, Any]],
    sql: str,
    engine: Engine,
) -> int:
    """Execute batched inserts inside a single transaction.

    Args:
        records: List of row dicts matching the SQL placeholders.
        sql: Parameterised INSERT SQL from _build_upsert_sql.
        engine: SQLAlchemy engine (transaction is rolled back on failure).

    Returns:
        Total number of rows written.
    """
    rows_written = 0
    total = len(records)
    with engine.begin() as conn:
        for start in range(0, total, BATCH_SIZE):
            batch = records[start : start + BATCH_SIZE]
            conn.execute(text(sql), batch)
            rows_written += len(batch)
            logger.debug("Wrote {:,} / {:,} rows to user_features", rows_written, total)
    return rows_written


def write_features_to_db(
    df: pd.DataFrame,
    engine: Engine,
    upsert: bool = True,
) -> dict[str, int | float]:
    """Write the feature DataFrame to the user_features table.

    Validates the 26 expected columns, builds a parameterised upsert SQL
    statement, and executes it in batches of BATCH_SIZE rows inside a single
    transaction. The transaction is automatically rolled back on any error.

    Args:
        df: Wide feature DataFrame from run_feature_pipeline (26 columns).
        engine: Connected SQLAlchemy Engine pointing to the feature store DB.
        upsert: If True, existing rows are updated via ON CONFLICT DO UPDATE.
            If False, duplicate user_id values will raise an IntegrityError.

    Returns:
        ``{"rows_written": N, "duration_sec": X.XXX}``

    Raises:
        ValueError: If df is missing any of the 26 required columns.
    """
    _validate_columns(df)
    columns = list(df.columns)
    sql = _build_upsert_sql(columns, upsert)
    records: list[dict[str, Any]] = df.to_dict(orient="records")
    t0 = time.perf_counter()
    rows_written = _execute_batches(records, sql, engine)
    duration = round(time.perf_counter() - t0, 3)
    logger.success(
        "Offline store write complete: {:,} rows in {:.3f}s", rows_written, duration
    )
    return {"rows_written": rows_written, "duration_sec": duration}


def read_user_features(engine: Engine, user_id: int) -> dict[str, Any] | None:
    """Read one user's full feature row from the offline store.

    Args:
        engine: Connected SQLAlchemy Engine pointing to the feature store DB.
        user_id: User identifier to look up (primary key of user_features).

    Returns:
        A column-name → value dict for the matching row (including the
        ``computed_at`` and ``feature_version`` metadata columns), or None
        if no row exists for that user_id.
    """
    stmt = select(UserFeatures).where(UserFeatures.user_id == user_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()
    return dict(row) if row is not None else None


def get_last_computed_at(engine: Engine) -> datetime | None:
    """Return the most recent ``computed_at`` timestamp across all feature rows.

    Args:
        engine: Connected SQLAlchemy Engine pointing to the feature store DB.

    Returns:
        The newest ``computed_at`` datetime, or None if the table is empty.
    """
    stmt = select(func.max(UserFeatures.computed_at))
    with engine.connect() as conn:
        result: datetime | None = conn.execute(stmt).scalar_one_or_none()
    return result
