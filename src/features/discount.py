"""Discount behavior feature computation functions.

Computes 3 user-level discount features: usage rate, average discount
rate (on discounted purchases), and total savings. All functions are
registered in the global feature registry via @feature_definition
(PRD § 9 E).
"""

from __future__ import annotations

import pandas as pd

from src.features.definitions import feature_definition


@feature_definition(
    name="discount_usage_rate",
    description="Fraction of purchases where a discount was applied",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 1.0),
)
def compute_discount_usage_rate(user_df: pd.DataFrame) -> float:
    """Compute the proportion of transactions with a discount applied.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Float in [0.0, 1.0], or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float(user_df["HasDiscountApplied"].mean())


@feature_definition(
    name="avg_discount_rate",
    description="Average discount percentage on transactions where a discount was used",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 1.0),
)
def compute_avg_discount_rate(user_df: pd.DataFrame) -> float:
    """Compute average DiscountRate over discounted transactions only.

    Excludes non-discounted transactions to avoid dilution of the
    average by 0.0 entries.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Mean DiscountRate over discounted rows, or 0.0 if none.
    """
    if user_df.empty:
        return 0.0
    discounted = user_df[user_df["HasDiscountApplied"]]
    if discounted.empty:
        return 0.0
    return float(discounted["DiscountRate"].mean())


@feature_definition(
    name="total_savings",
    description="Total monetary savings from discounts (sum of Price × DiscountRate)",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 1_000_000.0),
)
def compute_total_savings(user_df: pd.DataFrame) -> float:
    """Compute total savings as sum of unit price multiplied by discount rate.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Total savings in currency units, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float((user_df["Price"] * user_df["DiscountRate"]).sum())
