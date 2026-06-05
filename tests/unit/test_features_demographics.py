"""Unit tests for demographic feature computation functions.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

import pandas as pd

from src.features.demographics import compute_age, compute_country, compute_gender

_EMPTY_DF = pd.DataFrame(
    {
        "Age": pd.Series([], dtype=int),
        "Country": pd.Series([], dtype=str),
        "Gender": pd.Series([], dtype=str),
    }
)

_SAMPLE_DF = pd.DataFrame(
    {
        "Age": [28, 28, 28],
        "Country": ["USA", "USA", "USA"],
        "Gender": ["Female", "Female", "Female"],
    }
)


class TestComputeAge:
    """Tests for compute_age."""

    def test_compute_age_typical_user_returns_age(self) -> None:
        """Returns age from the first row."""
        assert compute_age(_SAMPLE_DF) == 28

    def test_compute_age_empty_dataframe_returns_negative_one(self) -> None:
        """Empty input returns sentinel -1."""
        assert compute_age(_EMPTY_DF) == -1

    def test_compute_age_single_row_returns_that_age(self) -> None:
        """Single-row DataFrame returns the one row's age."""
        df = pd.DataFrame({"Age": [42], "Country": ["UK"], "Gender": ["Male"]})
        assert compute_age(df) == 42


class TestComputeCountry:
    """Tests for compute_country."""

    def test_compute_country_typical_user_returns_country(self) -> None:
        """Returns country from the first row."""
        assert compute_country(_SAMPLE_DF) == "USA"

    def test_compute_country_empty_dataframe_returns_empty_string(self) -> None:
        """Empty input returns ''."""
        assert compute_country(_EMPTY_DF) == ""

    def test_compute_country_value_is_string(self) -> None:
        """Return type is always str (not numpy type)."""
        assert isinstance(compute_country(_SAMPLE_DF), str)


class TestComputeGender:
    """Tests for compute_gender."""

    def test_compute_gender_typical_user_returns_gender(self) -> None:
        """Returns gender from the first row."""
        assert compute_gender(_SAMPLE_DF) == "Female"

    def test_compute_gender_empty_dataframe_returns_empty_string(self) -> None:
        """Empty input returns ''."""
        assert compute_gender(_EMPTY_DF) == ""

    def test_compute_gender_value_is_string(self) -> None:
        """Return type is always str (not numpy type)."""
        assert isinstance(compute_gender(_SAMPLE_DF), str)
