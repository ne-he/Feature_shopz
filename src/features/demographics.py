"""Demographic feature computation functions.

Extracts 3 static user-level demographic attributes from a single user's
transaction history. These values are the same across all rows for a
given user; this module reads the first row. All functions are
registered in the global feature registry via @feature_definition
(PRD § 9 F).
"""

from __future__ import annotations

import pandas as pd

from src.features.definitions import feature_definition


@feature_definition(
    name="age",
    description="User age in years",
    data_type="int",
    owner="nehemiah",
    valid_range=(18.0, 69.0),
    refresh_cadence="static",
    null_handling="return_negative_one_for_empty",
)
def compute_age(user_df: pd.DataFrame) -> int:
    """Extract user age from the first transaction row.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Age in years, or -1 for empty input.
    """
    if user_df.empty:
        return -1
    return int(user_df["Age"].iloc[0])


@feature_definition(
    name="country",
    description="User's registered country",
    data_type="str",
    owner="nehemiah",
    refresh_cadence="static",
    null_handling="return_empty_string_for_empty",
)
def compute_country(user_df: pd.DataFrame) -> str:
    """Extract user country from the first transaction row.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Country string, or '' for empty input.
    """
    if user_df.empty:
        return ""
    return str(user_df["Country"].iloc[0])


@feature_definition(
    name="gender",
    description="User's self-reported gender",
    data_type="str",
    owner="nehemiah",
    refresh_cadence="static",
    null_handling="return_empty_string_for_empty",
)
def compute_gender(user_df: pd.DataFrame) -> str:
    """Extract user gender from the first transaction row.

    Args:
        user_df: All transaction rows for one user (cleaned).

    Returns:
        Gender string, or '' for empty input.
    """
    if user_df.empty:
        return ""
    return str(user_df["Gender"].iloc[0])
