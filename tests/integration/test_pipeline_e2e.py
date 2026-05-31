"""End-to-end integration tests: feature pipeline → offline store → PostgreSQL.

Requires Docker (testcontainers spins up a PostgreSQL 15 container).
The entire module is skipped when testcontainers is not installed.

Naming pattern: test_<scenario>_<expected_result>
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

testcontainers = pytest.importorskip(
    "testcontainers",
    reason="testcontainers not installed — skipping integration tests",
)
from testcontainers.postgres import PostgresContainer  # noqa: E402 (after importorskip)

from src.features.pipeline import run_feature_pipeline  # noqa: E402
from src.storage.models import Base  # noqa: E402
from src.storage.offline_store import write_features_to_db  # noqa: E402

_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"
_SAMPLE_CSV = _FIXTURES_DIR / "sample_data.csv"
_REFERENCE_DATE = date(2022, 1, 1)


@pytest.fixture(scope="module")
def pg_engine():  # type: ignore[return]
    """Start a PostgreSQL 15 container, create schema, yield engine, teardown."""
    with PostgresContainer("postgres:15") as pg:
        engine = create_engine(pg.get_connection_url())
        Base.metadata.create_all(engine)
        yield engine
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def feature_df() -> pd.DataFrame:
    """Run the pipeline once over the 10-row sample fixture."""
    return run_feature_pipeline(_SAMPLE_CSV, reference_date=_REFERENCE_DATE)


class TestPipelineE2E:
    """End-to-end tests: pipeline output → offline store → DB verification."""

    def test_write_inserts_all_users(self, pg_engine, feature_df: pd.DataFrame) -> None:  # type: ignore[no-untyped-def]
        """All 10 fixture users are persisted; rows_written matches len(df)."""
        with pg_engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE user_features"))

        stats = write_features_to_db(feature_df, pg_engine)

        assert stats["rows_written"] == len(feature_df)
        with pg_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM user_features")).scalar()
        assert count == len(feature_df)

    def test_upsert_is_idempotent(self, pg_engine, feature_df: pd.DataFrame) -> None:  # type: ignore[no-untyped-def]
        """Writing the same data twice with upsert=True keeps row count stable."""
        with pg_engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE user_features"))

        write_features_to_db(feature_df, pg_engine)
        write_features_to_db(feature_df, pg_engine, upsert=True)

        with pg_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM user_features")).scalar()
        assert count == len(feature_df)

    def test_written_row_matches_pipeline_output(
        self, pg_engine, feature_df: pd.DataFrame  # type: ignore[no-untyped-def]
    ) -> None:
        """User 7's recency_days in DB matches the pipeline DataFrame."""
        with pg_engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE user_features"))
        write_features_to_db(feature_df, pg_engine)

        expected = int(
            feature_df.loc[feature_df["user_id"] == 7, "recency_days"].iloc[0]
        )
        with pg_engine.connect() as conn:
            row = conn.execute(
                text("SELECT recency_days FROM user_features WHERE user_id = 7")
            ).fetchone()
        assert row is not None
        assert row[0] == expected

    def test_stats_contain_duration(self, pg_engine, feature_df: pd.DataFrame) -> None:  # type: ignore[no-untyped-def]
        """write_features_to_db returns a dict with rows_written and duration_sec."""
        with pg_engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE user_features"))
        stats = write_features_to_db(feature_df, pg_engine)
        assert "rows_written" in stats
        assert "duration_sec" in stats
        assert stats["duration_sec"] >= 0
