"""Unit tests for the feature pipeline orchestrator.

Exercises run_feature_pipeline end-to-end against the 10-row sample CSV
fixture, plus a synthesised multi-purchase user for the grouped path.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.features.definitions import (
    FeatureDefinition,
    FeatureRegistry,
    RegisteredFeature,
)
from src.features.pipeline import FEATURE_VERSION, run_feature_pipeline

# The 23 feature columns expected in the pipeline output (PRD § 9).
FEATURE_COLUMNS: frozenset[str] = frozenset(
    {
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
    }
)
METADATA_COLUMNS: frozenset[str] = frozenset({"user_id", "computed_at", "feature_version"})


@pytest.fixture
def pipeline_output(sample_csv_path: Path) -> pd.DataFrame:
    """Run the pipeline once over the sample fixture for reuse across tests."""
    return run_feature_pipeline(sample_csv_path, reference_date=date(2022, 1, 1))


def _write_multi_purchase_csv(sample_csv_path: Path, tmp_path: Path) -> Path:
    """Create a CSV where UserID 1 has three purchases of distinct products."""
    base = pd.read_csv(sample_csv_path)
    template = base[base["UserID"] == 1].iloc[0]
    rows = []
    for product_id, purchase_date in (
        (1001, "2021-03-01"),
        (1002, "2021-06-15"),
        (1003, "2021-09-20"),
    ):
        row = template.copy()
        row["ProductID"] = product_id
        row["PurchaseDate"] = purchase_date
        rows.append(row)
    out_path = tmp_path / "multi_purchase.csv"
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return out_path


class TestRunFeaturePipeline:
    """Tests for run_feature_pipeline over the sample fixture."""

    def test_run_feature_pipeline_returns_dataframe(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """The pipeline returns a pandas DataFrame."""
        assert isinstance(pipeline_output, pd.DataFrame)

    def test_run_feature_pipeline_has_all_feature_and_metadata_columns(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """Output has user_id, all 23 features, and the 2 metadata columns."""
        assert set(pipeline_output.columns) == FEATURE_COLUMNS | METADATA_COLUMNS

    def test_run_feature_pipeline_one_row_per_distinct_user(
        self, pipeline_output: pd.DataFrame, sample_csv_path: Path
    ) -> None:
        """Row count equals the number of distinct UserIDs in the input."""
        distinct_users = pd.read_csv(sample_csv_path)["UserID"].nunique()
        assert len(pipeline_output) == distinct_users

    def test_run_feature_pipeline_user_id_is_unique(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """user_id is a valid primary key — no duplicates."""
        assert pipeline_output["user_id"].is_unique

    def test_run_feature_pipeline_feature_version_is_v1(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """Every row is tagged with the current feature version."""
        assert (pipeline_output["feature_version"] == FEATURE_VERSION).all()

    def test_run_feature_pipeline_computed_at_is_populated(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """The computed_at metadata column has no missing values."""
        assert pipeline_output["computed_at"].notna().all()

    def test_run_feature_pipeline_no_null_features_on_clean_data(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """Clean fixture data produces no null feature values."""
        assert pipeline_output[list(FEATURE_COLUMNS)].notna().all().all()

    def test_run_feature_pipeline_feature_values_are_sane(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """Spot-check feature value ranges against their definitions."""
        assert (pipeline_output["recency_days"] >= 0).all()
        assert (pipeline_output["frequency_count"] == 1).all()
        assert (pipeline_output["monetary_total"] > 0).all()
        assert pipeline_output["positive_review_ratio"].between(0.0, 1.0).all()
        assert pipeline_output["discount_usage_rate"].between(0.0, 1.0).all()

    def test_run_feature_pipeline_explicit_reference_date_drives_recency(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """User 7 purchased 2021-12-25; against ref 2022-01-01 recency is 7."""
        user_7 = pipeline_output.loc[pipeline_output["user_id"] == 7].iloc[0]
        assert user_7["recency_days"] == 7

    def test_run_feature_pipeline_demographics_match_raw_data(
        self, pipeline_output: pd.DataFrame
    ) -> None:
        """Demographic features are copied verbatim from the raw row."""
        user_1 = pipeline_output.loc[pipeline_output["user_id"] == 1].iloc[0]
        assert user_1["age"] == 25
        assert user_1["country"] == "USA"
        assert user_1["gender"] == "Male"

    def test_run_feature_pipeline_default_reference_date_is_latest_purchase(
        self, sample_csv_path: Path
    ) -> None:
        """Omitting reference_date anchors recency to the latest PurchaseDate.

        User 7's purchase (2021-12-25) is the latest in the fixture, so its
        recency must be 0 when the default reference date is derived.
        """
        result = run_feature_pipeline(sample_csv_path)
        user_7 = result.loc[result["user_id"] == 7].iloc[0]
        assert user_7["recency_days"] == 0

    def test_run_feature_pipeline_imputes_null_when_a_feature_raises(
        self, sample_csv_path: Path
    ) -> None:
        """A feature whose compute function raises is imputed as null, not fatal."""
        registry = FeatureRegistry()

        def _exploding_compute(user_df: pd.DataFrame) -> int:
            raise ValueError("simulated feature failure")

        registry.register(
            RegisteredFeature(
                definition=FeatureDefinition(
                    name="exploding_feature",
                    description="Always fails",
                    data_type="int",
                    owner="test",
                ),
                compute=_exploding_compute,
            )
        )
        result = run_feature_pipeline(
            sample_csv_path, registry=registry, reference_date=date(2022, 1, 1)
        )
        assert result["exploding_feature"].isna().all()


class TestRunFeaturePipelineGrouping:
    """Tests for the per-user grouping path with a multi-purchase user."""

    def test_run_feature_pipeline_aggregates_multiple_purchases(
        self, sample_csv_path: Path, tmp_path: Path
    ) -> None:
        """A user with three purchases yields frequency_count 3, one output row."""
        csv_path = _write_multi_purchase_csv(sample_csv_path, tmp_path)
        result = run_feature_pipeline(csv_path, reference_date=date(2022, 1, 1))
        assert len(result) == 1
        row = result.iloc[0]
        assert row["frequency_count"] == 3
        assert row["product_diversity_count"] == 3

    def test_run_feature_pipeline_all_features_computed_for_grouped_user(
        self, sample_csv_path: Path, tmp_path: Path
    ) -> None:
        """Every one of the 23 features resolves to a non-null value."""
        csv_path = _write_multi_purchase_csv(sample_csv_path, tmp_path)
        result = run_feature_pipeline(csv_path, reference_date=date(2022, 1, 1))
        assert result[list(FEATURE_COLUMNS)].notna().all().all()
