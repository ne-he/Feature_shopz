"""Data cleaning and type-coercion for raw transaction data.

Handles the documented quirks from PRD § 6:
  - ReviewScore: values outside [1.0, 5.0] are clipped (synthetic noise).
  - SignUpDate / PurchaseDate: string → datetime.date.
  - LastLogin: string → datetime.datetime (pandas Timestamp).
  - HasDiscountApplied: string "True"/"False" → Python bool when needed.
"""

import pandas as pd
from loguru import logger

REVIEW_SCORE_MIN: float = 1.0
REVIEW_SCORE_MAX: float = 5.0


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all cleaning transformations to the raw transactions DataFrame.

    The input DataFrame is never modified in place — a copy is returned.

    Args:
        df: Raw DataFrame as returned by ``loader.load_transactions()``.

    Returns:
        New DataFrame with corrected dtypes and clipped ReviewScore values.
    """
    logger.info("Cleaning {:,} rows", len(df))
    df = df.copy()
    df = _clip_review_score(df)
    df = _parse_dates(df)
    df = _parse_booleans(df)
    logger.info("Cleaning complete")
    return df


def _clip_review_score(df: pd.DataFrame) -> pd.DataFrame:
    """Clip ReviewScore to [1.0, 5.0]; log how many rows were out of range."""
    out_of_range = (
        (df["ReviewScore"] < REVIEW_SCORE_MIN) | (df["ReviewScore"] > REVIEW_SCORE_MAX)
    ).sum()
    if out_of_range > 0:
        logger.warning(
            "Clipping {:,} ReviewScore values outside [{}, {}]",
            out_of_range,
            REVIEW_SCORE_MIN,
            REVIEW_SCORE_MAX,
        )
    df["ReviewScore"] = df["ReviewScore"].clip(lower=REVIEW_SCORE_MIN, upper=REVIEW_SCORE_MAX)
    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse date and datetime columns from string to proper Python types."""
    df["SignUpDate"] = pd.to_datetime(df["SignUpDate"]).dt.date
    df["PurchaseDate"] = pd.to_datetime(df["PurchaseDate"]).dt.date
    df["LastLogin"] = pd.to_datetime(df["LastLogin"])
    return df


def _parse_booleans(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce HasDiscountApplied to bool (CSV may load it as object/string)."""
    if df["HasDiscountApplied"].dtype == object:
        df["HasDiscountApplied"] = df["HasDiscountApplied"].map(
            {"True": True, "False": False}
        )
    return df
