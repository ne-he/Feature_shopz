"""Temporal feature computation functions.

Computes 3 user-level time-based features: days since signup, 30-day
activity flag, and purchase velocity. All functions are registered in
the global feature registry via @feature_definition (PRD § 9 D).

Note on synthetic data: LastLogin timestamps in the dataset are dated
2024, while PurchaseDate spans 2021–2022. is_active_30d will therefore
return False for all users when reference_date is today (2026). This is
an expected quirk of the synthetic dataset; the logic is correct.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.features.definitions import feature_definition


@feature_definition(
    name="days_since_signup",
    description="Days from the user's signup date to their most recent purchase",
    data_type="int",
    owner="nehemiah",
    valid_range=(0.0, 3650.0),
    null_handling="return_negative_one_for_empty",
)
def compute_days_since_signup(user_df: pd.DataFrame) -> int:
    """Compute tenure in days from SignUpDate to the last PurchaseDate.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Integer days between signup and last purchase, -1 if empty.
    """
    if user_df.empty:
        return -1
    signup: date = user_df["SignUpDate"].iloc[0]
    last_purchase: date = user_df["PurchaseDate"].max()
    return (last_purchase - signup).days


@feature_definition(
    name="is_active_30d",
    description="True if the user's last login is within 30 days of reference_date",
    data_type="bool",
    owner="nehemiah",
)
def compute_is_active_30d(user_df: pd.DataFrame, reference_date: date) -> bool:
    """Check whether the user logged in within the last 30 days.

    Args:
        user_df: All transaction rows for one user (cleaned).
        reference_date: The anchor 'today' date for the activity window.

    Returns:
        True if last login is >= (reference_date - 30 days), else False.
    """
    if user_df.empty:
        return False
    cutoff = reference_date - timedelta(days=30)
    last_login: pd.Timestamp = user_df["LastLogin"].max()
    return bool(last_login.date() >= cutoff)


@feature_definition(
    name="purchase_velocity",
    description="Average number of purchases per calendar month with activity",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 1000.0),
)
def compute_purchase_velocity(user_df: pd.DataFrame) -> float:
    """Compute purchases per active calendar month.

    An active month is any (year, month) pair that contains at least
    one purchase. Velocity = total_purchases / active_months.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Float purchases-per-active-month, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    active_months = int(
        user_df["PurchaseDate"].apply(lambda d: (d.year, d.month)).nunique()
    )
    return float(len(user_df)) / max(1, active_months)
