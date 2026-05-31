"""Shared pytest fixtures for the Feature Store MVP test suite.

Fixtures defined here are available to all tests without explicit import.
Add test-wide shared state, sample DataFrames, and path helpers here.
"""

from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CSV = FIXTURES_DIR / "sample_data.csv"


@pytest.fixture
def sample_csv_path() -> Path:
    """Return the path to the 10-row sample CSV fixture."""
    return SAMPLE_CSV


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Return the 10-row sample DataFrame loaded from the fixture CSV.

    Uses the raw (uncleaned) CSV — individual tests decide whether to
    call ``clean_transactions`` on top of this.
    """
    return pd.read_csv(SAMPLE_CSV)
