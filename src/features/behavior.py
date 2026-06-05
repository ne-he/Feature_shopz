"""Behavioral feature computation functions.

Computes 5 user-level behavioral features from a single user's
transaction history: preferred modalities (category, device, referral)
and diversity counts (category, product). All functions are registered
in the global feature registry via @feature_definition (PRD § 9 B).
"""

from __future__ import annotations

import pandas as pd

from src.features.definitions import feature_definition


def _most_frequent(series: pd.Series[str]) -> str:
    """Return the most-frequent string value; empty string for empty input."""
    if series.empty:
        return ""
    return str(series.value_counts().idxmax())


@feature_definition(
    name="preferred_category",
    description="Product category purchased most often by the user",
    data_type="str",
    owner="nehemiah",
)
def compute_preferred_category(user_df: pd.DataFrame) -> str:
    """Return the category appearing most in the user's transactions.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Most-frequent Category value, or '' for empty input.
    """
    return _most_frequent(user_df["Category"])


@feature_definition(
    name="preferred_device",
    description="Device type used most often by the user",
    data_type="str",
    owner="nehemiah",
)
def compute_preferred_device(user_df: pd.DataFrame) -> str:
    """Return the device type appearing most in the user's transactions.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Most-frequent DeviceType value, or '' for empty input.
    """
    return _most_frequent(user_df["DeviceType"])


@feature_definition(
    name="preferred_referral",
    description="Referral source that drove the most of the user's purchases",
    data_type="str",
    owner="nehemiah",
)
def compute_preferred_referral(user_df: pd.DataFrame) -> str:
    """Return the referral source appearing most in the user's transactions.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Most-frequent ReferralSource value, or '' for empty input.
    """
    return _most_frequent(user_df["ReferralSource"])


@feature_definition(
    name="category_diversity_count",
    description="Number of distinct product categories ever purchased",
    data_type="int",
    owner="nehemiah",
    valid_range=(0.0, 10.0),
)
def compute_category_diversity_count(user_df: pd.DataFrame) -> int:
    """Count distinct product categories in the user's purchase history.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Number of unique Category values.
    """
    return int(user_df["Category"].nunique())


@feature_definition(
    name="product_diversity_count",
    description="Number of distinct products (by ProductID) ever purchased",
    data_type="int",
    owner="nehemiah",
    valid_range=(0.0, 100_000.0),
)
def compute_product_diversity_count(user_df: pd.DataFrame) -> int:
    """Count distinct ProductIDs in the user's purchase history.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Number of unique ProductID values.
    """
    return int(user_df["ProductID"].nunique())
