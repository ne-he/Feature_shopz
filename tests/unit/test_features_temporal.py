"""Unit tests for temporal feature computation functions.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from src.features.temporal import (
    compute_days_since_signup,
    compute_is_active_30d,
    compute_purchase_velocity,
)

REF_DATE = date(2022, 1, 1)

_EMPTY_DF = pd.DataFrame(
    {
        "SignUpDate": pd.Series([], dtype=object),
        "PurchaseDate": pd.Series([], dtype=object),
        "LastLogin": pd.Series([], dtype="datetime64[ns]"),
    }
)


def _make_df(
    signup: date,
    purchases: list[date],
    last_login: datetime,
) -> pd.DataFrame:
    """Build a minimal per-user DataFrame for temporal tests."""
    return pd.DataFrame(
        {
            "SignUpDate": [signup] * len(purchases),
            "PurchaseDate": purchases,
            "LastLogin": pd.to_datetime([last_login] * len(purchases)),
        }
    )


class TestComputeDaysSinceSignup:
    """Tests for compute_days_since_signup."""

    def test_compute_days_since_signup_typical_user_returns_correct_days(self) -> None:
        """Signup 2021-01-01, last purchase 2021-12-31 → 364 days."""
        df = _make_df(
            signup=date(2021, 1, 1),
            purchases=[date(2021, 6, 1), date(2021, 12, 31)],
            last_login=datetime(2024, 1, 1),
        )
        assert compute_days_since_signup(df) == 364

    def test_compute_days_since_signup_empty_dataframe_returns_negative_one(self) -> None:
        """Empty user_df returns sentinel -1."""
        assert compute_days_since_signup(_EMPTY_DF) == -1

    def test_compute_days_since_signup_same_day_returns_zero(self) -> None:
        """Signup and purchase on same day → 0 days."""
        df = _make_df(
            signup=date(2021, 5, 10),
            purchases=[date(2021, 5, 10)],
            last_login=datetime(2024, 1, 1),
        )
        assert compute_days_since_signup(df) == 0


class TestComputeIsActive30d:
    """Tests for compute_is_active_30d."""

    def test_compute_is_active_30d_recent_login_returns_true(self) -> None:
        """Login 10 days before reference_date → True."""
        login = datetime(REF_DATE.year, REF_DATE.month, REF_DATE.day) - timedelta(days=10)
        df = _make_df(signup=date(2020, 1, 1), purchases=[date(2021, 6, 1)], last_login=login)
        assert compute_is_active_30d(df, REF_DATE) is True

    def test_compute_is_active_30d_old_login_returns_false(self) -> None:
        """Login 60 days before reference_date → False."""
        login = datetime(REF_DATE.year, REF_DATE.month, REF_DATE.day) - timedelta(days=60)
        df = _make_df(signup=date(2020, 1, 1), purchases=[date(2021, 6, 1)], last_login=login)
        assert compute_is_active_30d(df, REF_DATE) is False

    def test_compute_is_active_30d_empty_dataframe_returns_false(self) -> None:
        """Empty user_df returns False."""
        assert compute_is_active_30d(_EMPTY_DF, REF_DATE) is False


class TestComputePurchaseVelocity:
    """Tests for compute_purchase_velocity."""

    def test_compute_purchase_velocity_all_same_month_returns_count(self) -> None:
        """3 purchases in 1 month → velocity = 3.0."""
        df = _make_df(
            signup=date(2021, 1, 1),
            purchases=[date(2021, 6, 1), date(2021, 6, 10), date(2021, 6, 20)],
            last_login=datetime(2024, 1, 1),
        )
        assert compute_purchase_velocity(df) == pytest.approx(3.0)

    def test_compute_purchase_velocity_different_months_returns_fraction(self) -> None:
        """3 purchases across 3 different months → velocity = 1.0."""
        df = _make_df(
            signup=date(2021, 1, 1),
            purchases=[date(2021, 6, 1), date(2021, 7, 1), date(2021, 8, 1)],
            last_login=datetime(2024, 1, 1),
        )
        assert compute_purchase_velocity(df) == pytest.approx(1.0)

    def test_compute_purchase_velocity_empty_dataframe_returns_zero(self) -> None:
        """Empty input returns 0.0."""
        assert compute_purchase_velocity(_EMPTY_DF) == 0.0
