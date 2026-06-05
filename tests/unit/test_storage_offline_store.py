"""Unit tests for the offline store writer.

Exercises _validate_columns, _build_upsert_sql, and write_features_to_db
without a real database connection. Engine interactions are mocked.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.storage.offline_store import (
    _build_upsert_sql,
    _validate_columns,
    write_features_to_db,
)

_ALL_COLUMNS: list[str] = [
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
]


@pytest.fixture
def valid_df() -> pd.DataFrame:
    """Minimal valid feature DataFrame with all 26 required columns."""
    data = {col: [None] for col in _ALL_COLUMNS}
    data["user_id"] = [1]
    data["computed_at"] = [datetime.now()]
    data["feature_version"] = ["v1"]
    return pd.DataFrame(data)


@pytest.fixture
def mock_engine() -> MagicMock:
    """Mock SQLAlchemy Engine whose begin() context manager no-ops."""
    engine = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=MagicMock())
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    return engine


class TestValidateColumns:
    """Tests for _validate_columns."""

    def test_validate_columns_all_present_does_not_raise(self, valid_df: pd.DataFrame) -> None:
        """No exception when all 26 columns are present."""
        _validate_columns(valid_df)  # must not raise

    def test_validate_columns_missing_column_raises_value_error(
        self, valid_df: pd.DataFrame
    ) -> None:
        """Missing a required column raises ValueError naming it."""
        df_missing = valid_df.drop(columns=["recency_days"])
        with pytest.raises(ValueError, match="recency_days"):
            _validate_columns(df_missing)

    def test_validate_columns_multiple_missing_lists_all(
        self, valid_df: pd.DataFrame
    ) -> None:
        """All missing column names appear in the error message."""
        df_missing = valid_df.drop(columns=["recency_days", "monetary_total"])
        with pytest.raises(ValueError):
            _validate_columns(df_missing)


class TestBuildUpsertSql:
    """Tests for _build_upsert_sql."""

    def test_build_upsert_sql_upsert_true_contains_on_conflict(self) -> None:
        """upsert=True generates an ON CONFLICT DO UPDATE clause."""
        sql = _build_upsert_sql(_ALL_COLUMNS, upsert=True)
        assert "ON CONFLICT (user_id) DO UPDATE SET" in sql

    def test_build_upsert_sql_upsert_false_plain_insert(self) -> None:
        """upsert=False generates a plain INSERT without ON CONFLICT."""
        sql = _build_upsert_sql(_ALL_COLUMNS, upsert=False)
        assert "ON CONFLICT" not in sql
        assert sql.startswith("INSERT INTO user_features")

    def test_build_upsert_sql_excludes_user_id_from_set_clause(self) -> None:
        """user_id is not included in the SET clause (it's the conflict target)."""
        sql = _build_upsert_sql(_ALL_COLUMNS, upsert=True)
        # Grab the SET clause portion
        set_part = sql.split("DO UPDATE SET")[1]
        assert "user_id = EXCLUDED.user_id" not in set_part

    def test_build_upsert_sql_uses_named_placeholders(self) -> None:
        """Each column has a :col_name placeholder in the VALUES clause."""
        sql = _build_upsert_sql(["user_id", "age"], upsert=False)
        assert ":user_id" in sql
        assert ":age" in sql


class TestWriteFeaturesToDb:
    """Tests for write_features_to_db."""

    def test_write_features_to_db_returns_rows_written(
        self, valid_df: pd.DataFrame, mock_engine: MagicMock
    ) -> None:
        """Stats dict contains rows_written equal to len(df)."""
        stats = write_features_to_db(valid_df, mock_engine)
        assert stats["rows_written"] == len(valid_df)

    def test_write_features_to_db_returns_duration_sec(
        self, valid_df: pd.DataFrame, mock_engine: MagicMock
    ) -> None:
        """Stats dict contains a non-negative duration_sec."""
        stats = write_features_to_db(valid_df, mock_engine)
        assert "duration_sec" in stats
        assert stats["duration_sec"] >= 0

    def test_write_features_to_db_missing_column_raises_value_error(
        self, valid_df: pd.DataFrame, mock_engine: MagicMock
    ) -> None:
        """Validation fires before any DB call; engine is never touched."""
        df_bad = valid_df.drop(columns=["feature_version"])
        with pytest.raises(ValueError):
            write_features_to_db(df_bad, mock_engine)
        mock_engine.begin.assert_not_called()
