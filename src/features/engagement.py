"""Engagement feature computation functions.

Computes 4 user-level engagement features from a single user's
transaction history: session duration, review scores, review count,
and positive review ratio. All functions are registered in the global
feature registry via @feature_definition (PRD § 9 C).
"""

from __future__ import annotations

import pandas as pd

from src.features.definitions import feature_definition


@feature_definition(
    name="avg_session_duration",
    description="Average session duration in minutes across all user sessions",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 120.0),
)
def compute_avg_session_duration(user_df: pd.DataFrame) -> float:
    """Compute mean SessionDuration across all user transactions.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Mean session duration in minutes, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float(user_df["SessionDuration"].mean())


@feature_definition(
    name="avg_review_score",
    description="Average review score (1–5) given by the user",
    data_type="float",
    owner="nehemiah",
    valid_range=(1.0, 5.0),
)
def compute_avg_review_score(user_df: pd.DataFrame) -> float:
    """Compute mean ReviewScore across all user transactions.

    ReviewScore is expected to be clipped to [1.0, 5.0] by the cleaner
    before this function is called.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Mean review score, or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float(user_df["ReviewScore"].mean())


@feature_definition(
    name="total_reviews_given",
    description="Total number of reviews written by the user",
    data_type="int",
    owner="nehemiah",
    valid_range=(0.0, 100_000.0),
)
def compute_total_reviews_given(user_df: pd.DataFrame) -> int:
    """Count reviews submitted by the user (one per transaction).

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Number of rows in the DataFrame.
    """
    return len(user_df)


@feature_definition(
    name="positive_review_ratio",
    description="Fraction of reviews with a score of 4 or higher",
    data_type="float",
    owner="nehemiah",
    valid_range=(0.0, 1.0),
)
def compute_positive_review_ratio(user_df: pd.DataFrame) -> float:
    """Compute the proportion of reviews with ReviewScore >= 4.0.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Float in [0.0, 1.0], or 0.0 for empty input.
    """
    if user_df.empty:
        return 0.0
    return float((user_df["ReviewScore"] >= 4.0).mean())
