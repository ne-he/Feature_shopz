"""Unit tests for the ingestion module (loader, cleaner, schema).

Covers loader.py (CSV loading + column validation), cleaner.py
(ReviewScore clipping, date parsing, copy semantics), and schema.py
(Pydantic row-level validation).

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from src.ingestion.cleaner import clean_transactions
from src.ingestion.loader import load_transactions
from src.ingestion.schema import RawTransactionRow

# ---------------------------------------------------------------------------
# loader.py
# ---------------------------------------------------------------------------


class TestLoadTransactions:
    """Tests for load_transactions()."""

    def test_load_transactions_valid_csv_returns_dataframe(
        self, sample_csv_path: Path
    ) -> None:
        """Happy-path: valid CSV produces a non-empty DataFrame."""
        df = load_transactions(sample_csv_path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10

    def test_load_transactions_valid_csv_has_21_columns(
        self, sample_csv_path: Path
    ) -> None:
        """All 21 columns must be present after loading."""
        df = load_transactions(sample_csv_path)
        assert len(df.columns) == 21
        assert "UserID" in df.columns
        assert "ReviewScore" in df.columns

    def test_load_transactions_missing_file_raises_file_not_found(
        self, tmp_path: Path
    ) -> None:
        """Non-existent path raises FileNotFoundError (not a generic OSError)."""
        with pytest.raises(FileNotFoundError, match="Dataset not found"):
            load_transactions(tmp_path / "does_not_exist.csv")

    def test_load_transactions_missing_columns_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        """CSV with fewer columns raises ValueError listing the missing ones."""
        csv_path = tmp_path / "incomplete.csv"
        csv_path.write_text("UserID,UserName\n1,User_1\n")
        with pytest.raises(ValueError, match="Missing columns"):
            load_transactions(csv_path)


# ---------------------------------------------------------------------------
# cleaner.py
# ---------------------------------------------------------------------------


class TestCleanTransactions:
    """Tests for clean_transactions()."""

    def test_clean_transactions_clips_review_score_below_minimum(
        self, sample_df: pd.DataFrame
    ) -> None:
        """ReviewScore values < 1.0 (rows 4 and 10 in fixture) are clipped to 1.0."""
        df_clean = clean_transactions(sample_df)
        assert (df_clean["ReviewScore"] >= 1.0).all()

    def test_clean_transactions_clips_review_score_above_maximum(
        self, sample_df: pd.DataFrame
    ) -> None:
        """ReviewScore values > 5.0 (rows 5 and 9 in fixture) are clipped to 5.0."""
        df_clean = clean_transactions(sample_df)
        assert (df_clean["ReviewScore"] <= 5.0).all()

    def test_clean_transactions_parses_purchase_date_to_date_type(
        self, sample_df: pd.DataFrame
    ) -> None:
        """PurchaseDate is converted from string to datetime.date objects."""
        df_clean = clean_transactions(sample_df)
        assert isinstance(df_clean["PurchaseDate"].iloc[0], date)

    def test_clean_transactions_parses_last_login_to_datetime64(
        self, sample_df: pd.DataFrame
    ) -> None:
        """LastLogin is parsed to pandas datetime64 (Timestamp)."""
        df_clean = clean_transactions(sample_df)
        assert pd.api.types.is_datetime64_any_dtype(df_clean["LastLogin"])

    def test_clean_transactions_does_not_mutate_input(
        self, sample_df: pd.DataFrame
    ) -> None:
        """clean_transactions must return a copy; original must be unchanged."""
        original_scores = sample_df["ReviewScore"].tolist()
        clean_transactions(sample_df)
        assert sample_df["ReviewScore"].tolist() == original_scores

    def test_clean_transactions_returns_same_row_count(
        self, sample_df: pd.DataFrame
    ) -> None:
        """Cleaning must not drop or duplicate rows."""
        df_clean = clean_transactions(sample_df)
        assert len(df_clean) == len(sample_df)


# ---------------------------------------------------------------------------
# schema.py — Pydantic model
# ---------------------------------------------------------------------------

_VALID_ROW_DATA: dict[str, object] = {
    "UserID": 1,
    "UserName": "User_1",
    "Age": 25,
    "Gender": "Male",
    "Country": "USA",
    "SignUpDate": date(2020, 3, 15),
    "ProductID": 1001,
    "ProductName": "Laptop",
    "Category": "Electronics",
    "Price": 999.99,
    "PurchaseDate": date(2021, 6, 10),
    "Quantity": 1,
    "TotalAmount": 999.99,
    "HasDiscountApplied": False,
    "DiscountRate": 0.0,
    "ReviewScore": 4.5,
    "ReviewText": "Excellent",
    "LastLogin": datetime(2024, 1, 15, 10, 30),
    "SessionDuration": 45.0,
    "DeviceType": "Desktop",
    "ReferralSource": "Organic Search",
}


class TestRawTransactionRow:
    """Tests for the Pydantic RawTransactionRow model."""

    def test_raw_transaction_row_valid_data_creates_model(self) -> None:
        """Valid row data constructs the model without errors."""
        row = RawTransactionRow(**_VALID_ROW_DATA)  # type: ignore[arg-type]
        assert row.UserID == 1
        assert row.ReviewScore == 4.5

    def test_raw_transaction_row_invalid_gender_raises_validation_error(
        self,
    ) -> None:
        """Gender values outside the documented set are rejected."""
        bad = {**_VALID_ROW_DATA, "Gender": "Unknown"}
        with pytest.raises(ValidationError):
            RawTransactionRow(**bad)  # type: ignore[arg-type]

    def test_raw_transaction_row_invalid_category_raises_validation_error(
        self,
    ) -> None:
        """Category values outside the documented set are rejected."""
        bad = {**_VALID_ROW_DATA, "Category": "Furniture"}
        with pytest.raises(ValidationError):
            RawTransactionRow(**bad)  # type: ignore[arg-type]
