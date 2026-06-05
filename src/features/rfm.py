"""RFM (Recency, Frequency, Monetary) feature computation functions.

Computes 5 user-level features from a single user's transaction history.
Each function is decorated with @feature_definition, which attaches
metadata and registers it in the global feature registry (PRD § 9 A).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.features.definitions import feature_definition


@feature_definition(
    name="recency_days",
    description="Days since the user's most recent purchase",
    data_type="int",
    owner="nehemiah",
    valid_range=(0.0, 3650.0),
    null_handling="return_negative_one_for_empty",
)
def compute_recency_days(user_df: pd.DataFrame, reference_date: date) -> int:
    """Compute days between reference_date and the user's last purchase.

    Args:
        user_df: All transaction rows for one user (cleaned).
        reference_date: The anchor 'today' date for recency calculation.

    Returns:
        Integer days since last purchase, or -1 if user_df is empty.
    """
    if user_df.empty:
        return -1
    last_purchase: date = user_df["PurchaseDate"].max()
    return (reference_date - last_purchase).days


@feature_definition(
    name="frequency_count",
    description="Total number of purchase transactions made by the user",
    data_type="int",
    owner="nehemiah",
    valid_range=(0.0, 100_000.0),
)
def compute_frequency_count(user_df: pd.DataFrame) -> int:
    """Count total purchase transactions for the user.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Number of rows in the DataFrame.
    """
    return len(user_df)


@feature_definition(
    name="monetary_total",
    description="Sum of all transaction amounts (lifetime spend)",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 1_000_000.0),
)
def compute_monetary_total(user_df: pd.DataFrame) -> float:
    """Sum all TotalAmount values for the user.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Total lifetime spend, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float(user_df["TotalAmount"].sum())


@feature_definition(
    name="monetary_avg_per_purchase",
    description="Average order value per transaction",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 100_000.0),
)
def compute_monetary_avg_per_purchase(user_df: pd.DataFrame) -> float:
    """Compute mean TotalAmount across all user transactions.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Mean transaction value, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float(user_df["TotalAmount"].mean())


@feature_definition(
    name="monetary_max",
    description="Largest single transaction amount in the user's history",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 100_000.0),
)
def compute_monetary_max(user_df: pd.DataFrame) -> float:
    """Find the maximum TotalAmount in the user's transaction history.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Maximum single transaction value, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float(user_df["TotalAmount"].max())
