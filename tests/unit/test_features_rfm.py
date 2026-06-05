"""Unit tests for RFM feature computation functions.

Tests each compute function with: a typical multi-row user, a single-row
user, and an empty DataFrame (edge case).

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from datetime import date
from typing import Any

import pandas as pd
import pytest

from src.features.rfm import (
    compute_frequency_count,
    compute_monetary_avg_per_purchase,
    compute_monetary_max,
    compute_monetary_total,
    compute_recency_days,
)

REF_DATE = date(2022, 1, 1)
EMPTY_DF = pd.DataFrame(
    {"PurchaseDate": pd.Series([], dtype=object), "TotalAmount": pd.Series([], dtype=float)}
)


def _make_df(**overrides: Any) -> pd.DataFrame:
    """Build a minimal per-user transaction DataFrame."""
    data: dict[str, list[Any]] = {
        "PurchaseDate": [date(2021, 6, 15), date(2021, 9, 1), date(2021, 12, 20)],
        "TotalAmount": [100.0, 250.0, 75.50],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# recency_days
# ---------------------------------------------------------------------------


class TestComputeRecencyDays:
    """Tests for compute_recency_days."""

    def test_compute_recency_days_typical_user_returns_correct_days(self) -> None:
        """Recency is days from ref_date to the latest PurchaseDate."""
        df = _make_df()
        result = compute_recency_days(df, REF_DATE)
        # Latest purchase: 2021-12-20; ref: 2022-01-01 → 12 days
        assert result == 12

    def test_compute_recency_days_empty_dataframe_returns_negative_one(self) -> None:
        """Empty user DataFrame returns sentinel -1."""
        result = compute_recency_days(EMPTY_DF, REF_DATE)
        assert result == -1

    def test_compute_recency_days_same_day_returns_zero(self) -> None:
        """Purchase on the reference date yields 0 recency days."""
        df = pd.DataFrame({"PurchaseDate": [REF_DATE], "TotalAmount": [50.0]})
        result = compute_recency_days(df, REF_DATE)
        assert result == 0


# ---------------------------------------------------------------------------
# frequency_count
# ---------------------------------------------------------------------------


class TestComputeFrequencyCount:
    """Tests for compute_frequency_count."""

    def test_compute_frequency_count_typical_user_returns_row_count(self) -> None:
        """Returns the number of rows in user_df."""
        df = _make_df()
        assert compute_frequency_count(df) == 3

    def test_compute_frequency_count_empty_dataframe_returns_zero(self) -> None:
        """Empty DataFrame → 0 transactions."""
        assert compute_frequency_count(EMPTY_DF) == 0

    def test_compute_frequency_count_single_row_returns_one(self) -> None:
        """Single-purchase user returns 1."""
        df = pd.DataFrame({"PurchaseDate": [date(2021, 1, 1)], "TotalAmount": [50.0]})
        assert compute_frequency_count(df) == 1


# ---------------------------------------------------------------------------
# monetary_total
# ---------------------------------------------------------------------------


class TestComputeMonetaryTotal:
    """Tests for compute_monetary_total."""

    def test_compute_monetary_total_typical_user_sums_correctly(self) -> None:
        """Sum of 100 + 250 + 75.50 = 425.50."""
        df = _make_df()
        assert compute_monetary_total(df) == pytest.approx(425.50)

    def test_compute_monetary_total_empty_dataframe_returns_zero(self) -> None:
        """Empty input → 0.0."""
        assert compute_monetary_total(EMPTY_DF) == 0.0


# ---------------------------------------------------------------------------
# monetary_avg_per_purchase
# ---------------------------------------------------------------------------


class TestComputeMonetaryAvgPerPurchase:
    """Tests for compute_monetary_avg_per_purchase."""

    def test_compute_monetary_avg_typical_user_returns_mean(self) -> None:
        """425.50 / 3 ≈ 141.83."""
        df = _make_df()
        assert compute_monetary_avg_per_purchase(df) == pytest.approx(141.833, rel=1e-3)

    def test_compute_monetary_avg_empty_dataframe_returns_zero(self) -> None:
        """Empty input → 0.0."""
        assert compute_monetary_avg_per_purchase(EMPTY_DF) == 0.0

    def test_compute_monetary_avg_single_row_equals_total(self) -> None:
        """One transaction: average equals that transaction's value."""
        df = pd.DataFrame({"PurchaseDate": [date(2021, 5, 1)], "TotalAmount": [999.99]})
        assert compute_monetary_avg_per_purchase(df) == pytest.approx(999.99)


# ---------------------------------------------------------------------------
# monetary_max
# ---------------------------------------------------------------------------


class TestComputeMonetaryMax:
    """Tests for compute_monetary_max."""

    def test_compute_monetary_max_typical_user_returns_largest(self) -> None:
        """Max of 100, 250, 75.50 is 250."""
        df = _make_df()
        assert compute_monetary_max(df) == pytest.approx(250.0)

    def test_compute_monetary_max_empty_dataframe_returns_zero(self) -> None:
        """Empty input → 0.0."""
        assert compute_monetary_max(EMPTY_DF) == 0.0
