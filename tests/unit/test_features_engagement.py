"""Unit tests for engagement feature computation functions.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

import pandas as pd
import pytest

from src.features.engagement import (
    compute_avg_review_score,
    compute_avg_session_duration,
    compute_positive_review_ratio,
    compute_total_reviews_given,
)

_EMPTY_DF = pd.DataFrame(
    {
        "SessionDuration": pd.Series([], dtype=float),
        "ReviewScore": pd.Series([], dtype=float),
    }
)

_SAMPLE_DF = pd.DataFrame(
    {
        "SessionDuration": [30.0, 60.0, 45.0],
        "ReviewScore": [5.0, 3.0, 4.0],
    }
)


class TestComputeAvgSessionDuration:
    """Tests for compute_avg_session_duration."""

    def test_compute_avg_session_duration_typical_user_returns_mean(self) -> None:
        """Mean of 30, 60, 45 is 45.0."""
        assert compute_avg_session_duration(_SAMPLE_DF) == pytest.approx(45.0)

    def test_compute_avg_session_duration_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_avg_session_duration(_EMPTY_DF) == 0.0

    def test_compute_avg_session_duration_single_row_returns_that_value(self) -> None:
        """Single session → average equals that session's duration."""
        df = pd.DataFrame({"SessionDuration": [90.0], "ReviewScore": [4.0]})
        assert compute_avg_session_duration(df) == pytest.approx(90.0)


class TestComputeAvgReviewScore:
    """Tests for compute_avg_review_score."""

    def test_compute_avg_review_score_typical_user_returns_mean(self) -> None:
        """Mean of 5.0, 3.0, 4.0 is 4.0."""
        assert compute_avg_review_score(_SAMPLE_DF) == pytest.approx(4.0)

    def test_compute_avg_review_score_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_avg_review_score(_EMPTY_DF) == 0.0


class TestComputeTotalReviewsGiven:
    """Tests for compute_total_reviews_given."""

    def test_compute_total_reviews_given_typical_user_returns_row_count(self) -> None:
        """Three transactions → three reviews."""
        assert compute_total_reviews_given(_SAMPLE_DF) == 3

    def test_compute_total_reviews_given_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0."""
        assert compute_total_reviews_given(_EMPTY_DF) == 0


class TestComputePositiveReviewRatio:
    """Tests for compute_positive_review_ratio."""

    def test_compute_positive_review_ratio_typical_user_returns_fraction(self) -> None:
        """Scores 5.0, 3.0, 4.0 → 2 out of 3 positive → ratio ≈ 0.667."""
        result = compute_positive_review_ratio(_SAMPLE_DF)
        assert result == pytest.approx(2 / 3, rel=1e-3)

    def test_compute_positive_review_ratio_all_low_returns_zero(self) -> None:
        """All scores below 4.0 → ratio = 0.0."""
        df = pd.DataFrame({"ReviewScore": [1.0, 2.0, 3.0]})
        assert compute_positive_review_ratio(df) == 0.0

    def test_compute_positive_review_ratio_all_high_returns_one(self) -> None:
        """All scores >= 4.0 → ratio = 1.0."""
        df = pd.DataFrame({"ReviewScore": [4.0, 5.0, 4.5]})
        assert compute_positive_review_ratio(df) == pytest.approx(1.0)

    def test_compute_positive_review_ratio_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_positive_review_ratio(_EMPTY_DF) == 0.0
