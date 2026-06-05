"""CSV loading and structural validation for the raw transaction dataset.

Responsibility: read the file, confirm expected columns are present, return
a raw DataFrame. Type transformations and value corrections are handled by
cleaner.py, not here.
"""

from pathlib import Path

import pandas as pd
from loguru import logger

# Complete set of column names expected in the source CSV (PRD § 6).
EXPECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "UserID",
        "UserName",
        "Age",
        "Gender",
        "Country",
        "SignUpDate",
        "ProductID",
        "ProductName",
        "Category",
        "Price",
        "PurchaseDate",
        "Quantity",
        "TotalAmount",
        "HasDiscountApplied",
        "DiscountRate",
        "ReviewScore",
        "ReviewText",
        "LastLogin",
        "SessionDuration",
        "DeviceType",
        "ReferralSource",
    }
)


def load_transactions(csv_path: Path) -> pd.DataFrame:
    """Load the raw transaction CSV into a DataFrame.

    Validates that all 21 expected columns are present. No type coercions are
    applied here — that is cleaner.py's job.

    Args:
        csv_path: Absolute or relative path to the source CSV file.

    Returns:
        DataFrame with all 21 raw columns, exactly as they appear in the file.

    Raises:
        FileNotFoundError: If ``csv_path`` does not exist on disk.
        ValueError: If any of the 21 expected columns are absent.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    logger.info("Loading transactions from {}", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Loaded {:,} rows × {:,} columns", len(df), len(df.columns))

    _validate_columns(df)
    return df


def _validate_columns(df: pd.DataFrame) -> None:
    """Raise ValueError if any expected columns are absent from the DataFrame.

    Args:
        df: DataFrame to validate.

    Raises:
        ValueError: Lists the missing column names alphabetically.
    """
    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in CSV: {sorted(missing)}")
