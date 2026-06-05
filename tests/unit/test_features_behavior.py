"""Unit tests for behavioral feature computation functions.

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

import pandas as pd

from src.features.behavior import (
    compute_category_diversity_count,
    compute_preferred_category,
    compute_preferred_device,
    compute_preferred_referral,
    compute_product_diversity_count,
)

_EMPTY_DF = pd.DataFrame(
    {
        "Category": pd.Series([], dtype=str),
        "DeviceType": pd.Series([], dtype=str),
        "ReferralSource": pd.Series([], dtype=str),
        "ProductID": pd.Series([], dtype=int),
    }
)

_SAMPLE_DF = pd.DataFrame(
    {
        "Category": ["Electronics", "Electronics", "Books", "Electronics"],
        "DeviceType": ["Mobile", "Desktop", "Mobile", "Mobile"],
        "ReferralSource": ["Organic Search", "Ad Campaign", "Organic Search", "Organic Search"],
        "ProductID": [1001, 1002, 1003, 1001],
    }
)


class TestComputePreferredCategory:
    """Tests for compute_preferred_category."""

    def test_compute_preferred_category_typical_returns_most_frequent(self) -> None:
        """Electronics appears 3 times vs Books 1 time."""
        assert compute_preferred_category(_SAMPLE_DF) == "Electronics"

    def test_compute_preferred_category_empty_returns_empty_string(self) -> None:
        """Empty user_df returns ''."""
        assert compute_preferred_category(_EMPTY_DF) == ""


class TestComputePreferredDevice:
    """Tests for compute_preferred_device."""

    def test_compute_preferred_device_typical_returns_most_frequent(self) -> None:
        """Mobile appears 3 times vs Desktop 1 time."""
        assert compute_preferred_device(_SAMPLE_DF) == "Mobile"

    def test_compute_preferred_device_empty_returns_empty_string(self) -> None:
        """Empty user_df returns ''."""
        assert compute_preferred_device(_EMPTY_DF) == ""


class TestComputePreferredReferral:
    """Tests for compute_preferred_referral."""

    def test_compute_preferred_referral_typical_returns_most_frequent(self) -> None:
        """'Organic Search' appears 3 times vs 'Ad Campaign' 1 time."""
        assert compute_preferred_referral(_SAMPLE_DF) == "Organic Search"

    def test_compute_preferred_referral_empty_returns_empty_string(self) -> None:
        """Empty user_df returns ''."""
        assert compute_preferred_referral(_EMPTY_DF) == ""


class TestComputeCategoryDiversityCount:
    """Tests for compute_category_diversity_count."""

    def test_compute_category_diversity_count_returns_unique_count(self) -> None:
        """Sample has Electronics + Books → 2 distinct categories."""
        assert compute_category_diversity_count(_SAMPLE_DF) == 2

    def test_compute_category_diversity_count_empty_returns_zero(self) -> None:
        """Empty user_df → 0."""
        assert compute_category_diversity_count(_EMPTY_DF) == 0

    def test_compute_category_diversity_count_single_category_returns_one(self) -> None:
        """All purchases in the same category → 1."""
        df = pd.DataFrame({"Category": ["Books", "Books", "Books"]})
        assert compute_category_diversity_count(df) == 1


class TestComputeProductDiversityCount:
    """Tests for compute_product_diversity_count."""

    def test_compute_product_diversity_count_returns_unique_products(self) -> None:
        """Sample has ProductIDs 1001, 1002, 1003 (1001 repeated) → 3 distinct."""
        assert compute_product_diversity_count(_SAMPLE_DF) == 3

    def test_compute_product_diversity_count_empty_returns_zero(self) -> None:
        """Empty user_df → 0."""
        assert compute_product_diversity_count(_EMPTY_DF) == 0
