"""Unit tests for discount behavior feature computation functions.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

import pandas as pd
import pytest

from src.features.discount import (
    compute_avg_discount_rate,
    compute_discount_usage_rate,
    compute_total_savings,
)

_EMPTY_DF = pd.DataFrame(
    {
        "HasDiscountApplied": pd.Series([], dtype=bool),
        "DiscountRate": pd.Series([], dtype=float),
        "Price": pd.Series([], dtype=float),
    }
)

_SAMPLE_DF = pd.DataFrame(
    {
        "HasDiscountApplied": [True, False, True, False],
        "DiscountRate": [0.20, 0.0, 0.10, 0.0],
        "Price": [100.0, 200.0, 50.0, 80.0],
    }
)


class TestComputeDiscountUsageRate:
    """Tests for compute_discount_usage_rate."""

    def test_compute_discount_usage_rate_typical_returns_fraction(self) -> None:
        """2 out of 4 transactions discounted → rate = 0.5."""
        assert compute_discount_usage_rate(_SAMPLE_DF) == pytest.approx(0.5)

    def test_compute_discount_usage_rate_no_discounts_returns_zero(self) -> None:
        """All False → rate = 0.0."""
        df = pd.DataFrame(
            {
                "HasDiscountApplied": [False, False],
                "DiscountRate": [0.0, 0.0],
                "Price": [10.0, 20.0],
            }
        )
        assert compute_discount_usage_rate(df) == 0.0

    def test_compute_discount_usage_rate_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_discount_usage_rate(_EMPTY_DF) == 0.0


class TestComputeAvgDiscountRate:
    """Tests for compute_avg_discount_rate."""

    def test_compute_avg_discount_rate_typical_returns_mean_over_discounted(self) -> None:
        """Discounted rows: rates 0.20 and 0.10 → mean = 0.15."""
        assert compute_avg_discount_rate(_SAMPLE_DF) == pytest.approx(0.15)

    def test_compute_avg_discount_rate_no_discounts_returns_zero(self) -> None:
        """No discounted rows → 0.0."""
        df = pd.DataFrame(
            {
                "HasDiscountApplied": [False, False],
                "DiscountRate": [0.0, 0.0],
                "Price": [10.0, 20.0],
            }
        )
        assert compute_avg_discount_rate(df) == 0.0

    def test_compute_avg_discount_rate_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_avg_discount_rate(_EMPTY_DF) == 0.0


class TestComputeTotalSavings:
    """Tests for compute_total_savings."""

    def test_compute_total_savings_typical_returns_correct_sum(self) -> None:
        """Savings: 100*0.20 + 200*0.0 + 50*0.10 + 80*0.0 = 20 + 5 = 25."""
        assert compute_total_savings(_SAMPLE_DF) == pytest.approx(25.0)

    def test_compute_total_savings_no_discounts_returns_zero(self) -> None:
        """All DiscountRate=0 → total savings = 0."""
        df = pd.DataFrame(
            {"HasDiscountApplied": [False], "DiscountRate": [0.0], "Price": [500.0]}
        )
        assert compute_total_savings(df) == 0.0

    def test_compute_total_savings_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_total_savings(_EMPTY_DF) == 0.0
